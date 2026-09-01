"""
Layer 2: Vector Similarity Filter.

Performs semantic similarity search against the ChromaDB collection of
confirmed attack signatures. Detects paraphrased or near-duplicate attacks
that evade Layer 1's keyword matching.

Design intent:
    - Catch semantic variants of known injection patterns.
    - Enable the immunity feedback loop: new attacks detected downstream
      are registered here, making Layer 2 progressively more effective.
    - Operate in the 5-20ms range (embedding inference on CPU).
"""

import logging
import time

from app.models.schemas import LayerStatus, LayerTelemetry
from app.services.vector_db import VectorDBService

logger = logging.getLogger(__name__)


def evaluate(prompt: str, vector_db: VectorDBService) -> LayerTelemetry:
    """
    Compares the prompt against known attack vectors in ChromaDB.

    A prompt is considered an attack if its cosine distance to the nearest
    stored signature is at or below the configured similarity threshold.
    Lower distance values indicate higher semantic similarity.

    Args:
        prompt: The user prompt to evaluate.
        vector_db: The initialized VectorDBService instance.

    Returns:
        A LayerTelemetry object with status PASSED or BLOCKED.
    """
    start = time.monotonic()

    try:
        is_attack, distance, matched_doc = vector_db.search_similar_attack(prompt)
    except Exception as exc:
        # If the vector DB is unavailable, log and pass through to avoid
        # a single service failure taking down the entire gateway.
        latency = (time.monotonic() - start) * 1000
        logger.error("Layer 2 vector search failed: %s. Passing through.", str(exc))
        return LayerTelemetry(
            layer_name="layer_2_vectorial",
            status=LayerStatus.PASSED,
            latency_ms=round(latency, 3),
            detail="Vector DB unavailable. Layer bypassed.",
        )

    latency = (time.monotonic() - start) * 1000

    if is_attack:
        excerpt = (matched_doc[:80] + "...") if matched_doc and len(matched_doc) > 80 else matched_doc
        logger.warning(
            "Layer 2 blocked prompt. Cosine distance: %.4f | Matched: '%s'",
            distance,
            excerpt,
        )
        return LayerTelemetry(
            layer_name="layer_2_vectorial",
            status=LayerStatus.BLOCKED,
            latency_ms=round(latency, 3),
            detail=(
                f"High similarity to known attack signature. "
                f"Cosine distance: {distance:.4f}"
            ),
        )

    return LayerTelemetry(
        layer_name="layer_2_vectorial",
        status=LayerStatus.PASSED,
        latency_ms=round(latency, 3),
        detail=f"No similar attack found. Nearest cosine distance: {distance:.4f}",
    )
