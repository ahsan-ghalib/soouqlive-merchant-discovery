"""Contact management endpoints."""

from __future__ import annotations

from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, require_minimum_role
from app.compliance.suppression import add_suppression
from app.core.permissions import Role
from app.models.contact import BusinessContact
from app.models.user import User
from app.schemas.contact import (
    ContactCreate,
    ContactOut,
    ContactSuppressRequest,
    ContactUpdate,
    ContactVerifyRequest,
)
from app.services.lead_service import LeadError, LeadService
from app.utils.pagination import paginated_response, success_response

router = APIRouter(prefix="/contacts", tags=["Contacts"])

ResearcherUser = Annotated[User, Depends(require_minimum_role(Role.RESEARCHER))]


@router.get("")
async def list_contacts(
    db: DbSession,
    _user: CurrentUser,
    business_id: Optional[UUID] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=200),
):
    stmt = select(BusinessContact)
    if business_id:
        stmt = stmt.where(BusinessContact.business_id == business_id)
    total_stmt = select(BusinessContact)
    if business_id:
        total_stmt = total_stmt.where(BusinessContact.business_id == business_id)
    from sqlalchemy import func

    total = (
        await db.execute(select(func.count()).select_from(total_stmt.subquery()))
    ).scalar_one()
    rows = (
        await db.execute(
            stmt.order_by(BusinessContact.created_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
    ).scalars().all()
    data = [ContactOut.model_validate(c).model_dump(mode="json") for c in rows]
    return paginated_response(data, total=total, page=page, limit=limit, message="Contacts retrieved")


@router.post("")
async def create_contact(payload: ContactCreate, db: DbSession, user: ResearcherUser):
    service = LeadService(db)
    try:
        contact = await service.create_contact(payload, user)
    except LeadError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return success_response(
        data=ContactOut.model_validate(contact).model_dump(mode="json"),
        message="Contact created",
    )


@router.get("/{contact_id}")
async def get_contact(contact_id: UUID, db: DbSession, _user: CurrentUser):
    service = LeadService(db)
    try:
        contact = await service.get_contact(contact_id)
    except LeadError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return success_response(
        data=ContactOut.model_validate(contact).model_dump(mode="json"),
        message="Contact retrieved",
    )


@router.patch("/{contact_id}")
async def update_contact(
    contact_id: UUID,
    payload: ContactUpdate,
    db: DbSession,
    _user: ResearcherUser,
):
    service = LeadService(db)
    try:
        contact = await service.update_contact(contact_id, payload)
    except LeadError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return success_response(
        data=ContactOut.model_validate(contact).model_dump(mode="json"),
        message="Contact updated",
    )


@router.post("/{contact_id}/verify")
async def verify_contact(
    contact_id: UUID,
    payload: ContactVerifyRequest,
    db: DbSession,
    user: ResearcherUser,
):
    service = LeadService(db)
    try:
        contact = await service.verify_contact(
            contact_id,
            verification_method=payload.verification_method,
            is_verified=payload.is_verified,
            user=user,
        )
    except LeadError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return success_response(
        data=ContactOut.model_validate(contact).model_dump(mode="json"),
        message="Contact verification updated",
    )


@router.post("/{contact_id}/suppress")
async def suppress_contact(
    contact_id: UUID,
    payload: ContactSuppressRequest,
    db: DbSession,
    user: ResearcherUser,
):
    service = LeadService(db)
    try:
        contact = await service.get_contact(contact_id)
        record = await add_suppression(
            db,
            contact_type=contact.contact_type,
            contact_value=contact.contact_value,
            channel=payload.channel,
            reason=payload.reason,
        )
        from app.models.activity import Activity
        import uuid as uuid_lib

        db.add(
            Activity(
                id=uuid_lib.uuid4(),
                business_id=contact.business_id,
                user_id=user.id,
                activity_type="opt_out_received",
                description="Contact suppressed",
                metadata_={
                    "contact_id": str(contact.id),
                    "channel": payload.channel,
                    "suppression_id": str(record.id),
                },
            )
        )
        await db.flush()
    except LeadError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return success_response(
        data={
            "contact_id": str(contact.id),
            "suppression_id": str(record.id),
            "channel": payload.channel,
            "note": "Public contact details are not marketing consent; suppression recorded.",
        },
        message="Contact suppressed",
    )
