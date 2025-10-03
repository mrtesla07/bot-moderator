"""Application wiring and bootstrap helpers."""

from __future__ import annotations

import asyncio

from aiogram import Bot, Dispatcher
import uvicorn

from ..config import Settings
from ..data.database import Database
from ..handlers import register_handlers
from ..services.admin_service import AdminService
from ..services.chat_service import ChatService
from ..services.container import ServiceContainer
from ..services.captcha_service import CaptchaService
from ..services.moderation_service import ModerationService
from ..services.user_service import UserService
from ..web.server import create_app


class Application:
    def __init__(self, settings: Settings, dispatcher: Dispatcher, bot: Bot) -> None:
        self.settings = settings
        self.dispatcher = dispatcher
        self.bot = bot
        self.database = Database(url=settings.database_url, storage_dir=settings.storage_dir)
        self.services: ServiceContainer | None = None
        self.web_app = None
        self._web_server: uvicorn.Server | None = None
        self._web_task: asyncio.Task | None = None

    async def initialize(self) -> None:
        await self.database.connect()

        chat_service = ChatService(self.database)
        user_service = UserService(self.database)
        admin_service = AdminService(self.bot)
        captcha_service = CaptchaService(self.database)
        moderation_service = ModerationService(
            bot=self.bot,
            chat_service=chat_service,
            user_service=user_service,
            admin_service=admin_service,
            captcha_service=captcha_service,
        )
        self.services = ServiceContainer(
            bot=self.bot,
            chats=chat_service,
            users=user_service,
            admins=admin_service,
            moderation=moderation_service,
            captcha=captcha_service,
        )

        self.dispatcher["settings"] = self.settings
        self.dispatcher["services"] = self.services
        self.bot["settings"] = self.settings
        self.bot["services"] = self.services

        register_handlers(self.dispatcher)

        if self.settings.web_enabled:
            self.web_app = create_app(self.settings)
            config = uvicorn.Config(
                self.web_app,
                host=self.settings.web_host,
                port=self.settings.web_port,
                log_level=self.settings.log_level.lower(),
                loop="asyncio",
            )
            self._web_server = uvicorn.Server(config)
            self._web_task = asyncio.create_task(self._web_server.serve())

    async def shutdown(self) -> None:
        if self._web_server is not None:
            self._web_server.should_exit = True
        if self._web_task is not None:
            await self._web_task
            self._web_task = None
        self._web_server = None
        await self.database.disconnect()

