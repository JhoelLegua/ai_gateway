"""
Pydantic v2 schemas for Admin and SOC management endpoints.

Covers:
    - Notification recipient CRUD (users_notification)
    - Audit dataset review and export (prompt_audit_dataset)
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, EmailStr, Field, field_validator


# ==============================================================================
# Enumerations
# ==============================================================================

class RecipientRole(str, Enum):
    ADMIN = "ADMIN"
    SOC_ANALYST = "SOC_ANALYST"
    AUDITOR = "AUDITOR"


class ThreatCategory(str, Enum):
    PROMPT_LEAKAGE = "prompt_leakage"
    JAILBREAK = "jailbreak"
    DIRECT_INJECTION = "direct_injection"
    SOCIAL_ENGINEERING = "social_engineering"
    DATA_EXFIL = "data_exfil"
    LEGITIMATE = "legitimate"
    OTHER = "other"


# ==============================================================================
# Notification Recipient Schemas
# ==============================================================================

class RecipientCreate(BaseModel):
    """Payload to register a new SOC/Admin notification recipient."""

    first_name: str = Field(
        ..., min_length=1, max_length=100,
        description="Recipient's first name.",
        examples=["Carlos"],
    )
    last_name: str = Field(
        ..., min_length=1, max_length=100,
        description="Recipient's last name.",
        examples=["Ramírez"],
    )
    ci: str = Field(
        ..., min_length=4, max_length=30,
        description="National ID / Cédula de Identidad (unique identifier).",
        examples=["V-12345678"],
    )
    email: str = Field(
        ...,
        description="Email address that will receive Brevo security alerts.",
        examples=["c.ramirez@secops.local"],
    )
    role: RecipientRole = Field(
        default=RecipientRole.SOC_ANALYST,
        description="Role of the recipient within the security team.",
    )
    is_active: bool = Field(
        default=True,
        description="Whether this recipient should receive alert emails.",
    )

    @field_validator("email")
    @classmethod
    def lowercase_email(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("ci")
    @classmethod
    def normalize_ci(cls, v: str) -> str:
        return v.strip().upper()


class RecipientUpdate(BaseModel):
    """Partial update payload for a notification recipient."""

    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    email: str | None = Field(default=None)
    role: RecipientRole | None = Field(default=None)
    is_active: bool | None = Field(default=None)

    @field_validator("email")
    @classmethod
    def lowercase_email(cls, v: str | None) -> str | None:
        return v.strip().lower() if v else v


class RecipientResponse(BaseModel):
    """Full representation of a notification recipient, as returned by the API."""

    id: int
    first_name: str
    last_name: str
    ci: str
    email: str
    role: RecipientRole
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ==============================================================================
# Audit Dataset Schemas
# ==============================================================================

class AuditEntryResponse(BaseModel):
    """Representation of a single audit entry, as returned by the API."""

    id: int
    user_id: str
    session_id: str
    prompt_text: str
    predicted_threat: bool
    confidence_score: float | None
    blocked_by_layer: str | None
    block_reason: str | None
    created_at: datetime

    # HITL fields
    reviewed: bool
    is_threat: bool | None
    threat_category: str | None
    reviewed_by_ci: str | None
    reviewed_at: datetime | None

    model_config = {"from_attributes": True}


class AuditReviewRequest(BaseModel):
    """Payload submitted by a human analyst to label an audit entry."""

    is_threat: bool = Field(
        ...,
        description="True = confirmed attack. False = false positive / legitimate prompt.",
    )
    threat_category: ThreatCategory | None = Field(
        default=None,
        description="Category of the threat (required when is_threat=True).",
    )
    reviewed_by_ci: str = Field(
        ..., min_length=4, max_length=30,
        description="CI of the analyst submitting this review.",
        examples=["V-12345678"],
    )

    @field_validator("threat_category")
    @classmethod
    def category_required_when_threat(
        cls, v: ThreatCategory | None, info: Any
    ) -> ThreatCategory | None:
        values = info.data
        if values.get("is_threat") is True and v is None:
            raise ValueError("threat_category is required when is_threat=True")
        return v


class AuditSeedExportEntry(BaseModel):
    """A single entry in the seed JSON export format (ChromaDB-compatible)."""

    text: str
    category: str
    source: str = "hitl_validated"


class AuditExportResponse(BaseModel):
    """Response returned by the seed export endpoint."""

    total_exported: int
    entries: list[AuditSeedExportEntry]
