"""Application wiring and bootstrap helpers."""

from __future__ import annotations

from aiogram import Bot, Dispatcher

from ..config import Settings
from ..data.database import Database
from ..handlers import register_handlers
from ..services.admin_service import AdminService
from ..services.chat_service import ChatService
from ..services.container import ServiceContainer
from ..services.captcha_service import CaptchaService
from ..services.moderation_service import ModerationService
from ..services.user_service import UserService


class Application:
    def __init__(self, settings: Settings, dispatcher: Dispatcher, bot: Bot) -> None:
        self.settings = settings
        self.dispatcher = dispatcher
        self.bot = bot
        self.database = Database(url=settings.database_url, storage_dir=settings.storage_dir)
        self.services: ServiceContainer | None = None

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

    async def shutdown(self) -> None:
        await self.database.disconnect()
