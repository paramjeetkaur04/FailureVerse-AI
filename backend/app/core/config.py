"""Validated environment configuration; secrets never enter public API models."""

from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="FV_", env_file=("../.env", ".env"), extra="ignore"
    )

    environment: Literal["development", "test", "demo"] = "development"
    database_url: str = "sqlite:///./data/failureverse.db"
    demo_health_url: AnyHttpUrl = AnyHttpUrl("http://127.0.0.1:5001/health")
    allowed_origins: list[str] = [
        "http://localhost:5173", "http://127.0.0.1:5173",
        "http://localhost:8080", "http://127.0.0.1:8080",
    ]
    check_timeout_seconds: float = Field(default=2, ge=0.1, le=10)
    history_limit: int = Field(default=120, ge=10, le=1000)
    ollama_base_url: AnyHttpUrl = AnyHttpUrl("http://127.0.0.1:11434")
    ollama_model: str = Field(default="qwen3:8b", min_length=1, max_length=120)
    cloud_api_key: SecretStr = SecretStr("")

    @field_validator("database_url")
    @classmethod
    def phase_one_database(cls, value: str) -> str:
        if not value.startswith("sqlite:///"):
            raise ValueError("Phase 1 supports SQLite only; PostgreSQL is planned.")
        return value

    @field_validator("demo_health_url")
    @classmethod
    def local_demo_only(cls, value: AnyHttpUrl) -> AnyHttpUrl:
        if value.host not in {"127.0.0.1", "localhost", "demo-app"}:
            raise ValueError("Demo health target must be localhost or demo-app.")
        if value.username or value.password or value.query or value.fragment:
            raise ValueError("Demo health target cannot contain credentials or query data.")
        if value.path != "/health":
            raise ValueError("Only the demo /health route is allowed.")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
