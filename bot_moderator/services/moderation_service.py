"""Core moderation pipeline implementing major features."""

from __future__ import annotations

import re
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Deque

from aiogram import Bot
from aiogram.enums import ContentType
from aiogram.types import ChatJoinRequest, ChatMemberUpdated, Message

from ..core.actions import (
    BanUser,
    DeleteMessage,
    LiftRestrictions,
    LogAction,
    MuteUser,
    RestrictUser,
    SendMessage,
    WarnUser,
)
from ..core.result import ModerationResult
from ..models.settings import ChatSettings
from ..services.admin_service import AdminService
from ..services.captcha_service import CaptchaService
from ..utils import time as time_utils
from .chat_service import ChatService
from .user_service import UserService

URL_REGEX = re.compile(r"(?P<url>(https?://|www\.)[\w\-._~:/?#\[\]@!$&'()*+,;=%]+)", re.IGNORECASE)
PROFANITY_REGEX = re.compile(r"[^\w]+", re.UNICODE)

JOIN_FILTER_PRESETS = {
    "promo": ["http", "https", "t.me", "vk.com", "instagram", "shop"],
    "casino": ["casino", "bet", "slot", "1xbet"],
    "numbers": ["123", "777", "999", "000"],
}


class ModerationService:
    captcha_service: CaptchaService
    """Moderation detections orchestrator."""

    def __init__(
        self,
        bot: Bot,
        chat_service: ChatService,
        user_service: UserService,
        admin_service: AdminService,
        captcha_service: "CaptchaService",
    ) -> None:
        self.bot = bot
        self.chat_service = chat_service
        self.user_service = user_service
        self.admin_service = admin_service
        self.captcha_service = captcha_service
        self._settings_cache: dict[int, tuple[ChatSettings, float]] = {}
        self._flood_counters: dict[tuple[int, int], Deque[float]] = defaultdict(deque)
        self._raid_windows: dict[int, Deque[float]] = defaultdict(deque)

    async def get_settings(self, message: Message) -> ChatSettings:
        chat = message.chat
        cached = self._settings_cache.get(chat.id)
        now = time.time()
        if cached and now - cached[1] < 60:
            return cached[0]
        settings = await self.chat_service.ensure_chat(chat.id, chat.full_name if hasattr(chat, "full_name") else chat.title, getattr(chat, "username", None))
        self._settings_cache[chat.id] = (settings, now)
        return settings

    async def process_message(self, message: Message) -> ModerationResult:
        result = ModerationResult()
        if message.chat.type not in {"group", "supergroup"}:
            return result
        if not message.from_user or message.from_user.is_bot:
            return result

        settings = await self.get_settings(message)
        is_admin = await self.admin_service.is_admin(message.chat.id, message.from_user.id)
        if is_admin:
            return result

        await self._apply_night_mode(message, settings, result)
        if result.actions:
            return result

        if message.content_type in {ContentType.TEXT, ContentType.ANIMATION, ContentType.STICKER, ContentType.PHOTO, ContentType.VIDEO, ContentType.DOCUMENT, ContentType.VOICE, ContentType.VIDEO_NOTE}:
            await self._apply_flood(message, settings, result)
            await self._apply_stop_words(message, settings, result)
            await self._apply_profanity(message, settings, result)
            await self._apply_link_guard(message, settings, result)
            await self._apply_forward_guard(message, settings, result)
            await self._apply_reputation(message, settings, result)

        return result

    async def process_service_message(self, message: Message) -> ModerationResult:
        result = ModerationResult()
        settings = await self.get_settings(message)
        await self._handle_join_leave(message, settings, result)
        return result

    async def process_chat_member_update(self, update: ChatMemberUpdated) -> ModerationResult:
        result = ModerationResult()
        chat_id = update.chat.id
        settings = await self.chat_service.ensure_chat(chat_id, update.chat.title, getattr(update.chat, "username", None))
        if update.new_chat_member.user and not update.new_chat_member.user.is_bot:
            await self._process_anti_raid(chat_id, update.new_chat_member.user.id, settings, result)
        return result

    async def handle_join_request(self, request: ChatJoinRequest) -> ModerationResult:
        result = ModerationResult()
        settings = await self.chat_service.ensure_chat(request.chat.id, request.chat.title, request.chat.username)
        # Simplified questionnaire check
        if settings.questionnaire.enabled and settings.questionnaire.questions:
            text = "\n".join(f"{idx+1}. {q}" for idx, q in enumerate(settings.questionnaire.questions))
            result.add(
                SendMessage(
                    text=(
                        "Здравствуйте, {name}! Ответьте на вопросы, чтобы получить доступ:\n{questions}".format(
                            name=request.from_user.full_name,
                            questions=text,
                        )
                    )
                ),
                rule="questionnaire",
            )
        return result

    async def _apply_night_mode(self, message: Message, settings: ChatSettings, result: ModerationResult) -> None:
        config = settings.night_mode
        if not config.enabled:
            return
        local_dt = time_utils.to_timezone(message.date, settings.timezone)
        if time_utils.is_time_between(local_dt.time(), config.start, config.end):
            result.add(DeleteMessage(message_id=message.message_id), rule="night_mode")
            if config.action == "mute":
                result.add(MuteUser(user_id=message.from_user.id, until_seconds=3600), rule="night_mode")

    async def _apply_flood(self, message: Message, settings: ChatSettings, result: ModerationResult) -> None:
        config = settings.flood
        if not config.enabled:
            return
        key = (message.chat.id, message.from_user.id)
        window = self._flood_counters[key]
        now = message.date.timestamp()
        window.append(now)
        while window and now - window[0] > config.interval_seconds:
            window.popleft()
        if len(window) <= config.message_limit:
            return
        if config.punishment == "mute":
            result.add(MuteUser(user_id=message.from_user.id, until_seconds=config.mute_minutes * 60), rule="antiflood")
        elif config.punishment == "ban":
            result.add(BanUser(user_id=message.from_user.id), rule="antiflood")
        result.add(DeleteMessage(message_id=message.message_id), rule="antiflood")
        result.add(WarnUser(user_id=message.from_user.id, reason="Flood detected"), rule="antiflood")

    async def _apply_profanity(self, message: Message, settings: ChatSettings, result: ModerationResult) -> None:
        config = settings.profanity
        if not config.enabled or not message.text:
            return
        normalized = message.text.lower()
        hits = [word for word in config.dictionary if word.lower() in normalized]
        if not hits:
            return
        result.add(DeleteMessage(message_id=message.message_id), rule="profanity")
        state_value = await self.user_service.add_warning(message.chat.id, message.from_user.id)
        if state_value >= config.warn_threshold:
            result.add(MuteUser(user_id=message.from_user.id, until_seconds=config.mute_minutes * 60), rule="profanity")

    async def _apply_stop_words(self, message: Message, settings: ChatSettings, result: ModerationResult) -> None:
        config = settings.stop_words
        if not config.enabled or not message.text:
            return
        text_lower = message.text.lower()
        for stop_list in config.lists:
            for word in stop_list.words:
                if word.lower() in text_lower:
                    result.add(DeleteMessage(message_id=message.message_id), rule=f"stop_words:{stop_list.name}")
                    state_value = await self.user_service.add_warning(message.chat.id, message.from_user.id)
                    if state_value >= config.warn_threshold:
                        if stop_list.action == "mute":
                            result.add(MuteUser(user_id=message.from_user.id, until_seconds=stop_list.mute_minutes * 60), rule="stop_words")
                        elif stop_list.action == "ban":
                            result.add(BanUser(user_id=message.from_user.id), rule="stop_words")
                    return

    async def _apply_link_guard(self, message: Message, settings: ChatSettings, result: ModerationResult) -> None:
        config = settings.link_guard
        if not config.enabled:
            return
        text = message.text or message.caption or ""
        if not text:
            return
        links = [match.group("url") for match in URL_REGEX.finditer(text)]
        if not links:
            return
        state = await self.user_service.get_state(message.chat.id, message.from_user.id)
        if settings.link_guard.allow_trusted and (state.is_trusted or state.is_whitelisted):
            return
            if state.is_trusted or state.is_whitelisted:
                return
        for link in links:
            hostname = self._extract_hostname(link)
            if config.block_all and hostname not in config.whitelist_domains:
                result.add(DeleteMessage(message_id=message.message_id), rule="link_guard")
                result.add(WarnUser(user_id=message.from_user.id, reason="Links are not allowed"), rule="link_guard")
                return
            if hostname in config.blacklist_domains and hostname not in config.whitelist_domains:
                result.add(DeleteMessage(message_id=message.message_id), rule="link_guard")
                result.add(WarnUser(user_id=message.from_user.id, reason=f"Link {hostname} is banned"), rule="link_guard")
                return

    async def _apply_forward_guard(self, message: Message, settings: ChatSettings, result: ModerationResult) -> None:
        config = settings.forwards
        if config.allow_external_forwards:
            return
        if not message.forward_from and not message.forward_from_chat:
            return
        allowed = False
        if message.forward_from_chat:
            allowed = message.forward_from_chat.id in config.whitelist_senders
        if message.forward_from:
            allowed = allowed or message.forward_from.id in config.whitelist_senders
        if not allowed:
            result.add(DeleteMessage(message_id=message.message_id), rule="forward_guard")
            result.add(WarnUser(user_id=message.from_user.id, reason="Forwarding is disabled"), rule="forward_guard")

    async def _apply_reputation(self, message: Message, settings: ChatSettings, result: ModerationResult) -> None:
        config = settings.reputation
        if not config.enabled or not message.text:
            return
        text = message.text.strip().lower()
        target = message.reply_to_message
        if not target or not target.from_user or target.from_user.is_bot:
            return
        if text == config.upvote_command.lower():
            new_value = await self.user_service.adjust_reputation(message.chat.id, target.from_user.id, 1)
            result.add(SendMessage(text=f"Репутация пользователя {target.from_user.full_name}: {new_value}"), rule="reputation")
        elif text == config.downvote_command.lower():
            new_value = await self.user_service.adjust_reputation(message.chat.id, target.from_user.id, -1)
            result.add(SendMessage(text=f"Репутация пользователя {target.from_user.full_name}: {new_value}"), rule="reputation")

    def _extract_hostname(self, url: str) -> str:
        cleaned = url.lower()
        for prefix in ("http://", "https://"):
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix) :]
        return cleaned.split("/")[0].split(":")[0]

    async def _handle_join_leave(self, message: Message, settings: ChatSettings, result: ModerationResult) -> None:
        if message.new_chat_members:
            for user in message.new_chat_members:
                await self._process_new_member(message, user.id, settings, result)
        if message.left_chat_member:
            if settings.system_messages.delete_leave:
                result.add(DeleteMessage(message_id=message.message_id), rule="system_leave")

    async def _apply_join_filter(self, message: Message, member, settings: ChatSettings, result: ModerationResult) -> bool:
        config = settings.join_filter
        if not config.enabled or not member:
            return False
        combined = set(word.lower() for word in config.name_stopwords)
        for preset in config.presets:
            combined.update(word.lower() for word in JOIN_FILTER_PRESETS.get(preset, []))
        name = (member.full_name or "").lower()
        username = (member.username or "").lower()
        if config.close_chat:
            result.add(BanUser(user_id=member.id), rule="join_closed")
            result.add(SendMessage(text="Новые входы закрыты. Пользователь удалён."), rule="join_closed")
            return True
        for word in combined:
            if word and (word in name or word in username):
                result.add(BanUser(user_id=member.id), rule="join_filter")
                result.add(SendMessage(text=f"Пользователь {member.full_name} заблокирован из-за имени."), rule="join_filter")
                return True
        return False

    async def _apply_captcha(self, message: Message, user_id: int, settings: ChatSettings, result: ModerationResult) -> None:
        config = settings.captcha
        if not config.enabled:
            return
        if await self.captcha_service.pending(message.chat.id, user_id):
            return
        question, buttons = await self.captcha_service.create_challenge(
            message.chat.id, user_id, config.type, config.timeout_seconds
        )
        display_name = next((member.full_name for member in (message.new_chat_members or []) if member.id == user_id), None)
        if not display_name:
            try:
                member = await self.bot.get_chat_member(message.chat.id, user_id)
                display_name = member.user.full_name
            except Exception:  # noqa: BLE001
                display_name = "участник"
        mention = f"<a href=\"tg://user?id={user_id}\">{display_name}</a>"
        permissions = {
            "can_send_messages": False,
            "can_send_media_messages": False,
            "can_send_polls": False,
            "can_send_other_messages": False,
            "can_add_web_page_previews": False,
        }
        result.add(RestrictUser(user_id=user_id, permissions=permissions), rule="captcha")
        keyboard = [buttons] if buttons else None
        result.add(
            SendMessage(
                text=f"{mention}, {question}",
                keyboard=keyboard,
            ),
            rule="captcha",
        )

    async def resolve_captcha(self, chat_id: int, user_id: int, payload: str) -> ModerationResult:
        result = ModerationResult()
        verification = await self.captcha_service.verify(chat_id, user_id, payload)
        settings = await self.chat_service.get_settings(chat_id)
        self._settings_cache[chat_id] = (settings, time.time())
        try:
            member = await self.bot.get_chat_member(chat_id, user_id)
            display_name = member.user.full_name
        except Exception:  # noqa: BLE001
            display_name = "участник"
        mention = f"<a href=\"tg://user?id={user_id}\">{display_name}</a>"
        if verification.success:
            await self.captcha_service.clear(chat_id, user_id)
            result.add(LiftRestrictions(user_id=user_id), rule="captcha_success")
            result.add(SendMessage(text=f"{mention} успешно прошёл проверку ✅"), rule="captcha_success")
            return result
        if verification.expired or verification.attempts >= settings.captcha.max_attempts:
            await self.captcha_service.clear(chat_id, user_id)
            result.add(BanUser(user_id=user_id), rule="captcha_failure")
            result.add(SendMessage(text=f"{mention} не прошёл проверку и заблокирован"), rule="captcha_failure")
            return result
        remaining = max(settings.captcha.max_attempts - verification.attempts, 0)
        result.add(
            SendMessage(
                text=f"{mention}, ответ неверный. Осталось попыток: {remaining}",
            ),
            rule="captcha_retry",
        )
        return result

    async def _process_new_member(self, message: Message, user_id: int, settings: ChatSettings, result: ModerationResult) -> None:
        if settings.system_messages.delete_join:
            result.add(DeleteMessage(message_id=message.message_id), rule="system_join")
        new_member = next((member for member in message.new_chat_members or [] if member.id == user_id), None)
        if await self._apply_join_filter(message, new_member, settings, result):
            return
        if settings.welcome.enabled:
            welcome_text = settings.welcome.text.format(
                user=new_member.full_name if new_member else (message.from_user.full_name if message.from_user else "участник"),
                chat=message.chat.title,
            )
            result.add(SendMessage(text=welcome_text), rule="welcome")
        await self._apply_captcha(message, user_id, settings, result)
        await self._process_anti_raid(message.chat.id, user_id, settings, result)

    async def _process_anti_raid(self, chat_id: int, user_id: int, settings: ChatSettings, result: ModerationResult) -> None:
        config = settings.anti_raid
        if not config.enabled:
            return
        window = self._raid_windows[chat_id]
        now = time.time()
        window.append(now)
        while window and now - window[0] > config.within_seconds:
            window.popleft()
        if len(window) < config.join_threshold:
            return
        try:
            member = await self.bot.get_chat_member(chat_id, user_id)
            display_name = member.user.full_name
        except Exception:  # noqa: BLE001
            display_name = "участник"
        mention = f"<a href=\"tg://user?id={user_id}\">{display_name}</a>"
        if config.action == "mute":
            result.add(MuteUser(user_id=user_id, until_seconds=3600), rule="anti_raid")
            result.add(SendMessage(text=f"{mention} временно ограничен из-за массового вступления."), rule="anti_raid")
        elif config.action == "ban":
            result.add(BanUser(user_id=user_id), rule="anti_raid")
            result.add(SendMessage(text=f"{mention} заблокирован из-за подозрения на рейд."), rule="anti_raid")
        else:
            result.add(SendMessage(text=f"Обнаружена активность рейда. {mention}, подтвердите себя командой /trust при необходимости."), rule="anti_raid_notice")
        result.add(LogAction(level="WARNING", message="Anti-raid triggered", extra={"chat_id": chat_id, "user_id": user_id, "count": len(window)}))
