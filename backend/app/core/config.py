"""Application settings loaded from environment variables."""

from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: str = "development"
    app_name: str = "SoouqLive Merchant Discovery"
    app_secret_key: str = Field(default="dev-secret-change-me")
    debug: bool = True

    database_url: str = (
        "postgresql+asyncpg://merchant:merchant@localhost:5432/merchant_db"
    )
    database_url_sync: str = (
        "postgresql+psycopg2://merchant:merchant@localhost:5432/merchant_db"
    )

    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    jwt_secret_key: str = Field(default="dev-jwt-secret-change-me-min-32")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    google_maps_api_key: str = ""
    business_provider_api_key: str = ""
    business_provider_base_url: str = ""
    # City-full scrapes fan out many Text Search queries (~60 uniques each)
    places_daily_quota: int = 5000
    # Extra Place Details calls when Text Search lacks phone/website (costs more)
    places_fetch_details: bool = False

    frontend_url: str = "http://localhost:3000"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    suppression_hmac_secret: str = Field(default="dev-suppression-hmac-secret")
    export_storage_path: str = "./storage/exports"
    export_expiry_hours: int = 24

    seed_admin_email: str = "admin@soouqlive.example"
    seed_admin_password: str = "ChangeMeAdmin123!"
    seed_admin_name: str = "System Admin"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def strip_origins(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_development(self) -> bool:
        return self.app_env.lower() in {"development", "dev", "local", "test"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
