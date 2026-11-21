"""FastAPI application entrypoint."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.core.redis import close_redis, get_redis
from app.utils.pagination import success_response


@asynccontextmanager
async def lifespan(_app: FastAPI):
    setup_logging()
    # Warm Redis connection (non-fatal if Redis is down during early boot)
    try:
        client = await get_redis()
        await client.ping()
    except Exception:
        pass
    yield
    await close_redis()


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.is_development else None,
        redoc_url="/redoc" if settings.is_development else None,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(api_router)

    @application.get("/health")
    async def health():
        return success_response(
            data={"status": "ok", "env": settings.app_env},
            message="Healthy",
        )

    return application


app = create_app()
