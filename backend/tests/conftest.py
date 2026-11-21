"""Shared pytest fixtures."""

from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Ensure test settings before app import
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DEBUG", "false")
os.environ.setdefault("CELERY_TASK_ALWAYS_EAGER", "true")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://merchant:merchant@localhost:5432/merchant_db_test",
)
os.environ.setdefault(
    "DATABASE_URL_SYNC",
    "postgresql+psycopg2://merchant:merchant@localhost:5432/merchant_db_test",
)
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-key-at-least-32-chars")
os.environ.setdefault("APP_SECRET_KEY", "test-app-secret-key")
os.environ.setdefault("SUPPRESSION_HMAC_SECRET", "test-suppression-secret")
os.environ.setdefault("SEED_ADMIN_EMAIL", "admin@soouqlive.example")
os.environ.setdefault("SEED_ADMIN_PASSWORD", "ChangeMeAdmin123!")

from app.core.config import get_settings
from app.core.database import Base, get_db
from app.core.security import hash_password
from app.main import create_app
from app.models.user import User

get_settings.cache_clear()
settings = get_settings()


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def engine():
    eng = create_async_engine(settings.database_url, pool_pre_ping=True)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.execute(
            __import__("sqlalchemy").text("CREATE EXTENSION IF NOT EXISTS pgcrypto")
        )
        await conn.execute(
            __import__("sqlalchemy").text("CREATE EXTENSION IF NOT EXISTS pg_trgm")
        )
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest_asyncio.fixture
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession) -> User:
    user = User(
        id=uuid.uuid4(),
        full_name="Test Admin",
        email=f"admin-{uuid.uuid4().hex[:8]}@soouqlive.example",
        password_hash=hash_password("ChangeMeAdmin123!"),
        role="admin",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def client(engine, admin_user: User) -> AsyncGenerator[AsyncClient, None]:
    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    application = create_app()
    application.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Attach admin credentials for convenience
        ac.admin_email = admin_user.email  # type: ignore[attr-defined]
        ac.admin_password = "ChangeMeAdmin123!"  # type: ignore[attr-defined]
        yield ac

    application.dependency_overrides.clear()
