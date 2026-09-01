"""
Monitoring API endpoints.

Provides operational visibility into the gateway's runtime state:
    - GET  /v1/gateway/health       : Health check with aggregated statistics.
    - POST /v1/gateway/reset-vault  : Clears and reseeds the attack vector database.
"""

import logging

from fastapi import APIRouter, Depends, Request

from app.core import metrics as metrics_module
from app.core.config import Settings, get_settings
from app.core.security import verify_client_token
from app.models.schemas import (
    HealthStatusResponse,
    LayerStats,
    ModelsInfo,
    ResetVaultResponse,
    VectorDbInfo,
)
from app.services.vector_db import VectorDBService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/gateway", tags=["Monitoring"])


def _get_vector_db(request: Request) -> VectorDBService:
    """Retrieves the VectorDBService instance from the application state."""
    return request.app.state.vector_db


@router.get(
    "/health",
    summary="Gateway Health and Statistics",
    description=(
        "Returns the operational status of all gateway components including "
        "the ChromaDB vector store, loaded AI models, and aggregated request "
        "statistics broken down by security layer."
    ),
    response_model=HealthStatusResponse,
)
async def health(
    settings: Settings = Depends(get_settings),
    vector_db: VectorDBService = Depends(_get_vector_db),
) -> HealthStatusResponse:
    """
    Returns a comprehensive health report including per-layer block statistics,
    ChromaDB state, and model availability.
    """
    collector = metrics_module.metrics_collector
    raw_layer_stats = collector.get_layer_stats()
    layer_stats = [LayerStats(**s) for s in raw_layer_stats]

    try:
        sig_count = vector_db.get_signature_count()
        db_status = "online"
    except Exception:
        sig_count = 0
        db_status = "offline"

    from app.core.pipeline.layer_3_intelligence import _classifier
    model_status = "loaded" if _classifier is not None else "unavailable"

    return HealthStatusResponse(
        status="healthy",
        app_env=settings.app_env,
        uptime_seconds=collector.uptime_seconds,
        total_requests=collector.total_requests,
        clean_passed=collector.clean_passed,
        layer_stats=layer_stats,
        vector_db=VectorDbInfo(
            status=db_status,
            stored_signatures=sig_count,
            path=settings.vector_db_path,
        ),
        models=ModelsInfo(
            prompt_guard=f"{model_status}: {settings.prompt_guard_model}",
            embedding=settings.embedding_model_name,
        ),
    )


@router.post(
    "/reset-vault",
    summary="Reset Attack Vector Database",
    description=(
        "Deletes all learned and seeded attack signatures from ChromaDB "
        "and reloads the baseline seed dataset. This also resets the "
        "in-memory metrics counters. Requires a valid Bearer token."
    ),
    response_model=ResetVaultResponse,
)
async def reset_vault(
    _token: str = Depends(verify_client_token),
    vector_db: VectorDBService = Depends(_get_vector_db),
) -> ResetVaultResponse:
    """
    Resets the attack vault and reseeds from the baseline dataset.
    Also resets all in-memory metrics counters.
    """
    logger.warning("Reset vault requested. Clearing ChromaDB and reseeding.")
    vector_db.reset()
    metrics_module.metrics_collector.reset()
    sig_count = vector_db.get_signature_count()

    return ResetVaultResponse(
        status="reset_complete",
        message="Attack vault cleared and reseeded with initial attack signatures.",
        signatures_loaded=sig_count,
    )
