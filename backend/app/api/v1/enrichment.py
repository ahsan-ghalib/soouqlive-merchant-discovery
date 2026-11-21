"""Enrichment job endpoints."""

from __future__ import annotations

from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import CurrentUser, DbSession, require_minimum_role
from app.core.permissions import Role
from app.models.user import User
from app.schemas.enrichment import EnrichmentBulkRequest, EnrichmentJobCreate, EnrichmentJobOut
from app.services.enrichment_service import EnrichmentError, EnrichmentService
from app.utils.pagination import paginated_response, success_response

router = APIRouter(prefix="/enrichment", tags=["Enrichment"])

ResearcherUser = Annotated[User, Depends(require_minimum_role(Role.RESEARCHER))]


def _job_out(job) -> dict:
    return EnrichmentJobOut.model_validate(job).model_dump(mode="json")


@router.post("/jobs")
async def create_enrichment_job(
    payload: EnrichmentJobCreate,
    db: DbSession,
    user: ResearcherUser,
):
    service = EnrichmentService(db)
    try:
        job = await service.create_job(
            business_id=payload.business_id,
            job_type=payload.job_type,
            user=user,
            auto_start=True,
        )
    except EnrichmentError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return success_response(data=_job_out(job), message="Enrichment job created")


@router.get("/jobs")
async def list_enrichment_jobs(
    db: DbSession,
    _user: CurrentUser,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=200),
    status: Optional[str] = None,
    business_id: Optional[UUID] = None,
):
    service = EnrichmentService(db)
    jobs, total = await service.list_jobs(
        page=page,
        limit=limit,
        status=status,
        business_id=business_id,
    )
    return paginated_response(
        [_job_out(j) for j in jobs],
        total=total,
        page=page,
        limit=limit,
        message="Enrichment jobs retrieved",
    )


@router.get("/jobs/{job_id}")
async def get_enrichment_job(job_id: UUID, db: DbSession, _user: CurrentUser):
    service = EnrichmentService(db)
    try:
        job = await service.get_job(job_id)
    except EnrichmentError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return success_response(data=_job_out(job), message="Enrichment job retrieved")


@router.post("/businesses/{business_id}/run")
async def run_enrichment_for_business(
    business_id: UUID,
    db: DbSession,
    user: ResearcherUser,
    job_type: str = Query("website_discovery"),
):
    service = EnrichmentService(db)
    try:
        job = await service.create_job(
            business_id=business_id,
            job_type=job_type,
            user=user,
            auto_start=True,
        )
    except EnrichmentError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return success_response(data=_job_out(job), message="Enrichment started")


@router.post("/businesses/bulk")
async def bulk_enrichment(
    payload: EnrichmentBulkRequest,
    db: DbSession,
    user: ResearcherUser,
):
    service = EnrichmentService(db)
    result = await service.create_bulk(
        payload.business_ids,
        job_type=payload.job_type,
        user=user,
    )
    return success_response(data=result, message="Bulk enrichment queued")


@router.get("/businesses/{business_id}/results")
async def enrichment_results(business_id: UUID, db: DbSession, _user: CurrentUser):
    service = EnrichmentService(db)
    try:
        data = await service.results_for_business(business_id)
    except EnrichmentError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return success_response(data=data, message="Enrichment results retrieved")
