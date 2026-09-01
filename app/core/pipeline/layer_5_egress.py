"""
Layer 5: Egress Scanner.

Audits the raw LLM response before it is delivered to the client.
Detects two categories of egress anomalies:

    1. Canary Token Leakage: The LLM reproduced the secret canary token,
       indicating that its context boundaries were compromised.
    2. System Prompt Leakage: The LLM echoed phrases from internal directives,
       suggesting a successful prompt injection reached the output.

When an anomaly is detected, the response is suppressed, the incident is
registered in ChromaDB for future Layer 2 detection, and an HTTP 500 is
returned to the client.

Design intent:
    - Final safety net before data reaches the user.
    - Zero false negatives on canary token detection (exact string match).
    - Heuristic-based system prompt leak detection.
"""

import logging
import time

from app.core.config import Settings
from app.models.schemas import LayerStatus, LayerTelemetry
from app.services.vector_db import VectorDBService

logger = logging.getLogger(__name__)

# Phrases that, if present in the LLM response, indicate the system prompt
# was leaked or referenced by the model.
_SYSTEM_LEAK_INDICATORS: list[str] = [
    "internal security directive",
    "session integrity token",
    "confidential",
    "you must never reveal",
    "strictly private",
    "bnkcanary_",
]


def evaluate(
    llm_response: str,
    canary_token: str,
    original_prompt: str,
    settings: Settings,
    vector_db: VectorDBService,
    user_id: str,
    session_id: str,
) -> LayerTelemetry:
    """
    Inspects the LLM response for canary token or system prompt leakage.

    Args:
        llm_response: The raw text response from the LLM.
        canary_token: The exact canary token injected in Layer 4.
        original_prompt: The original user prompt, used for immunity registration.
        settings: Application configuration settings.
        vector_db: ChromaDB service for registering egress incidents.
        user_id: User identifier for incident metadata.
        session_id: Session identifier for incident metadata.

    Returns:
        A LayerTelemetry object with status PASSED or BLOCKED.
    """
    start = time.monotonic()
    lowered_response = llm_response.lower()

    # -- Check 1: Exact canary token presence (highest severity) ---------------
    if canary_token and canary_token in llm_response:
        latency = (time.monotonic() - start) * 1000
        logger.critical(
            "EGRESS BREACH: Canary token '%s' found in LLM response. User: %s",
            canary_token,
            user_id,
        )
        _register_egress_incident(
            prompt=original_prompt,
            reason="canary_token_leaked",
            vector_db=vector_db,
            user_id=user_id,
            session_id=session_id,
        )
        return LayerTelemetry(
            layer_name="layer_5_egress",
            status=LayerStatus.BLOCKED,
            latency_ms=round(latency, 3),
            detail="Canary token leakage detected in LLM response.",
        )

    # -- Check 2: System prompt leak indicators --------------------------------
    if settings.enable_egress_system_leak_scan:
        for indicator in _SYSTEM_LEAK_INDICATORS:
            if indicator in lowered_response:
                latency = (time.monotonic() - start) * 1000
                logger.critical(
                    "EGRESS BREACH: System prompt leak indicator '%s' found. User: %s",
                    indicator,
                    user_id,
                )
                _register_egress_incident(
                    prompt=original_prompt,
                    reason="system_prompt_leaked",
                    vector_db=vector_db,
                    user_id=user_id,
                    session_id=session_id,
                )
                return LayerTelemetry(
                    layer_name="layer_5_egress",
                    status=LayerStatus.BLOCKED,
                    latency_ms=round(latency, 3),
                    detail=(
                        f"System context leakage detected. "
                        f"Indicator matched: '{indicator}'"
                    ),
                )

    latency = (time.monotonic() - start) * 1000
    return LayerTelemetry(
        layer_name="layer_5_egress",
        status=LayerStatus.PASSED,
        latency_ms=round(latency, 3),
        detail="Response clean. No canary or system prompt leakage detected.",
    )


def _register_egress_incident(
    prompt: str,
    reason: str,
    vector_db: VectorDBService,
    user_id: str,
    session_id: str,
) -> None:
    """
    Registers the original prompt that caused an egress breach into ChromaDB.

    This enables the immunity feedback loop at the egress level: prompts
    that successfully bypassed ingress layers but caused a detectable
    egress anomaly are recorded for future Layer 2 detection.

    Args:
        prompt: The original user prompt.
        reason: The type of egress incident detected.
        vector_db: ChromaDB service instance.
        user_id: User identifier for metadata.
        session_id: Session identifier for metadata.
    """
    try:
        vector_db.add_attack_signature(
            text=prompt,
            metadata={
                "source": "layer_5_learned",
                "reason": reason,
                "user_id": user_id,
                "session_id": session_id,
            },
        )
    except Exception as exc:
        logger.error(
            "Failed to register egress incident in vector DB: %s", str(exc)
        )
