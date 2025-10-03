"""Create and validate onboarding captcha challenges."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import delete, select

from ..data.database import Database
from ..models.entities import PendingCaptcha


@dataclass(slots=True)
class CaptchaVerification:
    success: bool
    attempts: int
    expired: bool


class CaptchaService:
    def __init__(self, database: Database) -> None:
        self._db = database

    async def create_challenge(self, chat_id: int, user_id: int, kind: str, timeout_seconds: int) -> tuple[str, list[tuple[str, str]]]:
        token = secrets.token_urlsafe(8)
        if kind == "math":
            a, b = secrets.randbelow(9) + 1, secrets.randbelow(9) + 1
            question = f"Сколько будет {a} + {b}?"
            correct = str(a + b)
            options = {correct}
            while len(options) < 4:
                options.add(str(secrets.randbelow(18) + 1))
            buttons = [(option, f"cap|{token}|{option}") for option in sorted(options)]
        else:
            question = "Подтвердите, что вы не бот"
            correct = "human"
            buttons = [
                ("Я человек", f"cap|{token}|human"),
                ("Я бот", f"cap|{token}|bot"),
            ]
        expires_at = datetime.utcnow() + timedelta(seconds=timeout_seconds)
        async with self._db.session() as session:
            await session.execute(
                delete(PendingCaptcha).where(PendingCaptcha.chat_id == chat_id, PendingCaptcha.user_id == user_id)
            )
            record = PendingCaptcha(
                chat_id=chat_id,
                user_id=user_id,
                correct_answer=f"cap|{token}|{correct}",
                attempts=0,
                expires_at=expires_at,
            )
            session.add(record)
            await session.commit()
        return question, buttons

    async def verify(self, chat_id: int, user_id: int, payload: str) -> CaptchaVerification:
        async with self._db.session() as session:
            result = await session.execute(
                select(PendingCaptcha).where(
                    PendingCaptcha.chat_id == chat_id,
                    PendingCaptcha.user_id == user_id,
                )
            )
            record = result.scalar_one_or_none()
            if record is None:
                return CaptchaVerification(success=False, attempts=0, expired=True)
            if record.expires_at < datetime.utcnow():
                await session.delete(record)
                await session.commit()
                return CaptchaVerification(success=False, attempts=record.attempts, expired=True)
            if record.correct_answer == payload:
                attempts = record.attempts
                await session.delete(record)
                await session.commit()
                return CaptchaVerification(success=True, attempts=attempts, expired=False)
            record.attempts += 1
            await session.commit()
            return CaptchaVerification(success=False, attempts=record.attempts, expired=False)

    async def clear(self, chat_id: int, user_id: int) -> None:
        async with self._db.session() as session:
            await session.execute(
                delete(PendingCaptcha).where(
                    PendingCaptcha.chat_id == chat_id,
                    PendingCaptcha.user_id == user_id,
                )
            )
            await session.commit()

    async def pending(self, chat_id: int, user_id: int) -> bool:
        async with self._db.session() as session:
            result = await session.execute(
                select(PendingCaptcha.id).where(
                    PendingCaptcha.chat_id == chat_id,
                    PendingCaptcha.user_id == user_id,
                    PendingCaptcha.expires_at > datetime.utcnow(),
                )
            )
            return result.scalar_one_or_none() is not None
