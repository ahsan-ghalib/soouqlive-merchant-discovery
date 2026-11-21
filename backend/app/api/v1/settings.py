"""Application settings endpoints (SMTP)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import CurrentUser, DbSession, require_minimum_role
from app.core.permissions import Role
from app.models.user import User
from app.schemas.settings import SmtpSettingsOut, SmtpSettingsUpdate, SmtpTestRequest
from app.services.settings_service import SettingsError, SettingsService
from app.utils.pagination import success_response

router = APIRouter(prefix="/settings", tags=["Settings"])

ManagerUser = Annotated[User, Depends(require_minimum_role(Role.MANAGER))]


@router.get("/smtp")
async def get_smtp_settings(db: DbSession, user: CurrentUser):
    service = SettingsService(db)
    row = await service.get_smtp()
    data = SmtpSettingsOut.model_validate(service.to_out(row)).model_dump(mode="json")
    return success_response(data=data, message="SMTP settings retrieved")


@router.put("/smtp")
async def update_smtp_settings(
    payload: SmtpSettingsUpdate,
    db: DbSession,
    user: ManagerUser,
):
    service = SettingsService(db)
    try:
        row = await service.update_smtp(payload.model_dump())
    except SettingsError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    data = SmtpSettingsOut.model_validate(service.to_out(row)).model_dump(mode="json")
    return success_response(data=data, message="SMTP settings saved")


@router.post("/smtp/test")
async def test_smtp_settings(
    payload: SmtpTestRequest,
    db: DbSession,
    user: ManagerUser,
):
    service = SettingsService(db)
    try:
        result = await service.test_smtp(
            to_email=str(payload.to_email),
            subject=payload.subject,
            body=payload.body,
            use_template=payload.use_template,
            template=payload.template,
        )
    except SettingsError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return success_response(data=result, message="Test email sent")
