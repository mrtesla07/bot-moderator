"""Manage per-user moderation state."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, select, update

from ..data.database import Database
from ..models.entities import UserState


class UserService:
    """CRUD interface for user moderation data."""

    def __init__(self, database: Database) -> None:
        self._db = database

    async def get_state(self, chat_id: int, user_id: int) -> UserState:
        async with self._db.session() as session:
            result = await session.execute(
                select(UserState).where(UserState.chat_id == chat_id, UserState.user_id == user_id)
            )
            state = result.scalar_one_or_none()
            if state is None:
                state = UserState(chat_id=chat_id, user_id=user_id)
                session.add(state)
                await session.commit()
                await session.refresh(state)
            return state

    async def add_warning(self, chat_id: int, user_id: int) -> int:
        state = await self.get_state(chat_id, user_id)
        async with self._db.session() as session:
            new_value = state.warnings + 1
            await session.execute(
                update(UserState)
                .where(UserState.id == state.id)
                .values(warnings=new_value, updated_at=datetime.utcnow())
            )
            await session.commit()
        return new_value

    async def reset_warnings(self, chat_id: int, user_id: int) -> None:
        state = await self.get_state(chat_id, user_id)
        async with self._db.session() as session:
            await session.execute(
                update(UserState)
                .where(UserState.id == state.id)
                .values(warnings=0, updated_at=datetime.utcnow())
            )
            await session.commit()

    async def adjust_reputation(self, chat_id: int, user_id: int, delta: int) -> int:
        state = await self.get_state(chat_id, user_id)
        new_value = state.reputation + delta
        async with self._db.session() as session:
            await session.execute(
                update(UserState)
                .where(UserState.id == state.id)
                .values(reputation=new_value, updated_at=datetime.utcnow())
            )
            await session.commit()
        return new_value

    async def set_trust(self, chat_id: int, user_id: int, trusted: bool) -> None:
        state = await self.get_state(chat_id, user_id)
        async with self._db.session() as session:
            await session.execute(
                update(UserState)
                .where(UserState.id == state.id)
                .values(is_trusted=trusted, updated_at=datetime.utcnow())
            )
            await session.commit()

    async def set_whitelist(self, chat_id: int, user_id: int, whitelisted: bool) -> None:
        state = await self.get_state(chat_id, user_id)
        async with self._db.session() as session:
            await session.execute(
                update(UserState)
                .where(UserState.id == state.id)
                .values(is_whitelisted=whitelisted, updated_at=datetime.utcnow())
            )
            await session.commit()

    async def update_extra(self, chat_id: int, user_id: int, **fields) -> None:
        state = await self.get_state(chat_id, user_id)
        extra = {**state.extra, **fields}
        async with self._db.session() as session:
            await session.execute(
                update(UserState)
                .where(UserState.id == state.id)
                .values(extra=extra, updated_at=datetime.utcnow())
            )
            await session.commit()

    async def list_states(self, chat_id: int) -> list[UserState]:
        async with self._db.session() as session:
            result = await session.execute(
                select(UserState).where(UserState.chat_id == chat_id)
            )
            return list(result.scalars())

    async def delete_states(self, chat_id: int, user_ids: list[int]) -> int:
        if not user_ids:
            return 0
        async with self._db.session() as session:
            result = await session.execute(
                select(UserState.id).where(UserState.chat_id == chat_id, UserState.user_id.in_(user_ids))
            )
            ids = [row[0] for row in result]
            if not ids:
                return 0
            await session.execute(
                delete(UserState).where(UserState.id.in_(ids))
            )
            await session.commit()
            return len(ids)

    async def list_whitelisted(self, chat_id: int) -> list[UserState]:
        async with self._db.session() as session:
            result = await session.execute(
                select(UserState).where(UserState.chat_id == chat_id, UserState.is_whitelisted.is_(True))
            )
            return list(result.scalars())

