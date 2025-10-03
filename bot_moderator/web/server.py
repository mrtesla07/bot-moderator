"""FastAPI server exposing a lightweight admin UI."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from ..config import Settings
from ..services.container import ServiceContainer

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def create_app(services: ServiceContainer, settings: Settings) -> FastAPI:
    app = FastAPI(title="Bot Moderator UI", docs_url=None, redoc_url=None)
    app.state.services = services
    app.state.settings = settings

    @app.get("/")
    async def index(request: Request):
        chats = await services.chats.list_chats()
        return TEMPLATES.TemplateResponse(
            "index.html",
            {
                "request": request,
                "chats": chats,
            },
        )

    @app.get("/chats/{chat_id}")
    async def chat_detail(chat_id: int, request: Request):
        try:
            chat_settings = await services.chats.get_settings(chat_id)
        except ValueError as exc:  # pragma: no cover - defensive
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        chat_row = None
        for chat in await services.chats.list_chats():
            if chat.id == chat_id:
                chat_row = chat
                break
        return TEMPLATES.TemplateResponse(
            "chat_detail.html",
            {
                "request": request,
                "chat_id": chat_id,
                "chat": chat_row,
                "settings": chat_settings,
                "saved": request.query_params.get("saved") == "1",
            },
        )

    @app.post("/chats/{chat_id}")
    async def update_chat(
        chat_id: int,
        request: Request,
        subscription_tier: str = Form("free"),
        flood_message_limit: int = Form(...),
        flood_interval_seconds: int = Form(...),
        flood_punishment: str = Form("mute"),
        stop_words_enabled: bool = Form(False),
        captcha_enabled: bool = Form(False),
        silent_enabled: bool = Form(False),
        welcome_text: str = Form(""),
        reports_enabled: bool = Form(False),
        reports_chat_id: str = Form(""),
    ):
        try:
            chat_settings = await services.chats.get_settings(chat_id)
        except ValueError as exc:  # pragma: no cover - defensive
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        chat_settings.subscription.tier = subscription_tier
        chat_settings.flood.message_limit = max(1, flood_message_limit)
        chat_settings.flood.interval_seconds = max(1, flood_interval_seconds)
        chat_settings.flood.punishment = flood_punishment  # type: ignore[assignment]
        chat_settings.stop_words.enabled = stop_words_enabled
        chat_settings.captcha.enabled = captcha_enabled
        chat_settings.silent_mode.enabled = silent_enabled
        chat_settings.welcome.text = welcome_text
        chat_settings.reports.enabled = reports_enabled
        if reports_chat_id:
            try:
                chat_settings.reports.destination_chat_id = int(reports_chat_id)
            except ValueError:
                chat_settings.reports.destination_chat_id = None
        else:
            chat_settings.reports.destination_chat_id = None

        await services.chats.save_settings(chat_id, chat_settings)

        url = request.url_for("chat_detail", chat_id=chat_id) + "?saved=1"
        return RedirectResponse(url=url, status_code=303)

    return app
