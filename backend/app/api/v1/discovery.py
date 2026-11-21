"""Discovery job endpoints."""

from __future__ import annotations

from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import CurrentUser, DbSession, require_minimum_role
from app.core.permissions import Role
from app.models.user import User
from app.schemas.discovery import (
    CityScrapeRequest,
    CoverageSweepRequest,
    DiscoveryJobCreate,
    DiscoveryJobOut,
    DiscoveryPreviewRequest,
)
from app.services.discovery_service import DiscoveryError, DiscoveryService
from app.utils.pagination import paginated_response, success_response

router = APIRouter(prefix="/discovery", tags=["Discovery"])

ResearcherUser = Annotated[User, Depends(require_minimum_role(Role.RESEARCHER))]


def _job_out(job) -> dict:
    return DiscoveryJobOut.model_validate(job).model_dump(mode="json")


@router.post("/jobs")
async def create_discovery_job(
    payload: DiscoveryJobCreate,
    db: DbSession,
    user: ResearcherUser,
):
    service = DiscoveryService(db)
    try:
        job = await service.create_job(payload.model_dump(), user, auto_start=False)
    except DiscoveryError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return success_response(data=_job_out(job), message="Discovery job created")


@router.post("/coverage-sweep")
async def create_coverage_sweep(
    payload: CoverageSweepRequest,
    db: DbSession,
    user: ResearcherUser,
):
    """Launch many Places jobs across districts/cuisines to expand beyond ~60/query."""
    service = DiscoveryService(db)
    try:
        result = await service.create_coverage_sweep(payload.model_dump(), user)
    except DiscoveryError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return success_response(data=result, message="Coverage sweep created")


@router.post("/city-scrape")
async def create_city_scrape(
    payload: CityScrapeRequest,
    db: DbSession,
    user: ResearcherUser,
):
    """One job scrapes an entire city via Places multi-query + geo grid."""
    service = DiscoveryService(db)
    try:
        result = await service.create_city_scrape(payload.model_dump(), user)
    except DiscoveryError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return success_response(data=result, message="City scrape job created")


@router.get("/jobs")
async def list_discovery_jobs(
    db: DbSession,
    user: CurrentUser,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=200),
    status: Optional[str] = None,
):
    service = DiscoveryService(db)
    jobs, total = await service.list_jobs(page=page, limit=limit, status=status)
    return paginated_response(
        [_job_out(j) for j in jobs],
        total=total,
        page=page,
        limit=limit,
        message="Discovery jobs retrieved",
    )


@router.get("/jobs/{job_id}")
async def get_discovery_job(job_id: UUID, db: DbSession, user: CurrentUser):
    service = DiscoveryService(db)
    try:
        job = await service.get_job(job_id)
    except DiscoveryError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return success_response(data=_job_out(job), message="Discovery job retrieved")


@router.post("/jobs/{job_id}/start")
async def start_discovery_job(job_id: UUID, db: DbSession, user: ResearcherUser):
    service = DiscoveryService(db)
    try:
        job = await service.start_job(job_id, user)
    except DiscoveryError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return success_response(data=_job_out(job), message="Discovery job started")


@router.post("/jobs/{job_id}/pause")
async def pause_discovery_job(job_id: UUID, db: DbSession, user: ResearcherUser):
    service = DiscoveryService(db)
    try:
        job = await service.pause_job(job_id)
    except DiscoveryError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return success_response(data=_job_out(job), message="Discovery job paused")


@router.post("/jobs/{job_id}/cancel")
async def cancel_discovery_job(job_id: UUID, db: DbSession, user: ResearcherUser):
    service = DiscoveryService(db)
    try:
        job = await service.cancel_job(job_id)
    except DiscoveryError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return success_response(data=_job_out(job), message="Discovery job cancelled")


@router.post("/jobs/{job_id}/retry")
async def retry_discovery_job(job_id: UUID, db: DbSession, user: ResearcherUser):
    service = DiscoveryService(db)
    try:
        job = await service.retry_job(job_id, user)
    except DiscoveryError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return success_response(data=_job_out(job), message="Discovery job retried")


@router.get("/jobs/{job_id}/results")
async def discovery_job_results(
    job_id: UUID,
    db: DbSession,
    user: CurrentUser,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=200),
):
    service = DiscoveryService(db)
    try:
        businesses, total, job = await service.job_results(job_id, page=page, limit=limit)
    except DiscoveryError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    data = [
        {
            "id": str(b.id),
            "business_name": b.business_name,
            "business_name_ar": b.business_name_ar,
            "website_url": b.website_url,
            "lead_status": b.lead_status,
            "qualification_score": b.qualification_score,
            "created_at": b.created_at.isoformat() if b.created_at else None,
        }
        for b in businesses
    ]
    return paginated_response(
        data,
        total=total,
        page=page,
        limit=limit,
        message=f"Results for job {job.id}",
    )


@router.post("/preview")
async def preview_discovery(
    payload: DiscoveryPreviewRequest,
    db: DbSession,
    user: ResearcherUser,
):
    service = DiscoveryService(db)
    try:
        result = await service.preview(payload.model_dump())
    except DiscoveryError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return success_response(data=result, message="Provider-approved preview")
