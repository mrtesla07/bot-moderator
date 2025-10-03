"""Event handlers for moderation pipeline."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from aiogram import Router
from aiogram.enums import ContentType
from aiogram.filters import Command
from aiogram.types import ChatJoinRequest, ChatMemberUpdated, ChatPermissions, InlineKeyboardButton, InlineKeyboardMarkup, Message

from ..core.actions import BanUser, DeleteMessage, LiftRestrictions, LogAction, MuteUser, RestrictUser, SendMessage, WarnUser
from ..core.result import ModerationResult
from ..services.container import ServiceContainer

router = Router(name="moderation")


def _get_services(message: Message) -> ServiceContainer:
    services: ServiceContainer = message.bot["services"]
    return services


def _should_silence(settings, rule: str) -> bool:
    silent = settings.silent_mode
    if not silent.enabled:
        return False
    return any(rule.startswith(prefix) for prefix in silent.suppress_events)


async def apply_actions(message: Message, result: ModerationResult, settings) -> None:
    if not result.actions:
        return
    bot = message.bot
    chat_id = message.chat.id
    for action in result.actions:
        if isinstance(action, DeleteMessage):
            try:
                await bot.delete_message(chat_id, action.payload["message_id"])
            except Exception as exc:  # noqa: BLE001
                logging.debug("delete_message failed", exc_info=exc)
        elif isinstance(action, MuteUser):
            until = datetime.utcnow() + timedelta(seconds=action.payload["until_seconds"])
            perms = ChatPermissions(can_send_messages=False, can_send_other_messages=False, can_add_web_page_previews=False, can_send_audios=False, can_send_documents=False, can_send_photos=False, can_send_videos=False, can_send_video_notes=False, can_send_voice_notes=False)
            try:
                await bot.restrict_chat_member(
                    chat_id=chat_id,
                    user_id=action.payload["user_id"],
                    permissions=perms,
                    until_date=until,
                )
            except Exception as exc:  # noqa: BLE001
                logging.warning("mute failed", exc_info=exc)
        elif isinstance(action, BanUser):
            until = None
            seconds = action.payload.get("until_seconds")
            if seconds:
                until = datetime.utcnow() + timedelta(seconds=seconds)
            try:
                await bot.ban_chat_member(
                    chat_id=chat_id,
                    user_id=action.payload["user_id"],
                    until_date=until,
                    revoke_messages=bool(action.payload.get("delete_history_days")),
                )
            except Exception as exc:  # noqa: BLE001
                logging.error("ban failed", exc_info=exc)
        elif isinstance(action, WarnUser):
            if _should_silence(settings, "warning"):
                continue
            text = f"⚠️ <a href=\"tg://user?id={action.payload['user_id']}\">Пользователь</a>: {action.payload['reason']}"
            await bot.send_message(chat_id=chat_id, text=text)
        elif isinstance(action, RestrictUser):
            perms_dict = action.payload.get("permissions", {})
            seconds = action.payload.get("until_seconds")
            until = datetime.utcnow() + timedelta(seconds=seconds) if seconds else None
            permissions = ChatPermissions(**perms_dict)
            try:
                await bot.restrict_chat_member(
                    chat_id=chat_id,
                    user_id=action.payload["user_id"],
                    permissions=permissions,
                    until_date=until,
                )
            except Exception as exc:  # noqa: BLE001
                logging.warning("restrict failed", exc_info=exc)
        elif isinstance(action, LiftRestrictions):
            try:
                await bot.restrict_chat_member(
                    chat_id=chat_id,
                    user_id=action.payload["user_id"],
                    permissions=ChatPermissions(
                        can_send_messages=True,
                        can_send_media_messages=True,
                        can_send_polls=True,
                        can_send_other_messages=True,
                        can_add_web_page_previews=True,
                        can_invite_users=True,
                    ),
                )
            except Exception as exc:  # noqa: BLE001
                logging.warning("lift restrictions failed", exc_info=exc)
        elif isinstance(action, SendMessage):
            if _should_silence(settings, "service"):
                continue
            keyboard = action.payload.get("keyboard")
            reply_markup = None
            if keyboard:
                rows = []
                for row in keyboard:
                    buttons = [InlineKeyboardButton(text=label, callback_data=data) for label, data in row]
                    rows.append(buttons)
                reply_markup = InlineKeyboardMarkup(inline_keyboard=rows)
            await bot.send_message(
                chat_id=chat_id,
                text=action.payload["text"],
                reply_to_message_id=action.payload.get("reply_to"),
                reply_markup=reply_markup,
            )
        elif isinstance(action, LogAction):
            getattr(logging, action.payload["level"].lower(), logging.info)(
                action.payload["message"], extra=action.payload.get("extra")
            )
        else:
            logging.debug("Unhandled action %s", action)

    if settings.reports.enabled and settings.reports.destination_chat_id and result.triggered_rules:
        summary = "; ".join(result.triggered_rules)
        await bot.send_message(settings.reports.destination_chat_id, f"Сработали правила: {summary}")


@router.message(Command("ping"))
async def handle_ping(message: Message) -> None:
    await message.answer("bot-moderator на связи ✅")


@router.message(lambda msg: bool(msg.new_chat_members))
async def handle_new_members(message: Message) -> None:
    services = _get_services(message)
    settings = await services.moderation.get_settings(message)
    result = await services.moderation.process_service_message(message)
    await apply_actions(message, result, settings)


@router.message(lambda msg: msg.left_chat_member is not None)
async def handle_left_member(message: Message) -> None:
    services = _get_services(message)
    settings = await services.moderation.get_settings(message)
    result = await services.moderation.process_service_message(message)
    await apply_actions(message, result, settings)


@router.message(lambda msg: msg.content_type in {
    ContentType.TEXT,
    ContentType.ANIMATION,
    ContentType.DOCUMENT,
    ContentType.PHOTO,
    ContentType.VIDEO,
    ContentType.VOICE,
    ContentType.VIDEO_NOTE,
})
async def handle_message(message: Message) -> None:
    services = _get_services(message)
    settings = await services.moderation.get_settings(message)
    result = await services.moderation.process_message(message)
    await apply_actions(message, result, settings)


@router.chat_join_request()
async def handle_join_request(request: ChatJoinRequest) -> None:
    services: ServiceContainer = request.bot["services"]
    result = await services.moderation.handle_join_request(request)
    for action in result.actions:
        if isinstance(action, SendMessage):
            await request.bot.send_message(request.from_user.id, action.payload["text"])


@router.chat_member()
async def handle_chat_member_update(update: ChatMemberUpdated) -> None:
    bot = update.bot
    services: ServiceContainer = bot["services"]
    result = await services.moderation.process_chat_member_update(update)
    for action in result.actions:
        if isinstance(action, LogAction):
            getattr(logging, action.payload["level"].lower(), logging.info)(action.payload["message"], extra=action.payload.get("extra"))
