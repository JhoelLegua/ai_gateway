"""
Gateway API endpoint: POST /v1/gateway/chat.

The primary entry point for all client interactions. Validates the client
Bearer token, delegates processing to the pipeline manager, and maps the
pipeline result to the appropriate HTTP response code.
"""

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse

from app.core.config import Settings, get_settings
from app.core.pipeline import manager
from app.core.security import verify_client_token
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
        "and 500 if an egress anomaly is detected in the LLM response."
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
) -> JSONResponse:
    """
    Main gateway endpoint. Orchestrates the full security pipeline.

    The endpoint accepts a JSON body conforming to ChatRequest,
    validates the Authorization: Bearer header, and returns a structured
    JSON response with telemetry data embedded for observability.
    """
    logger.info(
        "Incoming request | user: %s | session: %s | bypass: %s",
        payload.user_id,
        payload.session_id,
        payload.bypass_gateway,
    )

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

    # Map the pipeline result type to the correct HTTP status code.
    if isinstance(result, EgressBlockedResponse):
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=result.model_dump(mode="json"),
        )

    if isinstance(result, BlockedResponse):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=result.model_dump(mode="json"),
        )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=result.model_dump(mode="json"),
    )
