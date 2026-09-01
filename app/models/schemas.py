"""
Pydantic v2 schemas for all API request and response models.
All models include strict types, field validation, and JSON examples
for automatic OpenAPI / Scalar documentation generation.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


# ==============================================================================
# Enumerations
# ==============================================================================

class AlertSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class RequestStatus(str, Enum):
    SUCCESS = "success"
    BLOCKED = "blocked"
    EGRESS_BLOCKED = "egress_blocked"


class LayerStatus(str, Enum):
    PASSED = "passed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


# ==============================================================================
# Telemetry Schemas
# ==============================================================================

class LayerTelemetry(BaseModel):
    """Represents the execution result of a single security layer."""

    layer_name: str = Field(
        ...,
        description="Internal identifier of the security layer.",
        examples=["layer_3_intelligence"],
    )
    status: LayerStatus = Field(
        ...,
        description="Outcome of the layer evaluation.",
    )
    latency_ms: float = Field(
        ...,
        ge=0,
        description="Time spent in this layer, in milliseconds.",
        examples=[12.4],
    )
    detail: str | None = Field(
        default=None,
        description="Human-readable detail or reason for the outcome.",
        examples=["Prompt injection score: 0.96"],
    )


# ==============================================================================
# Request Schemas
# ==============================================================================

class ChatRequest(BaseModel):
    """Incoming chat request from the client application."""

    user_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Unique identifier of the end user.",
        examples=["usr_98234"],
    )
    session_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Unique identifier of the active user session.",
        examples=["ses_001"],
    )
    message: str = Field(
        ...,
        min_length=1,
        max_length=4096,
        description="The user prompt to be inspected and forwarded to the LLM.",
        examples=["What is my current account balance?"],
    )
    bypass_gateway: bool = Field(
        default=False,
        description=(
            "When True, skips all security layers and forwards the message "
            "directly to the LLM. Intended for demonstration purposes only. "
            "This flag must be disabled in production environments."
        ),
    )

    @field_validator("message")
    @classmethod
    def message_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("message must not be blank or whitespace-only.")
        return value


# ==============================================================================
# Response Schemas
# ==============================================================================

class ChatResponse(BaseModel):
    """Successful response returned to the client after full pipeline execution."""

    status: RequestStatus = Field(default=RequestStatus.SUCCESS)
    response: str = Field(
        ...,
        description="The sanitized LLM response delivered to the client.",
        examples=["Your account balance is available in the Accounts section."],
    )
    session_id: str = Field(
        ...,
        description="Echo of the session identifier from the request.",
        examples=["ses_001"],
    )
    canary_verified: bool = Field(
        default=True,
        description="Confirms that the canary token integrity check passed.",
    )
    telemetry: list[LayerTelemetry] = Field(
        default_factory=list,
        description="Per-layer execution metrics for this request.",
    )
    total_latency_ms: float = Field(
        ...,
        ge=0,
        description="Total end-to-end processing time in milliseconds.",
        examples=[142.5],
    )
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class BlockedResponse(BaseModel):
    """Response returned when the pipeline blocks a request at ingress."""

    status: RequestStatus = Field(default=RequestStatus.BLOCKED)
    layer: str = Field(
        ...,
        description="The layer identifier that triggered the block.",
        examples=["layer_3_intelligence"],
    )
    reason: str = Field(
        ...,
        description="Human-readable explanation of why the request was blocked.",
        examples=["Prompt injection attempt detected with score 0.96."],
    )
    score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Confidence score from the AI classifier, when applicable.",
        examples=[0.96],
    )
    telemetry: list[LayerTelemetry] = Field(
        default_factory=list,
        description="Per-layer metrics up to the point of the block.",
    )
    total_latency_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Total processing time in milliseconds up to block.",
        examples=[18.5],
    )
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class EgressBlockedResponse(BaseModel):
    """Response returned when Layer 5 detects context or canary leakage."""

    status: RequestStatus = Field(default=RequestStatus.EGRESS_BLOCKED)
    layer: str = Field(
        default="layer_5_egress",
        description="Always layer_5_egress for egress anomalies.",
    )
    reason: str = Field(
        ...,
        description="Description of the egress policy violation.",
        examples=["Canary token leakage detected in LLM response."],
    )
    detail: str | None = Field(
        default=None,
        description="Additional technical details for SOC operators.",
    )
    telemetry: list[LayerTelemetry] = Field(
        default_factory=list,
        description="Complete pipeline telemetry.",
    )
    total_latency_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Total processing time in milliseconds.",
        examples=[210.0],
    )
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ==============================================================================
# Monitoring Schemas
# ==============================================================================

class LayerStats(BaseModel):
    """Aggregated block statistics for a single security layer."""

    layer_name: str
    total_blocked: int = Field(ge=0)
    avg_latency_ms: float = Field(ge=0)


class VectorDbInfo(BaseModel):
    """Current state of the ChromaDB vector store."""

    status: str = Field(examples=["online"])
    stored_signatures: int = Field(ge=0, examples=[85])
    path: str = Field(examples=["./data/gateway_vector_db"])


class ModelsInfo(BaseModel):
    """Loaded AI model status."""

    prompt_guard: str = Field(examples=["loaded_onnx_cpu"])
    embedding: str = Field(examples=["all-MiniLM-L6-v2"])


class HealthStatusResponse(BaseModel):
    """Complete health and statistics response for the gateway monitoring endpoint."""

    status: str = Field(examples=["healthy"])
    app_env: str = Field(examples=["development"])
    uptime_seconds: float = Field(ge=0, examples=[3600.0])
    total_requests: int = Field(ge=0, examples=[1500])
    clean_passed: int = Field(ge=0, examples=[1420])
    layer_stats: list[LayerStats] = Field(default_factory=list)
    vector_db: VectorDbInfo
    models: ModelsInfo
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ResetVaultResponse(BaseModel):
    """Confirmation response after resetting the attack vector database."""

    status: str = Field(examples=["reset_complete"])
    message: str = Field(
        examples=["Attack vault cleared and reseeded with initial attack signatures."]
    )
    signatures_loaded: int = Field(ge=0, examples=[20])
    timestamp: datetime = Field(default_factory=datetime.utcnow)
