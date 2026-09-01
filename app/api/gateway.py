"""
Gateway API endpoint: POST /v1/gateway/chat.

The primary entry point for all client interactions. Validates the client
Bearer token, delegates processing to the pipeline manager, and maps the
pipeline result to the appropriate HTTP response code.

Every processed request (blocked or allowed) is automatically logged to
the prompt_audit_dataset table for telemetry and HITL review.
"""

import logging
import time

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core import metrics as metrics_module
from app.core.pipeline import manager
from app.core.security import verify_client_token
from app.db.models import PromptAuditEntry
from app.db.session import get_db
from app.models.schemas import (
    BlockedResponse,
    ChatRequest,
    ChatResponse,
    EgressBlockedResponse,
    RequestStatus,
)
from app.services.llm_client import LLMClientService
from app.services.vector_db import VectorDBService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/gateway", tags=["Gateway"])


def _get_vector_db(request: Request) -> VectorDBService:
    """Retrieves the VectorDBService instance from the application state."""
    return request.app.state.vector_db


def _get_llm_client(request: Request) -> LLMClientService:
    """Retrieves the LLMClientService instance from the application state."""
    return request.app.state.llm_client


@router.post(
    "/chat",
    summary="Inspect and Route Chat Message",
    description=(
        "Receives a user prompt, runs it through the 5-layer security pipeline "
        "(Heuristic, Vectorial, AI Classifier, Canary Injection, Egress Scan), "
        "and forwards the sanitized prompt to the backend LLM. "
        "Returns HTTP 200 on success, 400 if blocked at ingress, "
        "and 500 if an egress anomaly is detected in the LLM response. "
        "Every request is automatically logged to the audit dataset."
    ),
    response_model=ChatResponse,
    responses={
        200: {"model": ChatResponse, "description": "Request processed successfully."},
        400: {"model": BlockedResponse, "description": "Request blocked at ingress."},
        401: {"description": "Invalid or missing Bearer token."},
        500: {"model": EgressBlockedResponse, "description": "Egress anomaly detected."},
    },
)
async def chat(
    payload: ChatRequest,
    background_tasks: BackgroundTasks,
    _token: str = Depends(verify_client_token),
    settings: Settings = Depends(get_settings),
    vector_db: VectorDBService = Depends(_get_vector_db),
    llm_client: LLMClientService = Depends(_get_llm_client),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """
    Main gateway endpoint. Orchestrates the full security pipeline.

    The endpoint accepts a JSON body conforming to ChatRequest,
    validates the Authorization: Bearer header, and returns a structured
    JSON response with telemetry data embedded for observability.
    Every request is persisted to the audit dataset regardless of outcome.
    """
    logger.info(
        "Incoming request | user: %s | session: %s | bypass: %s",
        payload.user_id,
        payload.session_id,
        payload.bypass_gateway,
    )

    _t0 = time.monotonic()
    result = await manager.process_request(
        user_id=payload.user_id,
        session_id=payload.session_id,
        message=payload.message,
        bypass_gateway=payload.bypass_gateway,
        settings=settings,
        vector_db=vector_db,
        llm_client=llm_client,
        background_tasks=background_tasks,
    )
    _total_ms = (time.monotonic() - _t0) * 1000

    # -----------------------------------------------------------------------
    # Persist audit entry to the database
    # -----------------------------------------------------------------------
    try:
        is_blocked = isinstance(result, (BlockedResponse, EgressBlockedResponse))
        blocked_layer: str | None = None
        block_reason: str | None = None
        confidence: float | None = None

        if is_blocked and hasattr(result, "telemetry"):
            for layer_t in (result.telemetry or []):
                if layer_t.status.value == "blocked":
                    blocked_layer = layer_t.layer_name
                    block_reason = layer_t.detail
                    if layer_t.layer_name == "layer_3_intelligence" and layer_t.detail:
                        # Extract score if present in detail string
                        try:
                            score_str = layer_t.detail.split("score:")[-1].strip()
                            confidence = float(score_str.split()[0])
                        except (ValueError, IndexError):
                            pass
                    break

        audit_entry = PromptAuditEntry(
            user_id=payload.user_id,
            session_id=payload.session_id,
            prompt_text=payload.message,
            predicted_threat=is_blocked,
            confidence_score=confidence,
            blocked_by_layer=blocked_layer,
            block_reason=block_reason,
        )
        db.add(audit_entry)
        await db.commit()
    except Exception as exc:
        # Audit persistence must never crash the gateway response
        logger.error("Failed to persist audit entry: %s", exc)

    # -----------------------------------------------------------------------
    # Map the pipeline result type to the correct HTTP status code.
    # -----------------------------------------------------------------------
    if isinstance(result, EgressBlockedResponse):
        _http_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    elif isinstance(result, BlockedResponse):
        _http_code = status.HTTP_400_BAD_REQUEST
    else:
        _http_code = status.HTTP_200_OK

    # Record Telescope metrics
    _collector = metrics_module.metrics_collector
    _collector.record_http_status(_http_code)
    _collector.record_request_event(
        user_id=payload.user_id,
        session_id=payload.session_id,
        total_ms=_total_ms,
        http_status=_http_code,
        blocked=_http_code != status.HTTP_200_OK,
        blocked_layer=blocked_layer,
    )

    if _http_code == status.HTTP_500_INTERNAL_SERVER_ERROR:
        return JSONResponse(
            status_code=_http_code,
            content=result.model_dump(mode="json"),
        )

    if _http_code == status.HTTP_400_BAD_REQUEST:
        return JSONResponse(
            status_code=_http_code,
            content=result.model_dump(mode="json"),
        )

    return JSONResponse(
        status_code=_http_code,
        content=result.model_dump(mode="json"),
    )

