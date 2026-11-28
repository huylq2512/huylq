"""Application settings, loaded from environment variables (12-factor).

Settings are created through `get_settings()` and injected where needed,
instead of being a module-level mutable global.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# <repo root>/.env  (backend/app/config.py -> parents[2] is the repo root)
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",  # .env also holds vars used by other components
    )

    app_name: str = "AI Business Management Platform"
    app_env: Literal["development", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    api_prefix: str = "/api/v1"

    # Required (no default): the app fails fast at startup if they are missing.
    database_url: str  # e.g. postgresql+asyncpg://user:pass@host:port/db
    redis_url: str  # e.g. redis://127.0.0.1:6379/0
    secret_key: str = Field(min_length=32)  # signs JWTs; generate with secrets.token_urlsafe(48)

    # Pinned to one algorithm; decoding never trusts the algorithm named in the token header.
    jwt_algorithm: Literal["HS256"] = "HS256"
    access_token_expire_minutes: int = Field(default=30, gt=0)

    health_check_timeout_seconds: float = 2.0

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
