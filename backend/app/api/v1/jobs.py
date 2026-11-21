"""Cross-queue job monitoring endpoints."""

from __future__ import annotations

from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession, require_minimum_role
from app.core.permissions import Role
from app.models.discovery_job import DiscoveryJob, EnrichmentJob
from app.models.user import User
from app.services.discovery_service import DiscoveryError, DiscoveryService
from app.utils.pagination import paginated_response, success_response

router = APIRouter(prefix="/jobs", tags=["Jobs"])

ResearcherUser = Annotated[User, Depends(require_minimum_role(Role.RESEARCHER))]


@router.get("")
async def list_jobs(
    db: DbSession,
    _user: CurrentUser,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=200),
    job_type: Optional[str] = Query(None, description="discovery|enrichment"),
    status: Optional[str] = None,
):
    if job_type == "enrichment":
        stmt = select(EnrichmentJob)
        count_stmt = select(func.count()).select_from(EnrichmentJob)
        if status:
            stmt = stmt.where(EnrichmentJob.status == status)
            count_stmt = count_stmt.where(EnrichmentJob.status == status)
        total = (await db.execute(count_stmt)).scalar_one()
        rows = (
            await db.execute(
                stmt.order_by(EnrichmentJob.created_at.desc())
                .offset((page - 1) * limit)
                .limit(limit)
            )
        ).scalars().all()
        data = [
            {
                "id": str(j.id),
                "job_family": "enrichment",
                "job_type": j.job_type,
                "business_id": str(j.business_id),
                "status": j.status,
                "attempts": j.attempts,
                "created_at": j.created_at.isoformat() if j.created_at else None,
                "completed_at": j.completed_at.isoformat() if j.completed_at else None,
            }
            for j in rows
        ]
    else:
        stmt = select(DiscoveryJob)
        count_stmt = select(func.count()).select_from(DiscoveryJob)
        if status:
            stmt = stmt.where(DiscoveryJob.status == status)
            count_stmt = count_stmt.where(DiscoveryJob.status == status)
        total = (await db.execute(count_stmt)).scalar_one()
        rows = (
            await db.execute(
                stmt.order_by(DiscoveryJob.created_at.desc())
                .offset((page - 1) * limit)
                .limit(limit)
            )
        ).scalars().all()
        data = [
            {
                "id": str(j.id),
                "job_family": "discovery",
                "name": j.name,
                "provider_id": str(j.provider_id) if j.provider_id else None,
                "status": j.status,
                "total_expected": j.total_expected,
                "total_processed": j.total_processed,
                "total_created": j.total_created,
                "total_duplicates": j.total_duplicates,
                "total_failed": j.total_failed,
                "started_at": j.started_at.isoformat() if j.started_at else None,
                "completed_at": j.completed_at.isoformat() if j.completed_at else None,
                "created_at": j.created_at.isoformat() if j.created_at else None,
            }
            for j in rows
        ]

    return paginated_response(data, total=total, page=page, limit=limit, message="Jobs retrieved")


@router.get("/queue/stats")
async def queue_stats(db: DbSession, _user: CurrentUser):
    discovery_counts = {}
    for status in ["pending", "queued", "processing", "completed", "failed", "cancelled"]:
        discovery_counts[status] = (
            await db.execute(
                select(func.count()).select_from(DiscoveryJob).where(DiscoveryJob.status == status)
            )
        ).scalar_one()

    enrichment_pending = (
        await db.execute(
            select(func.count()).select_from(EnrichmentJob).where(EnrichmentJob.status == "pending")
        )
    ).scalar_one()

    return success_response(
        data={
            "discovery": discovery_counts,
            "enrichment": {"pending": enrichment_pending},
            "queues": ["discovery", "enrichment", "validation", "scoring", "exports", "maintenance"],
        },
        message="Queue stats",
    )


@router.get("/worker/stats")
async def worker_stats(_user: CurrentUser):
    try:
        from app.workers.celery_app import celery_app

        inspector = celery_app.control.inspect(timeout=1.0)
        stats = inspector.stats() if inspector else None
        active = inspector.active() if inspector else None
        return success_response(
            data={"stats": stats or {}, "active": active or {}, "reachable": bool(stats)},
            message="Worker stats",
        )
    except Exception:
        return success_response(
            data={"stats": {}, "active": {}, "reachable": False},
            message="Worker stats unavailable",
        )


@router.get("/{job_id}")
async def get_job(job_id: UUID, db: DbSession, _user: CurrentUser):
    job = await db.get(DiscoveryJob, job_id)
    if job:
        return success_response(
            data={
                "id": str(job.id),
                "job_family": "discovery",
                "name": job.name,
                "status": job.status,
                "total_expected": job.total_expected,
                "total_processed": job.total_processed,
                "total_created": job.total_created,
                "total_duplicates": job.total_duplicates,
                "total_failed": job.total_failed,
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            },
            message="Job retrieved",
        )

    enrichment = await db.get(EnrichmentJob, job_id)
    if enrichment:
        return success_response(
            data={
                "id": str(enrichment.id),
                "job_family": "enrichment",
                "job_type": enrichment.job_type,
                "status": enrichment.status,
                "business_id": str(enrichment.business_id),
                "attempts": enrichment.attempts,
            },
            message="Job retrieved",
        )

    raise HTTPException(status_code=404, detail="Job not found")


@router.post("/{job_id}/retry")
async def retry_job(job_id: UUID, db: DbSession, user: ResearcherUser):
    service = DiscoveryService(db)
    try:
        job = await service.retry_job(job_id, user)
    except DiscoveryError as exc:
        enrichment = await db.get(EnrichmentJob, job_id)
        if enrichment is None:
            raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
        enrichment.status = "pending"
        enrichment.attempts = 0
        enrichment.error_message = None
        await db.flush()
        return success_response(
            data={"id": str(enrichment.id), "status": enrichment.status},
            message="Enrichment job queued for retry",
        )
    return success_response(
        data={
            "id": str(job.id),
            "status": job.status,
            "job_family": "discovery",
        },
        message="Job retried",
    )
