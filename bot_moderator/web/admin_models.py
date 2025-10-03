"""Tortoise ORM models used by the FastAPI-Admin interface."""

from __future__ import annotations

from typing import Any

from fastapi_admin.models import AbstractAdmin
from tortoise import fields
from tortoise.models import Model

from ..models.settings import DEFAULT_SETTINGS


def _default_settings() -> dict[str, Any]:
    """Return a fresh copy of default chat settings."""

    return DEFAULT_SETTINGS.model_dump()


class Chat(Model):
    id = fields.IntField(pk=True)
    title = fields.CharField(max_length=255, null=True)
    username = fields.CharField(max_length=255, null=True)
    settings = fields.JSONField(default=_default_settings)
    language = fields.CharField(max_length=32, default="ru")
    timezone = fields.CharField(max_length=64, default="Europe/Moscow")
    subscription_tier = fields.CharField(max_length=32, default="free")
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "chats"


class UserState(Model):
    id = fields.IntField(pk=True)
    chat_id = fields.IntField(index=True)
    user_id = fields.IntField(index=True)
    warnings = fields.IntField(default=0)
    reputation = fields.IntField(default=0)
    trust_level = fields.CharField(max_length=32, default="default")
    is_whitelisted = fields.BooleanField(default=False)
    is_trusted = fields.BooleanField(default=False)
    last_message_at = fields.DatetimeField(null=True)
    flood_counter = fields.IntField(default=0)
    extra = fields.JSONField(default=dict)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "user_states"
        unique_together = (("chat_id", "user_id"),)


class BanRecord(Model):
    id = fields.IntField(pk=True)
    chat_id = fields.IntField(index=True)
    user_id = fields.IntField(index=True)
    reason = fields.CharField(max_length=255, null=True)
    issued_by = fields.IntField(null=True)
    expires_at = fields.DatetimeField(null=True)
    shared_with_network = fields.BooleanField(default=False)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "ban_records"


class ActionLog(Model):
    id = fields.IntField(pk=True)
    chat_id = fields.IntField(index=True)
    user_id = fields.IntField(null=True, index=True)
    action = fields.CharField(max_length=128)
    payload = fields.JSONField(default=dict)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "action_logs"


class PendingCaptcha(Model):
    id = fields.IntField(pk=True)
    chat_id = fields.IntField(index=True)
    user_id = fields.IntField(index=True)
    correct_answer = fields.CharField(max_length=100)
    attempts = fields.IntField(default=0)
    expires_at = fields.DatetimeField()
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "pending_captcha"
        unique_together = (("chat_id", "user_id"),)


class JoinRequest(Model):
    id = fields.IntField(pk=True)
    chat_id = fields.IntField(index=True)
    user_id = fields.IntField(index=True)
    questionnaire_answers = fields.JSONField(default=dict)
    status = fields.CharField(max_length=32, default="pending")
    created_at = fields.DatetimeField(auto_now_add=True)
    expires_at = fields.DatetimeField(null=True)

    class Meta:
        table = "join_requests"
        unique_together = (("chat_id", "user_id"),)


class AdminUser(AbstractAdmin):
    id = fields.IntField(pk=True)
    is_active = fields.BooleanField(default=True)
    is_superuser = fields.BooleanField(default=True)

    class Meta:
        table = "admin_users"

