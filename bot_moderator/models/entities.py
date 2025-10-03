"""Database models used by the moderator bot."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, SQLModel

from .settings import ChatSettings, DEFAULT_SETTINGS


class Chat(SQLModel, table=True):
    __tablename__ = "chats"

    id: int = Field(primary_key=True)
    title: str | None = Field(default=None)
    username: str | None = Field(default=None)
    settings: dict = Field(default_factory=lambda: DEFAULT_SETTINGS.model_dump(), sa_column=Column(JSON))
    language: str = Field(default="ru")
    timezone: str = Field(default="Europe/Moscow")
    subscription_tier: str = Field(default="free")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class UserState(SQLModel, table=True):
    __tablename__ = "user_states"
    __table_args__ = (UniqueConstraint("chat_id", "user_id", name="uq_user_chat"),)

    id: int | None = Field(default=None, primary_key=True)
    chat_id: int = Field(index=True)
    user_id: int = Field(index=True)
    warnings: int = Field(default=0)
    reputation: int = Field(default=0)
    trust_level: str = Field(default="default")
    is_whitelisted: bool = Field(default=False)
    is_trusted: bool = Field(default=False)
    last_message_at: datetime | None = Field(default=None)
    flood_counter: int = Field(default=0)
    extra: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class BanRecord(SQLModel, table=True):
    __tablename__ = "ban_records"

    id: int | None = Field(default=None, primary_key=True)
    chat_id: int = Field(index=True)
    user_id: int = Field(index=True)
    reason: str | None = Field(default=None)
    issued_by: int | None = Field(default=None)
    expires_at: datetime | None = Field(default=None)
    shared_with_network: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ActionLog(SQLModel, table=True):
    __tablename__ = "action_logs"

    id: int | None = Field(default=None, primary_key=True)
    chat_id: int = Field(index=True)
    user_id: int | None = Field(default=None, index=True)
    action: str = Field()
    payload: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)


class PendingCaptcha(SQLModel, table=True):
    __tablename__ = "pending_captcha"
    __table_args__ = (UniqueConstraint("chat_id", "user_id", name="uq_captcha"),)

    id: int | None = Field(default=None, primary_key=True)
    chat_id: int = Field(index=True)
    user_id: int = Field(index=True)
    correct_answer: str = Field()
    attempts: int = Field(default=0)
    expires_at: datetime = Field()
    created_at: datetime = Field(default_factory=datetime.utcnow)


class JoinRequest(SQLModel, table=True):
    __tablename__ = "join_requests"
    __table_args__ = (UniqueConstraint("chat_id", "user_id", name="uq_join_request"),)

    id: int | None = Field(default=None, primary_key=True)
    chat_id: int = Field(index=True)
    user_id: int = Field(index=True)
    questionnaire_answers: dict = Field(default_factory=dict, sa_column=Column(JSON))
    status: str = Field(default="pending")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime | None = Field(default=None)


def settings_from_row(row: Chat) -> ChatSettings:
    """Restore :class:`ChatSettings` instance from a database row."""

    data = DEFAULT_SETTINGS.model_dump()
    data.update(row.settings or {})
    return ChatSettings.model_validate(data)
