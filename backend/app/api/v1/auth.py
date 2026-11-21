"""Authentication endpoints."""

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    LoginResponseData,
    RefreshRequest,
    TokenPair,
    UserOut,
)
from app.services.auth_service import AuthError, AuthService
from app.utils.pagination import success_response

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login")
async def login(payload: LoginRequest, db: DbSession):
    service = AuthService(db)
    try:
        user, tokens = await service.authenticate(payload.email, payload.password)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    data = LoginResponseData(user=UserOut.model_validate(user), tokens=tokens)
    return success_response(data=data.model_dump(mode="json"), message="Login successful")


@router.post("/refresh")
async def refresh(payload: RefreshRequest, db: DbSession):
    service = AuthService(db)
    try:
        tokens = await service.refresh(payload.refresh_token)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return success_response(
        data=tokens.model_dump(),
        message="Token refreshed",
    )


@router.post("/logout")
async def logout(payload: RefreshRequest, db: DbSession, _user: CurrentUser):
    service = AuthService(db)
    await service.logout(payload.refresh_token)
    return success_response(message="Logged out successfully")


@router.get("/me")
async def me(user: CurrentUser):
    return success_response(
        data=UserOut.model_validate(user).model_dump(mode="json"),
        message="Current user",
    )


@router.post("/change-password")
async def change_password(
    payload: ChangePasswordRequest,
    db: DbSession,
    user: CurrentUser,
):
    service = AuthService(db)
    try:
        await service.change_password(
            user,
            payload.current_password,
            payload.new_password,
        )
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return success_response(message="Password changed successfully")
