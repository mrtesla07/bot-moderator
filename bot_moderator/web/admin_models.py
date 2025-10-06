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


    def _ensure_section(self, path: tuple[str, ...]) -> dict:
        node = self.settings
        for key in path:
            node = node.setdefault(key, {})
        return node

    @staticmethod
    def _parse_optional_int(value: int | str | None) -> int | None:
        if value in (None, '', 'None'):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @property
    def command_menu_hidden(self) -> bool:
        return self.settings.get("command_menu", {}).get("hidden", False)

    @command_menu_hidden.setter
    def command_menu_hidden(self, value: bool) -> None:
        section = self._ensure_section(("command_menu",))
        section["hidden"] = bool(value)

    @property
    def reports_enabled(self) -> bool:
        return self.settings.get("reports", {}).get("enabled", True)

    @reports_enabled.setter
    def reports_enabled(self, value: bool) -> None:
        section = self._ensure_section(("reports",))
        section["enabled"] = bool(value)

    @property
    def reports_notify_admins(self) -> bool:
        return self.settings.get("reports", {}).get("notify_admins", False)

    @reports_notify_admins.setter
    def reports_notify_admins(self, value: bool) -> None:
        section = self._ensure_section(("reports",))
        section["notify_admins"] = bool(value)

    @property
    def reports_destination_chat_id(self) -> int | None:
        return self.settings.get("reports", {}).get("destination_chat_id")

    @reports_destination_chat_id.setter
    def reports_destination_chat_id(self, value: int | None) -> None:
        section = self._ensure_section(("reports",))
        section["destination_chat_id"] = self._parse_optional_int(value)

    @property
    def reports_secondary_chat_id(self) -> int | None:
        return self.settings.get("reports", {}).get("secondary_chat_id")

    @reports_secondary_chat_id.setter
    def reports_secondary_chat_id(self, value: int | None) -> None:
        section = self._ensure_section(("reports",))
        section["secondary_chat_id"] = self._parse_optional_int(value)

    @property
    def reports_include_rules(self) -> str:
        rules = self.settings.get("reports", {}).get("include_rules", [])
        return ", ".join(rules)

    @reports_include_rules.setter
    def reports_include_rules(self, value: str) -> None:
        section = self._ensure_section(("reports",))
        rules = [item.strip() for item in (value or "").split(",") if item.strip()]
        section["include_rules"] = rules

    @property
    def reports_exclude_rules(self) -> str:
        rules = self.settings.get("reports", {}).get("exclude_rules", [])
        return ", ".join(rules)

    @reports_exclude_rules.setter
    def reports_exclude_rules(self, value: str) -> None:
        section = self._ensure_section(("reports",))
        rules = [item.strip() for item in (value or "").split(",") if item.strip()]
        section["exclude_rules"] = rules

    @property
    def questionnaire_enabled(self) -> bool:
        return self.settings.get("questionnaire", {}).get("enabled", False)

    @questionnaire_enabled.setter
    def questionnaire_enabled(self, value: bool) -> None:
        section = self._ensure_section(("questionnaire",))
        section["enabled"] = bool(value)

    @property
    def questionnaire_questions(self) -> str:
        questions = self.settings.get("questionnaire", {}).get("questions", [])
        return "
".join(questions)

    @questionnaire_questions.setter
    def questionnaire_questions(self, value: str) -> None:
        section = self._ensure_section(("questionnaire",))
        questions = [line.strip() for line in (value or "").splitlines() if line.strip()]
        section["questions"] = questions

    @property
    def questionnaire_auto_approve_seconds(self) -> int:
        return self.settings.get("questionnaire", {}).get("auto_approve_seconds") or 0

    @questionnaire_auto_approve_seconds.setter
    def questionnaire_auto_approve_seconds(self, value: int) -> None:
        section = self._ensure_section(("questionnaire",))
        seconds = int(value)
        seconds = self._parse_optional_int(value) or 0
        section["auto_approve_seconds"] = max(seconds, 0)

    @property
    def questionnaire_auto_reject_seconds(self) -> int:
        return self.settings.get("questionnaire", {}).get("auto_reject_seconds", 180)

    @questionnaire_auto_reject_seconds.setter
    def questionnaire_auto_reject_seconds(self, value: int) -> None:
        section = self._ensure_section(("questionnaire",))
        seconds = self._parse_optional_int(value) or 0
        section["auto_reject_seconds"] = max(seconds, 0)

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

