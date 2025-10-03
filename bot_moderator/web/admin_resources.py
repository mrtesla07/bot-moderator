"""FastAPI-Admin resource declarations."""

from __future__ import annotations

from fastapi_admin.resources import Field, Model
from fastapi_admin.widgets import displays, filters, inputs

from . import admin_models


class ChatResource(Model):
    label = "Чаты"
    icon = "fas fa-comments"
    model = admin_models.Chat
    filters = [
        filters.Search(name="title", label="Название"),
        filters.Search(name="username", label="Username"),
        filters.Search(name="subscription_tier", label="Тариф", search_mode="equals"),
    ]
    fields = [
        "id",
        "title",
        "username",
        "subscription_tier",
        Field(
            name="settings",
            label="Настройки",
            display=displays.Json(),
            input_=inputs.Json(),
        ),
        "language",
        "timezone",
        "created_at",
        "updated_at",
    ]


class UserStateResource(Model):
    label = "Состояния пользователей"
    icon = "fas fa-users"
    model = admin_models.UserState
    filters = [
        filters.Search(name="chat_id", label="Chat ID", search_mode="equals"),
        filters.Search(name="user_id", label="User ID", search_mode="equals"),
    ]
    fields = [
        "id",
        "chat_id",
        "user_id",
        "warnings",
        "reputation",
        "trust_level",
        "is_whitelisted",
        "is_trusted",
        "last_message_at",
        "flood_counter",
        Field(
            name="extra",
            label="Дополнительные данные",
            display=displays.Json(),
            input_=inputs.Json(null=True),
        ),
        "created_at",
        "updated_at",
    ]


class BanRecordResource(Model):
    label = "Баны"
    icon = "fas fa-ban"
    model = admin_models.BanRecord
    filters = [
        filters.Search(name="chat_id", label="Chat ID", search_mode="equals"),
        filters.Search(name="user_id", label="User ID", search_mode="equals"),
    ]
    fields = [
        "id",
        "chat_id",
        "user_id",
        "reason",
        "issued_by",
        "expires_at",
        "shared_with_network",
        "created_at",
    ]


class ActionLogResource(Model):
    label = "Журнал действий"
    icon = "fas fa-clipboard-list"
    model = admin_models.ActionLog
    filters = [
        filters.Search(name="chat_id", label="Chat ID", search_mode="equals"),
        filters.Search(name="user_id", label="User ID", search_mode="equals"),
        filters.Search(name="action", label="Действие"),
    ]
    fields = [
        "id",
        "chat_id",
        "user_id",
        "action",
        Field(
            name="payload",
            label="Данные",
            display=displays.Json(),
            input_=inputs.Json(null=True),
        ),
        "created_at",
    ]


class PendingCaptchaResource(Model):
    label = "Капча"
    icon = "fas fa-shield-alt"
    model = admin_models.PendingCaptcha
    filters = [
        filters.Search(name="chat_id", label="Chat ID", search_mode="equals"),
        filters.Search(name="user_id", label="User ID", search_mode="equals"),
    ]
    fields = [
        "id",
        "chat_id",
        "user_id",
        "correct_answer",
        "attempts",
        "expires_at",
        "created_at",
    ]


class JoinRequestResource(Model):
    label = "Заявки"
    icon = "fas fa-door-open"
    model = admin_models.JoinRequest
    filters = [
        filters.Search(name="chat_id", label="Chat ID", search_mode="equals"),
        filters.Search(name="user_id", label="User ID", search_mode="equals"),
        filters.Search(name="status", label="Статус", search_mode="equals"),
    ]
    fields = [
        "id",
        "chat_id",
        "user_id",
        Field(
            name="questionnaire_answers",
            label="Анкета",
            display=displays.Json(),
            input_=inputs.Json(null=True),
        ),
        "status",
        "created_at",
        "expires_at",
    ]


class AdminUserResource(Model):
    label = "Администраторы"
    icon = "fas fa-user-shield"
    model = admin_models.AdminUser
    filters = [filters.Search(name="username", label="Логин")]
    fields = [
        "id",
        "username",
        Field(
            name="password",
            label="Пароль",
            display=displays.InputOnly(),
            input_=inputs.Password(),
        ),
        "is_active",
        "is_superuser",
    ]
