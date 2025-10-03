"""FastAPI application wiring for the admin dashboard."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from aioredis import Redis, from_url as redis_from_url
from fastapi import FastAPI
from fastapi_admin.app import FastAPIAdmin
from fastapi_admin.middlewares import language_processor
from fastapi_admin.providers.login import UsernamePasswordProvider
from fastapi_admin.routes import router as admin_router
from sqlalchemy.engine import make_url
from starlette.middleware.base import BaseHTTPMiddleware
from tortoise.contrib.fastapi import register_tortoise

from ..config import Settings
from . import admin_models, admin_resources


def create_app(settings: Settings) -> FastAPI:
    """Configure a FastAPI application with FastAPI-Admin mounted at the root."""

    admin_app = _build_admin_app()
    _register_resources(admin_app)

    tortoise_url = settings.admin_database_url or _convert_database_url(settings.database_url)
    register_tortoise(
        admin_app,
        db_url=tortoise_url,
        modules={"models": ["bot_moderator.web.admin_models"]},
        generate_schemas=False,
        add_exception_handlers=True,
    )

    provider = UsernamePasswordProvider(
        admin_model=admin_models.AdminUser,
        login_title="Bot Moderator Admin",
        login_logo_url=settings.admin_logo_url,
    )

    state: dict[str, Optional[Redis]] = {"redis": None}
    configured = {"done": False}

    @admin_app.on_event("startup")
    async def _startup() -> None:
        redis = redis_from_url(settings.admin_redis_url, encoding="utf-8", decode_responses=True)
        state["redis"] = redis
        if not configured["done"]:
            await admin_app.configure(
                redis=redis,
                logo_url=settings.admin_logo_url,
                default_locale=settings.admin_default_locale,
                language_switch=False,
                admin_path="/",
                providers=[provider],
            )
            await _ensure_default_admin(provider, settings)
            configured["done"] = True

    @admin_app.on_event("shutdown")
    async def _shutdown() -> None:
        redis = state.pop("redis", None)
        if redis is not None:
            await redis.close()
        state["redis"] = None

    app = FastAPI(title="Bot Moderator Admin", docs_url=None, redoc_url=None)
    app.mount("/", admin_app)
    return app


def _build_admin_app() -> FastAPIAdmin:
    app = FastAPIAdmin(title="Bot Moderator Admin", description="Admin panel for the moderator bot")
    app.add_middleware(BaseHTTPMiddleware, dispatch=language_processor)
    app.include_router(admin_router)
    return app


def _register_resources(admin_app: FastAPIAdmin) -> None:
    admin_app.register_resources(
        admin_resources.ChatResource,
        admin_resources.UserStateResource,
        admin_resources.BanRecordResource,
        admin_resources.ActionLogResource,
        admin_resources.PendingCaptchaResource,
        admin_resources.JoinRequestResource,
        admin_resources.AdminUserResource,
    )


async def _ensure_default_admin(provider: UsernamePasswordProvider, settings: Settings) -> None:
    if not settings.admin_username or not settings.admin_password:
        return
    exists = await admin_models.AdminUser.filter(username=settings.admin_username).exists()
    if not exists:
        await provider.create_user(
            username=settings.admin_username,
            password=settings.admin_password,
            is_active=True,
            is_superuser=True,
        )


def _convert_database_url(sqlalchemy_url: str) -> str:
    url = make_url(sqlalchemy_url)
    driver = url.drivername
    if driver.startswith("sqlite"):
        if url.database is None or url.database == ":memory":
            return "sqlite://:memory:"
        database_path = Path(url.database)
        if not database_path.is_absolute():
            database_path = (Path.cwd() / database_path).resolve()
        return f"sqlite://{database_path.as_posix()}"
    scheme_map = {
        "postgresql": "postgres",
        "postgresql+asyncpg": "postgres",
        "postgresql+psycopg": "postgres",
        "mysql": "mysql",
        "mysql+asyncmy": "mysql",
        "mysql+aiomysql": "mysql",
    }
    for prefix, scheme in scheme_map.items():
        if driver.startswith(prefix):
            updated = url.set(drivername=scheme)
            return updated.render_as_string(hide_password=False)
    raise ValueError(f"Unsupported database URL for FastAPI-Admin: {sqlalchemy_url}")

