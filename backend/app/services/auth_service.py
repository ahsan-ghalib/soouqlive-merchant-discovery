"""Authentication business logic."""

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    needs_rehash,
    verify_password,
)
from app.models.user import RefreshToken, User
from app.schemas.auth import TokenPair


class AuthError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.settings = get_settings()

    async def authenticate(self, email: str, password: str) -> tuple[User, TokenPair]:
        result = await self.db.execute(
            select(User).where(User.email == email.lower().strip())
        )
        user = result.scalar_one_or_none()
        if user is None or not verify_password(password, user.password_hash):
            raise AuthError("Invalid email or password", status_code=401)
        if not user.is_active:
            raise AuthError("User account is inactive", status_code=403)

        if needs_rehash(user.password_hash):
            user.password_hash = hash_password(password)

        tokens = await self._issue_tokens(user)
        user.last_login_at = datetime.now(timezone.utc)
        await self.db.flush()
        await self.db.refresh(user)
        return user, tokens

    async def refresh(self, refresh_token: str) -> TokenPair:
        try:
            payload = decode_token(refresh_token)
        except jwt.PyJWTError as exc:
            raise AuthError("Invalid or expired refresh token", status_code=401) from exc

        if payload.get("type") != "refresh":
            raise AuthError("Invalid refresh token type", status_code=401)

        jti = payload.get("jti")
        user_id = payload.get("sub")
        if not jti or not user_id:
            raise AuthError("Invalid refresh token payload", status_code=401)

        result = await self.db.execute(
            select(RefreshToken).where(RefreshToken.jti == jti)
        )
        stored = result.scalar_one_or_none()
        if stored is None or stored.revoked_at is not None:
            raise AuthError("Refresh token revoked or unknown", status_code=401)
        if stored.expires_at < datetime.now(timezone.utc):
            raise AuthError("Refresh token expired", status_code=401)
        if stored.token_hash != _hash_token(refresh_token):
            raise AuthError("Refresh token mismatch", status_code=401)

        user_result = await self.db.execute(select(User).where(User.id == UUID(user_id)))
        user = user_result.scalar_one_or_none()
        if user is None or not user.is_active:
            raise AuthError("User not found or inactive", status_code=401)

        # Rotate refresh token
        stored.revoked_at = datetime.now(timezone.utc)
        tokens = await self._issue_tokens(user)
        await self.db.flush()
        return tokens

    async def logout(self, refresh_token: Optional[str]) -> None:
        if not refresh_token:
            return
        try:
            payload = decode_token(refresh_token)
        except jwt.PyJWTError:
            return
        jti = payload.get("jti")
        if not jti:
            return
        result = await self.db.execute(
            select(RefreshToken).where(RefreshToken.jti == jti)
        )
        stored = result.scalar_one_or_none()
        if stored and stored.revoked_at is None:
            stored.revoked_at = datetime.now(timezone.utc)
            await self.db.flush()

    async def change_password(
        self,
        user: User,
        current_password: str,
        new_password: str,
    ) -> None:
        if not verify_password(current_password, user.password_hash):
            raise AuthError("Current password is incorrect", status_code=400)
        if current_password == new_password:
            raise AuthError("New password must be different", status_code=400)

        user.password_hash = hash_password(new_password)

        # Revoke all refresh tokens for this user
        result = await self.db.execute(
            select(RefreshToken).where(
                RefreshToken.user_id == user.id,
                RefreshToken.revoked_at.is_(None),
            )
        )
        for token in result.scalars().all():
            token.revoked_at = datetime.now(timezone.utc)
        await self.db.flush()

    async def _issue_tokens(self, user: User) -> TokenPair:
        access = create_access_token(user.id, user.role)
        refresh = create_refresh_token(user.id)
        payload = decode_token(refresh)
        jti = payload["jti"]
        expires_at = datetime.now(timezone.utc) + timedelta(
            days=self.settings.refresh_token_expire_days
        )
        self.db.add(
            RefreshToken(
                user_id=user.id,
                jti=jti,
                token_hash=_hash_token(refresh),
                expires_at=expires_at,
            )
        )
        await self.db.flush()
        return TokenPair(access_token=access, refresh_token=refresh)
