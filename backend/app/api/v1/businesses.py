"""Business / lead management endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import CurrentUser, DbSession, require_minimum_role
from app.core.permissions import Role
from app.models.user import User
from app.schemas.business import (
    BusinessAssignRequest,
    BusinessBulkImportRequest,
    BusinessBulkUpdateRequest,
    BusinessCreate,
    BusinessListFilters,
    BusinessOut,
    BusinessUpdate,
)
from app.services.lead_service import LeadError, LeadService
from app.utils.pagination import paginated_response, success_response

router = APIRouter(prefix="/businesses", tags=["Businesses"])

ResearcherUser = Annotated[User, Depends(require_minimum_role(Role.RESEARCHER))]
ManagerUser = Annotated[User, Depends(require_minimum_role(Role.MANAGER))]


def _serialize_business(data) -> dict:
    return BusinessOut.model_validate(data).model_dump(mode="json")


@router.get("")
async def list_businesses(
    db: DbSession,
    _user: CurrentUser,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=200),
    city: Optional[str] = None,
    location_id: Optional[UUID] = None,
    category: Optional[str] = None,
    category_id: Optional[UUID] = None,
    lead_status: Optional[str] = None,
    business_status: Optional[str] = None,
    minimum_score: Optional[int] = Query(None, ge=0, le=100),
    maximum_score: Optional[int] = Query(None, ge=0, le=100),
    has_website: Optional[bool] = None,
    has_email: Optional[bool] = None,
    has_phone: Optional[bool] = None,
    source: Optional[str] = None,
    assigned_to: Optional[UUID] = None,
    created_from: Optional[datetime] = None,
    created_to: Optional[datetime] = None,
    search: Optional[str] = None,
):
    filters = BusinessListFilters(
        page=page,
        limit=limit,
        city=city,
        location_id=location_id,
        category=category,
        category_id=category_id,
        lead_status=lead_status,
        business_status=business_status,
        minimum_score=minimum_score,
        maximum_score=maximum_score,
        has_website=has_website,
        has_email=has_email,
        has_phone=has_phone,
        source=source,
        assigned_to=assigned_to,
        created_from=created_from,
        created_to=created_to,
        search=search,
    )
    service = LeadService(db)
    rows, total = await service.list_businesses(filters)
    return paginated_response(
        [_serialize_business(r) for r in rows],
        total=total,
        page=page,
        limit=limit,
        message="Businesses retrieved",
    )


@router.post("")
async def create_business(payload: BusinessCreate, db: DbSession, user: ResearcherUser):
    service = LeadService(db)
    try:
        business, dup = await service.create_business(payload, user)
    except LeadError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    message = "Duplicate merged into existing business" if dup else "Business created"
    return success_response(
        data={
            "business": _serialize_business(business),
            "dedupe": dup,
        },
        message=message,
    )


@router.post("/bulk-import")
async def bulk_import(payload: BusinessBulkImportRequest, db: DbSession, user: ResearcherUser):
    service = LeadService(db)
    try:
        result = await service.bulk_import(
            records=payload.records,
            provider_key=payload.provider,
            user=user,
            location_id=payload.location_id,
            category_id=payload.category_id,
        )
    except LeadError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return success_response(data=result, message="Bulk import completed")


@router.post("/bulk-update")
async def bulk_update(payload: BusinessBulkUpdateRequest, db: DbSession, user: ResearcherUser):
    service = LeadService(db)
    items = [(item.id, item.patch) for item in payload.items]
    result = await service.bulk_update(items, user)
    return success_response(data=result, message="Bulk update completed")


@router.get("/{business_id}")
async def get_business(business_id: UUID, db: DbSession, _user: CurrentUser):
    service = LeadService(db)
    try:
        business = await service.get_business(business_id)
        contacts = await service.list_contacts(business_id)
    except LeadError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    data = _serialize_business(business)
    contact_rows = [
        {
            "id": str(c.id),
            "contact_type": c.contact_type,
            "contact_value": c.contact_value,
            "normalized_value": c.normalized_value,
            "label": c.label,
            "is_primary": c.is_primary,
            "is_verified": c.is_verified,
        }
        for c in contacts
    ]
    phones = [c for c in contact_rows if c["contact_type"] == "business_phone"]
    emails = [c for c in contact_rows if c["contact_type"] == "business_email"]
    data["contacts"] = contact_rows
    data["primary_phone"] = phones[0]["contact_value"] if phones else None
    data["primary_email"] = emails[0]["contact_value"] if emails else None
    data["has_phone"] = bool(phones)
    data["has_email"] = bool(emails)
    data["has_website"] = bool(business.website_url)
    return success_response(data=data, message="Business retrieved")


@router.patch("/{business_id}")
async def update_business(
    business_id: UUID,
    payload: BusinessUpdate,
    db: DbSession,
    user: ResearcherUser,
):
    service = LeadService(db)
    try:
        business = await service.update_business(business_id, payload, user)
    except LeadError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return success_response(data=_serialize_business(business), message="Business updated")


@router.delete("/{business_id}")
async def delete_business(
    business_id: UUID,
    db: DbSession,
    user: ManagerUser,
    hard: bool = Query(False),
):
    service = LeadService(db)
    try:
        result = await service.delete_business(business_id, user, hard=hard)
    except LeadError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return success_response(data=result, message="Business delete processed")


@router.post("/{business_id}/assign")
async def assign_business(
    business_id: UUID,
    payload: BusinessAssignRequest,
    db: DbSession,
    user: ResearcherUser,
):
    service = LeadService(db)
    try:
        business = await service.assign_business(business_id, payload.assigned_to, user)
    except LeadError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return success_response(data=_serialize_business(business), message="Business assigned")


@router.get("/{business_id}/activities")
async def business_activities(
    business_id: UUID,
    db: DbSession,
    _user: CurrentUser,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=200),
):
    service = LeadService(db)
    try:
        rows, total = await service.list_activities(business_id, page=page, limit=limit)
    except LeadError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    data = [
        {
            "id": str(a.id),
            "activity_type": a.activity_type,
            "description": a.description,
            "user_id": str(a.user_id) if a.user_id else None,
            "campaign_id": str(a.campaign_id) if a.campaign_id else None,
            "metadata": a.metadata_,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in rows
    ]
    return paginated_response(
        data, total=total, page=page, limit=limit, message="Activities retrieved"
    )


@router.get("/{business_id}/contacts")
async def business_contacts(business_id: UUID, db: DbSession, _user: CurrentUser):
    service = LeadService(db)
    try:
        contacts = await service.list_contacts(business_id)
    except LeadError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    data = [
        {
            "id": str(c.id),
            "contact_type": c.contact_type,
            "contact_value": c.contact_value,
            "normalized_value": c.normalized_value,
            "label": c.label,
            "is_primary": c.is_primary,
            "is_verified": c.is_verified,
            "verification_method": c.verification_method,
        }
        for c in contacts
    ]
    return success_response(data=data, message="Contacts retrieved")
