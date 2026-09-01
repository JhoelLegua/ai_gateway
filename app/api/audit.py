"""
Audit dataset management and HITL review API.

Endpoints (all require Admin Bearer Token):
    GET  /v1/audit/records            - List audit entries (with filters)
    POST /v1/audit/{id}/review        - Submit human-in-the-loop label
    GET  /v1/audit/export/seed        - Export validated threats as seed JSON
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_admin_token
from app.db.models import PromptAuditEntry
from app.db.session import get_db
from app.models.schemas_admin import (
    AuditEntryResponse,
    AuditExportResponse,
    AuditReviewRequest,
    AuditSeedExportEntry,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/v1/audit",
    tags=["Audit Dataset (Admin)"],
)


@router.get(
    "/records",
    response_model=list[AuditEntryResponse],
    summary="List audit dataset records",
    description=(
        "Returns intercepted prompt records. Filter by reviewed status, "
        "threat verdict, or limit results. Ordered by most recent first. "
        "Requires Admin Bearer Token."
    ),
)
async def list_audit_records(
    reviewed: bool | None = Query(default=None, description="Filter by reviewed status."),
    is_threat: bool | None = Query(default=None, description="Filter by human verdict."),
    limit: int = Query(default=100, ge=1, le=1000, description="Max number of records to return."),
    offset: int = Query(default=0, ge=0, description="Number of records to skip (pagination)."),
    _token: str = Depends(verify_admin_token),
    db: AsyncSession = Depends(get_db),
) -> list[AuditEntryResponse]:
    """Retrieve prompt audit records with optional filters."""
    query = (
        select(PromptAuditEntry)
        .order_by(PromptAuditEntry.created_at.desc())
        .limit(limit)
        .offset(offset)
    )

    if reviewed is not None:
        query = query.where(PromptAuditEntry.reviewed.is_(reviewed))
    if is_threat is not None:
        query = query.where(PromptAuditEntry.is_threat.is_(is_threat))

    result = await db.execute(query)
    entries = result.scalars().all()
    return [AuditEntryResponse.model_validate(e) for e in entries]


@router.post(
    "/{entry_id}/review",
    response_model=AuditEntryResponse,
    summary="Submit human-in-the-loop review",
    description=(
        "Allows a SOC analyst to label a prompt record as a confirmed threat "
        "(is_threat=True) or a false positive (is_threat=False). "
        "Records with is_threat=True and reviewed=True are candidates for "
        "ChromaDB seed export. Requires Admin Bearer Token."
    ),
)
async def review_audit_entry(
    entry_id: int,
    payload: AuditReviewRequest,
    _token: str = Depends(verify_admin_token),
    db: AsyncSession = Depends(get_db),
) -> AuditEntryResponse:
    """Submit a human analyst review label for an audit entry."""
    result = await db.execute(
        select(PromptAuditEntry).where(PromptAuditEntry.id == entry_id)
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audit entry not found.")

    entry.reviewed = True
    entry.is_threat = payload.is_threat
    entry.threat_category = payload.threat_category.value if payload.threat_category else None
    entry.reviewed_by_ci = payload.reviewed_by_ci
    entry.reviewed_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(entry)

    logger.info(
        "Audit entry id=%s reviewed by CI=%s | is_threat=%s | category=%s",
        entry_id, payload.reviewed_by_ci, payload.is_threat, payload.threat_category,
    )
    return AuditEntryResponse.model_validate(entry)


@router.get(
    "/export/seed",
    response_model=AuditExportResponse,
    summary="Export validated threats as seed dataset",
    description=(
        "Exports all human-validated threat entries (reviewed=True, is_threat=True) "
        "in the ChromaDB seed-compatible JSON format. "
        "Use this to re-train or enrich the vector database with real attack samples. "
        "Requires Admin Bearer Token."
    ),
)
async def export_seed_dataset(
    _token: str = Depends(verify_admin_token),
    db: AsyncSession = Depends(get_db),
) -> AuditExportResponse:
    """Export all human-validated threats in ChromaDB seed format."""
    result = await db.execute(
        select(PromptAuditEntry).where(
            PromptAuditEntry.reviewed.is_(True),
            PromptAuditEntry.is_threat.is_(True),
        ).order_by(PromptAuditEntry.reviewed_at.asc())
    )
    entries = result.scalars().all()

    seed_entries = [
        AuditSeedExportEntry(
            text=e.prompt_text,
            category=e.threat_category or "other",
            source="hitl_validated",
        )
        for e in entries
    ]

    logger.info("Seed export requested: %d validated threat entries.", len(seed_entries))
    return AuditExportResponse(total_exported=len(seed_entries), entries=seed_entries)
