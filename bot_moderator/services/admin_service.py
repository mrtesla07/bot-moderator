"""Helpers for working with chat administrators."""

from __future__ import annotations

import time
from dataclasses import dataclass

from aiogram import Bot
from aiogram.types import ChatMemberAdministrator, ChatMemberOwner


@dataclass
class AdminCacheEntry:
    members: set[int]
    expires_at: float


class AdminService:
    def __init__(self, bot: Bot, ttl: int = 120) -> None:
        self._bot = bot
        self._ttl = ttl
        self._cache: dict[int, AdminCacheEntry] = {}

    async def get_admin_ids(self, chat_id: int) -> set[int]:
        now = time.time()
        cached = self._cache.get(chat_id)
        if cached and cached.expires_at > now:
            return cached.members
        admins = await self._bot.get_chat_administrators(chat_id)
        admin_ids = {
            member.user.id
            for member in admins
            if isinstance(member, (ChatMemberAdministrator, ChatMemberOwner))
        }
        self._cache[chat_id] = AdminCacheEntry(members=admin_ids, expires_at=now + self._ttl)
        return admin_ids

    async def is_admin(self, chat_id: int, user_id: int) -> bool:
        return user_id in await self.get_admin_ids(chat_id)
