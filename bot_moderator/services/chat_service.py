"""Persistence layer for chat settings."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select, update
from sqlmodel import SQLModel

from ..data.database import Database
from ..models.entities import Chat, settings_from_row
from ..models.settings import ChatSettings, DEFAULT_SETTINGS


class ChatService:
    """CRUD operations for chats and their settings."""

    def __init__(self, database: Database) -> None:
        self._db = database

    async def ensure_chat(self, chat_id: int, title: str | None, username: str | None) -> ChatSettings:
        """Fetch chat settings or create defaults."""

        async with self._db.session() as session:
            result = await session.execute(select(Chat).where(Chat.id == chat_id))
            row: Chat | None = result.scalar_one_or_none()
            if row is None:
                row = Chat(
                    id=chat_id,
                    title=title,
                    username=username,
                    settings=DEFAULT_SETTINGS.model_dump(),
                )
                session.add(row)
                await session.commit()
                return DEFAULT_SETTINGS.model_copy()
            if title and row.title != title:
                row.title = title
            if username and row.username != username:
                row.username = username
            row.updated_at = datetime.utcnow()
            await session.commit()
            return settings_from_row(row)

    async def get_settings(self, chat_id: int) -> ChatSettings:
        async with self._db.session() as session:
            result = await session.execute(select(Chat).where(Chat.id == chat_id))
            row = result.scalar_one_or_none()
            if row is None:
                raise ValueError(f"Chat {chat_id} is not registered")
            return settings_from_row(row)

    async def save_settings(self, chat_id: int, settings: ChatSettings) -> None:
        data = settings.model_dump()
        async with self._db.session() as session:
            await session.execute(
                update(Chat)
                .where(Chat.id == chat_id)
                .values(settings=data, updated_at=datetime.utcnow(), subscription_tier=settings.subscription.tier)
            )
            await session.commit()

    async def set_subscription(self, chat_id: int, tier: str) -> None:
        async with self._db.session() as session:
            await session.execute(
                update(Chat).where(Chat.id == chat_id).values(subscription_tier=tier, updated_at=datetime.utcnow())
            )
            await session.commit()

    async def list_chats(self) -> list[Chat]:
        async with self._db.session() as session:
            result = await session.execute(select(Chat).order_by(Chat.updated_at.desc()))
            return list(result.scalars())

