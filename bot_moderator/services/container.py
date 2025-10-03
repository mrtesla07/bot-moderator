"""Dependency container for convenient handler wiring."""

from __future__ import annotations

from dataclasses import dataclass

from aiogram import Bot

from .admin_service import AdminService
from .chat_service import ChatService
from .moderation_service import ModerationService
from .user_service import UserService
from .captcha_service import CaptchaService


@dataclass
class ServiceContainer:
    bot: Bot
    chats: ChatService
    users: UserService
    admins: AdminService
    moderation: ModerationService
    captcha: CaptchaService
