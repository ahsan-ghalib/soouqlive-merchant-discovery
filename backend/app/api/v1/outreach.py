"""Slow email outreach blast endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, DbSession, require_minimum_role
from app.core.permissions import Role
from app.models.user import User
from app.services.outreach_service import OutreachError, OutreachService
from app.utils.pagination import success_response

router = APIRouter(prefix="/outreach", tags=["Outreach"])

ManagerUser = Annotated[User, Depends(require_minimum_role(Role.MANAGER))]


class StartVendorBlastRequest(BaseModel):
    name: str = Field(default="Vendor outreach — slow send", max_length=255)
    delay_seconds: int = Field(default=75, ge=45, le=600)
    # Keep conservative for Gmail / deliverability
    daily_limit: int = Field(default=120, ge=20, le=400)
    auto_start: bool = True


@router.post("/vendor-blast")
async def start_vendor_blast(
    payload: StartVendorBlastRequest,
    db: DbSession,
    user: ManagerUser,
):
    """Queue vendor outreach HTML to all sendable emails, one-by-one with delay."""
    service = OutreachService(db)
    try:
        result = await service.create_and_queue_vendor_blast(
            name=payload.name,
            delay_seconds=payload.delay_seconds,
            daily_limit=payload.daily_limit,
            auto_start=payload.auto_start,
        )
    except OutreachError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return success_response(data=result, message="Vendor outreach blast queued")


@router.get("/blasts")
async def list_blasts(db: DbSession, user: CurrentUser, limit: int = Query(20, ge=1, le=100)):
    rows = await OutreachService(db).list_blasts(limit=limit)
    return success_response(data=rows, message="Email blasts")


@router.get("/blasts/{blast_id}")
async def get_blast(blast_id: UUID, db: DbSession, user: CurrentUser):
    try:
        data = await OutreachService(db).status(blast_id)
    except OutreachError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return success_response(data=data, message="Blast status")


@router.post("/blasts/{blast_id}/pause")
async def pause_blast(blast_id: UUID, db: DbSession, user: ManagerUser):
    try:
        blast = await OutreachService(db).pause(blast_id)
    except OutreachError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return success_response(
        data={"id": str(blast.id), "status": blast.status},
        message="Blast paused",
    )


@router.post("/blasts/{blast_id}/resume")
async def resume_blast(blast_id: UUID, db: DbSession, user: ManagerUser):
    try:
        blast = await OutreachService(db).resume(blast_id)
    except OutreachError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return success_response(
        data={"id": str(blast.id), "status": blast.status},
        message="Blast resumed",
    )
