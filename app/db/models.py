"""
SQLAlchemy ORM models for the AI Gateway relational database.

Tables:
    - users_notification: Security team members receiving Brevo email alerts.
    - prompt_audit_dataset: All intercepted prompts with Gateway telemetry
      and optional Human-in-the-Loop (HITL) review labels.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""


# ==============================================================================
# Table 1: users_notification
# ==============================================================================

class NotificationRecipient(Base):
    """
    Security team members who receive Brevo SMTP alert emails.

    Managed dynamically via /v1/notifications/recipients endpoints.
    Only recipients with is_active=True are included in alert dispatches.
    """

    __tablename__ = "users_notification"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Identity
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    ci: Mapped[str] = mapped_column(String(30), unique=True, nullable=False,
                                    comment="National ID / Cédula de Identidad")
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)

    # Role within the security team
    role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="SOC_ANALYST",
        comment="SOC_ANALYST | ADMIN | AUDITOR",
    )

    # Alert subscription toggle
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="True = receives alerts; False = silenced",
    )

    # Audit timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<NotificationRecipient id={self.id} email={self.email!r} "
            f"active={self.is_active}>"
        )


# ==============================================================================
# Table 2: prompt_audit_dataset
# ==============================================================================

class PromptAuditEntry(Base):
    """
    Audit log of every prompt processed by the Gateway.

    Each record captures both the Gateway's automatic prediction and,
    optionally, the validated label from a human analyst (HITL workflow).
    Validated entries with is_threat=True can be exported to enrich ChromaDB.
    """

    __tablename__ = "prompt_audit_dataset"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Request context
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)

    # Gateway automatic telemetry
    predicted_threat: Mapped[bool] = mapped_column(
        Boolean, nullable=False,
        comment="True if the Gateway blocked or flagged the prompt"
    )
    confidence_score: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="AI classifier confidence score (Layer 3), if applicable"
    )
    blocked_by_layer: Mapped[str | None] = mapped_column(
        String(50), nullable=True,
        comment="e.g. layer_1_heuristics | layer_2_vectorial | layer_3_intelligence | layer_5_egress"
    )
    block_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Human-in-the-Loop (HITL) review fields
    reviewed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
        comment="True once a human analyst has reviewed this entry"
    )
    is_threat: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True,
        comment="Human verdict: True=confirmed attack, False=false positive / legitimate"
    )
    threat_category: Mapped[str | None] = mapped_column(
        String(50), nullable=True,
        comment="e.g. prompt_leakage | jailbreak | direct_injection | legitimate"
    )
    reviewed_by_ci: Mapped[str | None] = mapped_column(
        String(30), nullable=True,
        comment="CI of the analyst who reviewed this entry (FK to users_notification.ci)"
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return (
            f"<PromptAuditEntry id={self.id} threat={self.predicted_threat} "
            f"reviewed={self.reviewed}>"
        )
