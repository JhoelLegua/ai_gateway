"""
Pipeline Manager (Orchestrator).

Coordinates the full Ingress -> Forwarding -> Egress security pipeline.
Applies each layer sequentially, short-circuits on failure, collects
telemetry, updates metrics, and dispatches background email alerts.

This module is the single point of truth for the request processing flow.
"""

import logging
import time
from typing import Any

from fastapi import BackgroundTasks

from app.core import metrics as metrics_module
from app.core.config import Settings
from app.core.pipeline import (
    layer_1_heuristics,
    layer_2_vectorial,
    layer_3_intelligence,
    layer_4_canary,
    layer_5_egress,
)
from app.models.schemas import (
    BlockedResponse,
    ChatResponse,
    EgressBlockedResponse,
    LayerStatus,
    LayerTelemetry,
)
from app.services.email_notifier import send_security_alert
from app.services.llm_client import LLMClientService
from app.services.vector_db import VectorDBService

logger = logging.getLogger(__name__)


async def process_request(
    user_id: str,
    session_id: str,
    message: str,
    bypass_gateway: bool,
    settings: Settings,
    vector_db: VectorDBService,
    llm_client: LLMClientService,
    background_tasks: BackgroundTasks,
) -> ChatResponse | BlockedResponse | EgressBlockedResponse:
    """
    Executes the full security pipeline for a single chat request.

    Pipeline stages:
        [Ingress]
        1. Layer 1 - Heuristic filter (regex / banned substrings)
        2. Layer 2 - Vector similarity search (ChromaDB)
        3. Layer 3 - AI Transformer classifier (Prompt Guard)
        4. Layer 4 - Canary token injection

        [Forwarding]
        5. LLM call via async HTTP client (Groq Cloud or Mock)

        [Egress]
        6. Layer 5 - Response audit (canary + system prompt leak detection)

    When bypass_gateway is True, all ingress layers are skipped and the
    message is forwarded directly to the LLM without security wrapping.

    Args:
        user_id: Client-provided user identifier.
        session_id: Client-provided session identifier.
        message: The raw user prompt.
        bypass_gateway: Skip all security layers for demonstration purposes.
        settings: Application configuration.
        vector_db: Initialized ChromaDB service.
        llm_client: Initialized async LLM client.
        background_tasks: FastAPI task queue for async email dispatch.

    Returns:
        One of ChatResponse (200), BlockedResponse (400), or
        EgressBlockedResponse (500), depending on the pipeline outcome.
    """
    pipeline_start = time.monotonic()
    telemetry: list[LayerTelemetry] = []
    collector = metrics_module.metrics_collector
    collector.record_request()

    # ------------------------------------------------------------------
    # BYPASS MODE: Skip all security layers (demo comparison only)
    # ------------------------------------------------------------------
    if bypass_gateway:
        logger.info(
            "Bypass mode active for user %s. Forwarding directly to LLM.", user_id
        )
        try:
            llm_response = await llm_client.complete(
                user_message=message,
                system_prompt="",
                bypass=True,
            )
        except RuntimeError as exc:
            logger.error("LLM call failed in bypass mode: %s", str(exc))
            llm_response = "The backend LLM is currently unavailable. Please retry."

        total_latency = (time.monotonic() - pipeline_start) * 1000
        return ChatResponse(
            response=llm_response,
            session_id=session_id,
            canary_verified=False,
            telemetry=[],
            total_latency_ms=round(total_latency, 2),
        )

    # ------------------------------------------------------------------
    # LAYER 1: Heuristic Filter
    # ------------------------------------------------------------------
    l1_result = layer_1_heuristics.evaluate(message)
    telemetry.append(l1_result)
    collector.record_layer(
        "layer_1_heuristics",
        l1_result.latency_ms,
        l1_result.status == LayerStatus.BLOCKED,
    )

    if l1_result.status == LayerStatus.BLOCKED:
        _dispatch_alert(
            background_tasks, settings, user_id, session_id,
            "layer_1_heuristics", l1_result.detail or "", message, None,
        )
        return BlockedResponse(
            layer="layer_1_heuristics",
            reason=l1_result.detail or "Heuristic pattern matched.",
            telemetry=telemetry,
        )

    # ------------------------------------------------------------------
    # LAYER 2: Vector Similarity
    # ------------------------------------------------------------------
    l2_result = layer_2_vectorial.evaluate(message, vector_db)
    telemetry.append(l2_result)
    collector.record_layer(
        "layer_2_vectorial",
        l2_result.latency_ms,
        l2_result.status == LayerStatus.BLOCKED,
    )

    if l2_result.status == LayerStatus.BLOCKED:
        _dispatch_alert(
            background_tasks, settings, user_id, session_id,
            "layer_2_vectorial", l2_result.detail or "", message, None,
        )
        return BlockedResponse(
            layer="layer_2_vectorial",
            reason=l2_result.detail or "Similar attack signature found.",
            telemetry=telemetry,
        )

    # ------------------------------------------------------------------
    # LAYER 3: AI Intelligence Classifier
    # ------------------------------------------------------------------
    l3_result, injection_score = layer_3_intelligence.evaluate(
        prompt=message,
        settings=settings,
        vector_db=vector_db,
        user_id=user_id,
        session_id=session_id,
    )
    telemetry.append(l3_result)
    collector.record_layer(
        "layer_3_intelligence",
        l3_result.latency_ms,
        l3_result.status == LayerStatus.BLOCKED,
    )

    if l3_result.status == LayerStatus.BLOCKED:
        _dispatch_alert(
            background_tasks, settings, user_id, session_id,
            "layer_3_intelligence", l3_result.detail or "", message, injection_score,
        )
        return BlockedResponse(
            layer="layer_3_intelligence",
            reason=l3_result.detail or "Prompt injection intent classified by AI.",
            score=injection_score,
            telemetry=telemetry,
        )

    # ------------------------------------------------------------------
    # LAYER 4: Canary Token Injection
    # ------------------------------------------------------------------
    canary_token, protected_system_prompt, l4_result = layer_4_canary.inject(
        message, settings
    )
    telemetry.append(l4_result)

    # ------------------------------------------------------------------
    # FORWARDING: LLM Call
    # ------------------------------------------------------------------
    try:
        llm_response = await llm_client.complete(
            user_message=message,
            system_prompt=protected_system_prompt,
            bypass=False,
        )
    except RuntimeError as exc:
        logger.error("LLM call failed: %s", str(exc))
        total_latency = (time.monotonic() - pipeline_start) * 1000
        return BlockedResponse(
            layer="llm_forwarding",
            reason="Backend LLM is unavailable. Please retry later.",
            telemetry=telemetry,
        )

    # ------------------------------------------------------------------
    # LAYER 5: Egress Scanner
    # ------------------------------------------------------------------
    l5_result = layer_5_egress.evaluate(
        llm_response=llm_response,
        canary_token=canary_token,
        original_prompt=message,
        settings=settings,
        vector_db=vector_db,
        user_id=user_id,
        session_id=session_id,
    )
    telemetry.append(l5_result)
    collector.record_layer(
        "layer_5_egress",
        l5_result.latency_ms,
        l5_result.status == LayerStatus.BLOCKED,
    )

    if l5_result.status == LayerStatus.BLOCKED:
        _dispatch_alert(
            background_tasks, settings, user_id, session_id,
            "layer_5_egress", l5_result.detail or "", message, None,
        )
        return EgressBlockedResponse(
            reason=l5_result.detail or "Egress anomaly detected in LLM response.",
            telemetry=telemetry,
        )

    # ------------------------------------------------------------------
    # SUCCESS: All layers passed
    # ------------------------------------------------------------------
    collector.record_clean()
    total_latency = (time.monotonic() - pipeline_start) * 1000
    logger.info(
        "Request processed cleanly for user %s in %.2fms.", user_id, total_latency
    )

    return ChatResponse(
        response=llm_response,
        session_id=session_id,
        canary_verified=True,
        telemetry=telemetry,
        total_latency_ms=round(total_latency, 2),
    )


def _dispatch_alert(
    background_tasks: BackgroundTasks,
    settings: Settings,
    user_id: str,
    session_id: str,
    layer: str,
    reason: str,
    prompt: str,
    score: float | None,
) -> None:
    """
    Enqueues a security alert email as a background task.

    Using FastAPI BackgroundTasks ensures the email is sent asynchronously
    after the HTTP response has been returned to the client, preventing
    SMTP latency from affecting the client experience.

    Args:
        background_tasks: FastAPI BackgroundTasks instance.
        settings: Application configuration.
        user_id: Identifier of the requesting user.
        session_id: Identifier of the active session.
        layer: The layer identifier that triggered the alert.
        reason: Human-readable block reason.
        prompt: The original user prompt.
        score: Optional AI classifier confidence score.
    """
    background_tasks.add_task(
        send_security_alert,
        settings=settings,
        user_id=user_id,
        session_id=session_id,
        layer=layer,
        reason=reason,
        prompt=prompt,
        score=score,
    )
