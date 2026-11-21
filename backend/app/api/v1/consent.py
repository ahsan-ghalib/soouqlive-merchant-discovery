"""Consent and eligibility endpoints."""

from __future__ import annotations

from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import CurrentUser, DbSession, require_minimum_role
from app.core.permissions import Role
from app.models.user import User
from app.schemas.consent import (
    ConsentCreate,
    ConsentOut,
    ConsentWithdrawRequest,
    EligibilityCheckRequest,
)
from app.services.consent_service import ConsentError, ConsentService
from app.utils.pagination import paginated_response, success_response

router = APIRouter(prefix="/consent", tags=["Consent"])

ResearcherUser = Annotated[User, Depends(require_minimum_role(Role.RESEARCHER))]


@router.get("")
async def list_consent(
    db: DbSession,
    _user: CurrentUser,
    business_id: Optional[UUID] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=200),
):
    rows, total = await ConsentService(db).list_consent(
        business_id=business_id,
        page=page,
        limit=limit,
    )
    data = [ConsentOut.model_validate(r).model_dump(mode="json") for r in rows]
    return paginated_response(data, total=total, page=page, limit=limit, message="Consent records")


@router.post("")
async def create_consent(payload: ConsentCreate, db: DbSession, user: ResearcherUser):
    try:
        record = await ConsentService(db).record_consent(
            business_id=payload.business_id,
            contact_id=payload.contact_id,
            purpose=payload.purpose,
            channel=payload.channel,
            consent_status=payload.consent_status,
            consent_method=payload.consent_method,
            consent_evidence=payload.consent_evidence,
            consented_at=payload.consented_at,
            user=user,
        )
    except ConsentError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return success_response(
        data=ConsentOut.model_validate(record).model_dump(mode="json"),
        message="Consent recorded",
    )


@router.get("/businesses/{business_id}")
async def business_consent(business_id: UUID, db: DbSession, _user: CurrentUser):
    try:
        rows = await ConsentService(db).get_business_consent(business_id)
    except ConsentError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    data = [ConsentOut.model_validate(r).model_dump(mode="json") for r in rows]
    return success_response(data=data, message="Business consent retrieved")


@router.post("/{consent_id}/withdraw")
async def withdraw_consent(
    consent_id: UUID,
    payload: ConsentWithdrawRequest,
    db: DbSession,
    user: ResearcherUser,
):
    try:
        record = await ConsentService(db).withdraw(
            consent_id,
            user,
            reason=payload.reason,
        )
    except ConsentError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return success_response(
        data=ConsentOut.model_validate(record).model_dump(mode="json"),
        message="Consent withdrawn",
    )


@router.post("/check-eligibility")
async def check_eligibility(payload: EligibilityCheckRequest, db: DbSession, _user: CurrentUser):
    result = await ConsentService(db).check_eligibility(
        business_id=payload.business_id,
        purpose=payload.purpose,
        channel=payload.channel,
        contact_id=payload.contact_id,
    )
    return success_response(data=result.to_dict(), message="Eligibility checked")
