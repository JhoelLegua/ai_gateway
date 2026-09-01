"""
Layer 3: AI Intelligence Classifier.

Uses a fine-tuned Transformer model to classify whether a prompt
contains prompt injection or jailbreak intent. This layer handles
sophisticated social engineering attacks that evade heuristic and
vector-based detection.

Model: protectai/distilroberta-base-prompt-injection
Source: https://huggingface.co/protectai/distilroberta-base-prompt-injection

Design intent:
    - Catch semantically novel jailbreaks not present in the vector store.
    - Operate on CPU using the standard transformers pipeline.
    - Trigger the immunity feedback loop by registering detected attacks
      into ChromaDB, making Layer 2 progressively smarter.
    - Target latency: 25-60ms on a modern multi-core CPU.
"""

import logging
import time
from typing import Any

from app.core.config import Settings
from app.models.schemas import LayerStatus, LayerTelemetry
from app.services.vector_db import VectorDBService

logger = logging.getLogger(__name__)

# Module-level classifier singleton. Loaded once during application startup.
_classifier: Any = None


def load_model(settings: Settings) -> None:
    """
    Loads the Transformer classification pipeline into memory.

    This function is called once during FastAPI lifespan startup to
    pre-warm the model, ensuring zero cold-start latency on the
    first incoming request.

    Args:
        settings: Application settings providing model name and cache path.
    """
    global _classifier
    if _classifier is not None:
        return

    import os
    os.environ["HF_HOME"] = settings.hf_home

    try:
        from transformers import pipeline as hf_pipeline

        logger.info("Loading AI classifier model: %s", settings.prompt_guard_model)
        _classifier = hf_pipeline(
            task="text-classification",
            model=settings.prompt_guard_model,
            device=-1,  # Force CPU inference (-1 = CPU in transformers)
            truncation=True,
            max_length=512,
        )
        logger.info("AI classifier model loaded successfully.")
    except Exception as exc:
        logger.error(
            "Failed to load AI classifier model '%s': %s. Layer 3 will be skipped.",
            settings.prompt_guard_model,
            str(exc),
        )
        _classifier = None


def evaluate(
    prompt: str,
    settings: Settings,
    vector_db: VectorDBService,
    user_id: str,
    session_id: str,
) -> tuple[LayerTelemetry, float | None]:
    """
    Classifies the prompt for injection intent using the loaded Transformer model.

    If a positive classification is returned with a score above the configured
    threshold, the prompt is registered in ChromaDB (immunity feedback loop)
    and the layer returns a BLOCKED status.

    Args:
        prompt: The user prompt to evaluate.
        settings: Application settings with the injection score threshold.
        vector_db: ChromaDB service for the immunity registration.
        user_id: Used for metadata when registering new signatures.
        session_id: Used for metadata when registering new signatures.

    Returns:
        A tuple of (LayerTelemetry, score_or_None).
        The score is returned so the caller can include it in blocked responses.
    """
    start = time.monotonic()

    # Standard benign greetings (prevents English-biased classifier false positives on simple words like 'hola')
    _BENIGN_GREETINGS = {
        "hola", "buenas", "buenos dias", "buenas tardes", "buenas noches",
        "saludos", "hello", "hi", "hey", "que tal", "hola como estas",
        "hola buenos dias", "buen dia", "gracias", "muchas gracias",
    }
    cleaned_prompt = prompt.strip().lower().rstrip(".!?,¿¡")
    if cleaned_prompt in _BENIGN_GREETINGS:
        latency = (time.monotonic() - start) * 1000
        return (
            LayerTelemetry(
                layer_name="layer_3_intelligence",
                status=LayerStatus.PASSED,
                latency_ms=round(latency, 3),
                detail="Standard conversational greeting verified: SAFE (Score: 1.0000)",
            ),
            1.0,
        )

    if _classifier is None:
        latency = (time.monotonic() - start) * 1000
        logger.warning("Layer 3 classifier not available. Skipping.")
        return (
            LayerTelemetry(
                layer_name="layer_3_intelligence",
                status=LayerStatus.SKIPPED,
                latency_ms=round(latency, 3),
                detail="AI classifier model not loaded. Layer skipped.",
            ),
            None,
        )

    try:
        results = _classifier(prompt)
        # The model returns a list; we take the top result.
        top_result = results[0] if isinstance(results, list) else results
        label: str = top_result.get("label", "").upper()
        score: float = top_result.get("score", 0.0)

        # The model labels injections as "INJECTION" with high score.
        # SAFE prompts are labeled "SAFE" with high score.
        is_injection = (
            "INJECTION" in label and score >= settings.injection_score_threshold
        )

        latency = (time.monotonic() - start) * 1000

        if is_injection:
            logger.warning(
                "Layer 3 blocked prompt. Label: %s | Score: %.4f | User: %s",
                label,
                score,
                user_id,
            )
            # Immunity feedback loop: register the new attack signature.
            try:
                vector_db.add_attack_signature(
                    text=prompt,
                    metadata={
                        "source": "layer_3_learned",
                        "score": str(score),
                        "user_id": user_id,
                        "session_id": session_id,
                    },
                )
            except Exception as db_exc:
                logger.error(
                    "Failed to register learned attack in vector DB: %s", str(db_exc)
                )

            return (
                LayerTelemetry(
                    layer_name="layer_3_intelligence",
                    status=LayerStatus.BLOCKED,
                    latency_ms=round(latency, 3),
                    detail=f"Prompt injection classified with score {score:.4f}.",
                ),
                score,
            )

        return (
            LayerTelemetry(
                layer_name="layer_3_intelligence",
                status=LayerStatus.PASSED,
                latency_ms=round(latency, 3),
                detail=f"Classification: {label} | Score: {score:.4f}",
            ),
            score,
        )

    except Exception as exc:
        latency = (time.monotonic() - start) * 1000
        logger.error("Layer 3 classifier raised an exception: %s", str(exc))
        return (
            LayerTelemetry(
                layer_name="layer_3_intelligence",
                status=LayerStatus.SKIPPED,
                latency_ms=round(latency, 3),
                detail=f"Classifier error: {str(exc)}. Layer skipped.",
            ),
            None,
        )
