"""Campaign management endpoints."""

from __future__ import annotations

from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import CurrentUser, DbSession, require_minimum_role
from app.core.permissions import Role
from app.models.user import User
from app.schemas.campaign import (
    CampaignCreate,
    CampaignLeadsAddRequest,
    CampaignOut,
    CampaignQualifyRequest,
    CampaignUpdate,
)
from app.services.campaign_service import CampaignError, CampaignService
from app.utils.pagination import paginated_response, success_response

router = APIRouter(prefix="/campaigns", tags=["Campaigns"])

ResearcherUser = Annotated[User, Depends(require_minimum_role(Role.RESEARCHER))]
ManagerUser = Annotated[User, Depends(require_minimum_role(Role.MANAGER))]


def _out(campaign) -> dict:
    return CampaignOut.model_validate(campaign).model_dump(mode="json")


@router.get("")
async def list_campaigns(
    db: DbSession,
    _user: CurrentUser,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=200),
    status: Optional[str] = None,
):
    rows, total = await CampaignService(db).list_campaigns(page=page, limit=limit, status=status)
    return paginated_response(
        [_out(c) for c in rows],
        total=total,
        page=page,
        limit=limit,
        message="Campaigns retrieved",
    )


@router.post("")
async def create_campaign(payload: CampaignCreate, db: DbSession, user: ResearcherUser):
    try:
        campaign = await CampaignService(db).create(payload.model_dump(), user)
    except CampaignError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return success_response(data=_out(campaign), message="Campaign created")


@router.get("/{campaign_id}")
async def get_campaign(campaign_id: UUID, db: DbSession, _user: CurrentUser):
    try:
        campaign = await CampaignService(db).get(campaign_id)
    except CampaignError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return success_response(data=_out(campaign), message="Campaign retrieved")


@router.patch("/{campaign_id}")
async def update_campaign(
    campaign_id: UUID,
    payload: CampaignUpdate,
    db: DbSession,
    user: ResearcherUser,
):
    try:
        campaign = await CampaignService(db).update(
            campaign_id,
            payload.model_dump(exclude_unset=True),
        )
    except CampaignError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return success_response(data=_out(campaign), message="Campaign updated")


@router.delete("/{campaign_id}")
async def delete_campaign(campaign_id: UUID, db: DbSession, user: ManagerUser):
    try:
        await CampaignService(db).delete(campaign_id)
    except CampaignError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return success_response(message="Campaign deleted")


@router.post("/{campaign_id}/leads")
async def add_campaign_leads(
    campaign_id: UUID,
    payload: CampaignLeadsAddRequest,
    db: DbSession,
    user: ResearcherUser,
):
    try:
        result = await CampaignService(db).add_leads(
            campaign_id,
            payload.business_ids,
            user,
            assigned_to=payload.assigned_to,
        )
    except CampaignError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return success_response(data=result, message="Leads added to campaign")


@router.delete("/{campaign_id}/leads/{business_id}")
async def remove_campaign_lead(
    campaign_id: UUID,
    business_id: UUID,
    db: DbSession,
    user: ResearcherUser,
):
    try:
        await CampaignService(db).remove_lead(campaign_id, business_id)
    except CampaignError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return success_response(message="Lead removed from campaign")


@router.get("/{campaign_id}/analytics")
async def campaign_analytics(campaign_id: UUID, db: DbSession, _user: CurrentUser):
    try:
        data = await CampaignService(db).analytics(campaign_id)
    except CampaignError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return success_response(data=data, message="Campaign analytics")


@router.post("/{campaign_id}/qualify")
async def qualify_campaign(
    campaign_id: UUID,
    payload: CampaignQualifyRequest,
    db: DbSession,
    user: ResearcherUser,
):
    try:
        result = await CampaignService(db).qualify_campaign(
            campaign_id,
            user,
            minimum_score=payload.minimum_score,
            rescore=payload.rescore,
        )
    except CampaignError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return success_response(data=result, message="Campaign leads qualified")
