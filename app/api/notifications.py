"""
Notification recipients management API.

Endpoints (all require Admin Bearer Token):
    POST   /v1/notifications/recipients          - Register a new SOC recipient
    GET    /v1/notifications/recipients          - List all recipients
    PATCH  /v1/notifications/recipients/{id}/toggle - Toggle active status
    PUT    /v1/notifications/recipients/{id}     - Update recipient data
    DELETE /v1/notifications/recipients/{id}     - Remove a recipient
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_admin_token
from app.db.models import NotificationRecipient
from app.db.session import get_db
from app.models.schemas_admin import RecipientCreate, RecipientResponse, RecipientUpdate

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/v1/notifications",
    tags=["Notifications (Admin)"],
)


@router.post(
    "/recipients",
    response_model=RecipientResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new notification recipient",
    description=(
        "Adds a new SOC team member to the alert distribution list. "
        "Requires Admin Bearer Token. Only active recipients receive Brevo emails."
    ),
)
async def create_recipient(
    payload: RecipientCreate,
    _token: str = Depends(verify_admin_token),
    db: AsyncSession = Depends(get_db),
) -> RecipientResponse:
    """Register a new notification recipient in the database."""
    # Check for duplicates
    existing = await db.execute(
        select(NotificationRecipient).where(
            (NotificationRecipient.email == payload.email)
            | (NotificationRecipient.ci == payload.ci)
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A recipient with this email or CI already exists.",
        )

    recipient = NotificationRecipient(
        first_name=payload.first_name,
        last_name=payload.last_name,
        ci=payload.ci,
        email=payload.email,
        role=payload.role.value,
        is_active=payload.is_active,
    )
    db.add(recipient)
    await db.commit()
    await db.refresh(recipient)

    logger.info("New notification recipient registered: %s (%s)", payload.email, payload.ci)
    return RecipientResponse.model_validate(recipient)


@router.get(
    "/recipients",
    response_model=list[RecipientResponse],
    summary="List notification recipients",
    description=(
        "Returns all registered SOC team members. "
        "Use ?active_only=true to filter only active recipients. "
        "Requires Admin Bearer Token."
    ),
)
async def list_recipients(
    active_only: bool = Query(default=False, description="Filter only active recipients."),
    _token: str = Depends(verify_admin_token),
    db: AsyncSession = Depends(get_db),
) -> list[RecipientResponse]:
    """Retrieve all notification recipients, optionally filtered by active status."""
    query = select(NotificationRecipient).order_by(NotificationRecipient.id)
    if active_only:
        query = query.where(NotificationRecipient.is_active.is_(True))

    result = await db.execute(query)
    recipients = result.scalars().all()
    return [RecipientResponse.model_validate(r) for r in recipients]


@router.patch(
    "/recipients/{recipient_id}/toggle",
    response_model=RecipientResponse,
    summary="Toggle recipient active status",
    description=(
        "Flips the is_active flag for a recipient without deleting the record. "
        "Useful to temporarily silence alerts for a specific person. "
        "Requires Admin Bearer Token."
    ),
)
async def toggle_recipient(
    recipient_id: int,
    _token: str = Depends(verify_admin_token),
    db: AsyncSession = Depends(get_db),
) -> RecipientResponse:
    """Toggle the is_active flag for a notification recipient."""
    result = await db.execute(
        select(NotificationRecipient).where(NotificationRecipient.id == recipient_id)
    )
    recipient = result.scalar_one_or_none()
    if not recipient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipient not found.")

    recipient.is_active = not recipient.is_active
    await db.commit()
    await db.refresh(recipient)

    logger.info(
        "Recipient %s (%s) toggled to is_active=%s",
        recipient.email, recipient.ci, recipient.is_active,
    )
    return RecipientResponse.model_validate(recipient)


@router.put(
    "/recipients/{recipient_id}",
    response_model=RecipientResponse,
    summary="Update recipient data",
    description=(
        "Updates one or more fields of an existing recipient. "
        "Requires Admin Bearer Token."
    ),
)
async def update_recipient(
    recipient_id: int,
    payload: RecipientUpdate,
    _token: str = Depends(verify_admin_token),
    db: AsyncSession = Depends(get_db),
) -> RecipientResponse:
    """Partially update a notification recipient's fields."""
    result = await db.execute(
        select(NotificationRecipient).where(NotificationRecipient.id == recipient_id)
    )
    recipient = result.scalar_one_or_none()
    if not recipient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipient not found.")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "role" and value is not None:
            value = value.value  # Convert enum to string
        setattr(recipient, field, value)

    await db.commit()
    await db.refresh(recipient)
    return RecipientResponse.model_validate(recipient)


@router.delete(
    "/recipients/{recipient_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a notification recipient",
    description=(
        "Permanently removes a recipient from the alert distribution list. "
        "Consider using the toggle endpoint to temporarily silence alerts instead. "
        "Requires Admin Bearer Token."
    ),
)
async def delete_recipient(
    recipient_id: int,
    _token: str = Depends(verify_admin_token),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Permanently delete a notification recipient."""
    result = await db.execute(
        select(NotificationRecipient).where(NotificationRecipient.id == recipient_id)
    )
    recipient = result.scalar_one_or_none()
    if not recipient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipient not found.")

    await db.delete(recipient)
    await db.commit()
    logger.info("Notification recipient id=%s (%s) deleted.", recipient_id, recipient.email)
