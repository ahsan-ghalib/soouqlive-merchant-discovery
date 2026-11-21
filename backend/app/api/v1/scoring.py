"""Lead scoring and CRM workflow endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import CurrentUser, DbSession, require_minimum_role
from app.core.permissions import Role
from app.models.business import Business
from app.models.user import User
from app.schemas.business import BusinessOut
from app.schemas.scoring import (
    LeadTransitionRequest,
    QualifyRequest,
    ScoreBulkRequest,
    ScoreBusinessRequest,
)
from app.services.crm_service import CRMError, CRMService
from app.services.scoring_service import ScoringService
from app.utils.pagination import success_response
from app.workers.scoring_tasks import score_businesses_bulk

router = APIRouter(prefix="/crm", tags=["Scoring & CRM"])

ResearcherUser = Annotated[User, Depends(require_minimum_role(Role.RESEARCHER))]


@router.post("/businesses/score/bulk")
async def score_bulk(payload: ScoreBulkRequest, db: DbSession, user: ResearcherUser):
    if payload.async_mode:
        task = score_businesses_bulk.delay(
            [str(i) for i in payload.business_ids],
            auto_qualify=payload.auto_qualify,
            qualify_threshold=payload.qualify_threshold,
        )
        return success_response(
            data={
                "queued": True,
                "task_id": getattr(task, "id", None),
                "count": len(payload.business_ids),
            },
            message="Bulk scoring queued",
        )

    service = ScoringService(db)
    results = []
    for business_id in payload.business_ids:
        try:
            breakdown = await service.score_business_async(
                business_id,
                user_id=user.id,
                auto_qualify=payload.auto_qualify,
                qualify_threshold=payload.qualify_threshold,
            )
            results.append(
                {
                    "id": str(business_id),
                    "status": "ok",
                    "score": breakdown.total,
                    "components": breakdown.components,
                }
            )
        except Exception as exc:
            results.append({"id": str(business_id), "status": "failed", "error": str(exc)})
    return success_response(data={"results": results}, message="Bulk scoring completed")


@router.post("/businesses/{business_id}/score")
async def score_one(
    business_id: UUID,
    payload: ScoreBusinessRequest,
    db: DbSession,
    user: ResearcherUser,
):
    business = await db.get(Business, business_id)
    if business is None:
        raise HTTPException(status_code=404, detail="Business not found")

    breakdown = await ScoringService(db).score_business_async(
        business_id,
        user_id=user.id,
        auto_qualify=payload.auto_qualify,
        qualify_threshold=payload.qualify_threshold,
    )
    await db.refresh(business)
    return success_response(
        data={
            "business": BusinessOut.model_validate(business).model_dump(mode="json"),
            "score": breakdown.total,
            "components": breakdown.components,
            "details": breakdown.details,
            "qualification_reason": business.qualification_reason,
        },
        message="Lead scored",
    )


@router.get("/businesses/{business_id}/score")
async def get_score(business_id: UUID, db: DbSession, _user: CurrentUser):
    business = await db.get(Business, business_id)
    if business is None:
        raise HTTPException(status_code=404, detail="Business not found")
    return success_response(
        data={
            "business_id": str(business.id),
            "qualification_score": business.qualification_score,
            "qualification_reason": business.qualification_reason,
            "lead_status": business.lead_status,
        },
        message="Score retrieved",
    )


@router.post("/businesses/{business_id}/transition")
async def transition_lead(
    business_id: UUID,
    payload: LeadTransitionRequest,
    db: DbSession,
    user: ResearcherUser,
):
    service = CRMService(db)
    try:
        business = await service.transition_status(
            business_id,
            payload.lead_status,
            user,
            note=payload.note,
            force=payload.force,
        )
    except CRMError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return success_response(
        data=BusinessOut.model_validate(business).model_dump(mode="json"),
        message="Lead status updated",
    )


@router.post("/leads/qualify")
async def qualify_leads(payload: QualifyRequest, db: DbSession, user: ResearcherUser):
    service = CRMService(db)
    try:
        result = await service.qualify_leads(
            user=user,
            business_ids=payload.business_ids,
            minimum_score=payload.minimum_score,
            rescore=payload.rescore,
            limit=payload.limit,
        )
    except CRMError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return success_response(data=result, message="Lead qualification completed")


@router.get("/leads/pipeline")
async def lead_pipeline(db: DbSession, _user: CurrentUser):
    summary = await CRMService(db).pipeline_summary()
    return success_response(data=summary, message="Pipeline summary")
