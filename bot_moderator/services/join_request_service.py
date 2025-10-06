
"""Persistence helpers for join requests and questionnaires."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy import delete, select

from ..data.database import Database
from ..models.entities import JoinRequest


class JoinRequestService:
    """CRUD operations around join requests and questionnaire answers."""

    def __init__(self, database: Database) -> None:
        self._db = database

    async def upsert_request(
        self,
        *,
        chat_id: int,
        user_id: int,
        questions: Sequence[str],
        expires_at: datetime | None,
    ) -> JoinRequest:
        payload = {
            "questions": list(questions),
            "answers": [],
        }
        now = datetime.now(timezone.utc)
        async with self._db.session() as session:
            result = await session.execute(
                select(JoinRequest).where(JoinRequest.chat_id == chat_id, JoinRequest.user_id == user_id)
            )
            request = result.scalar_one_or_none()
            if request is None:
                request = JoinRequest(
                    chat_id=chat_id,
                    user_id=user_id,
                    questionnaire_answers=payload,
                    status="pending",
                    created_at=now,
                    expires_at=expires_at,
                )
                session.add(request)
            else:
                request.questionnaire_answers = payload
                request.status = "pending"
                request.created_at = now
                request.expires_at = expires_at
            await session.commit()
            await session.refresh(request)
            return request

    async def store_answers(self, chat_id: int, user_id: int, answers: Sequence[str]) -> JoinRequest | None:
        async with self._db.session() as session:
            result = await session.execute(
                select(JoinRequest).where(JoinRequest.chat_id == chat_id, JoinRequest.user_id == user_id)
            )
            request = result.scalar_one_or_none()
            if request is None:
                return None
            payload = dict(request.questionnaire_answers or {})
            payload["answers"] = list(answers)
            payload["answered_at"] = datetime.now(timezone.utc).isoformat()
            request.questionnaire_answers = payload
            session.add(request)
            await session.commit()
            await session.refresh(request)
            return request

    async def set_status(self, chat_id: int, user_id: int, status: str) -> None:
        async with self._db.session() as session:
            result = await session.execute(
                select(JoinRequest).where(JoinRequest.chat_id == chat_id, JoinRequest.user_id == user_id)
            )
            request = result.scalar_one_or_none()
            if request is None:
                return
            request.status = status
            if status != "pending":
                request.expires_at = None
            session.add(request)
            await session.commit()

    async def get_request(self, chat_id: int, user_id: int) -> JoinRequest | None:
        async with self._db.session() as session:
            result = await session.execute(
                select(JoinRequest).where(JoinRequest.chat_id == chat_id, JoinRequest.user_id == user_id)
            )
            return result.scalar_one_or_none()

    async def list_pending(self, chat_id: int) -> list[JoinRequest]:
        async with self._db.session() as session:
            result = await session.execute(
                select(JoinRequest)
                .where(JoinRequest.chat_id == chat_id, JoinRequest.status == "pending")
                .order_by(JoinRequest.created_at.asc())
            )
            return list(result.scalars())

    async def list_pending_for_user(self, user_id: int) -> list[JoinRequest]:
        async with self._db.session() as session:
            result = await session.execute(
                select(JoinRequest)
                .where(JoinRequest.user_id == user_id, JoinRequest.status == "pending")
                .order_by(JoinRequest.created_at.desc())
            )
            return list(result.scalars())

    async def delete(self, chat_id: int, user_id: int) -> None:
        async with self._db.session() as session:
            await session.execute(
                delete(JoinRequest).where(JoinRequest.chat_id == chat_id, JoinRequest.user_id == user_id)
            )
            await session.commit()
