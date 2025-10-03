"""Application configuration utilities."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables or `.env`."""

    bot_token: str
    database_url: str = "sqlite+aiosqlite:///./data/moderator.db"
    log_level: str = "INFO"
    default_timezone: str = "Europe/Moscow"
    storage_dir: str = "./data"
    premium_feature_whitelist: set[str] = Field(default_factory=set)
    network_secret: str | None = None
    default_language: Literal["ru", "en"] = "ru"
    report_chat_id: int | None = None
    web_enabled: bool = True
    web_host: str = "0.0.0.0"
    web_port: int = 8080

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    """Return cached settings instance."""

    return Settings()
