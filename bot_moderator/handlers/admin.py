"""Administrative commands for managing chat settings."""

from __future__ import annotations

from datetime import time

from aiogram import Router
from aiogram.errors import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import Message

from ..services.container import ServiceContainer

router = Router(name="admin")


async def _require_admin(message: Message) -> ServiceContainer | None:
    services: ServiceContainer = message.bot["services"]
    is_admin = await services.admins.is_admin(message.chat.id, message.from_user.id)
    if not is_admin:
        await message.reply("Эта команда доступна только администраторам.")
        return None
    return services


def _extract_target(message: Message, raw: str | None) -> tuple[int | None, str]:
    if message.reply_to_message and message.reply_to_message.from_user:
        return message.reply_to_message.from_user.id, message.reply_to_message.from_user.full_name
    if not raw:
        return None, ""
    raw = raw.strip()
    if raw.startswith("@"):
        return None, raw
    try:
        return int(raw), raw
    except ValueError:
        return None, raw


async def _resolve_user_id(services: ServiceContainer, chat_id: int, identifier: str | None, fallback_name: str) -> tuple[int | None, str]:
    if identifier is None:
        return None, fallback_name
    if identifier.startswith("@"):
        try:
            chat = await services.bot.get_chat(identifier)
            return chat.id, chat.full_name
        except TelegramBadRequest:
            return None, identifier
    try:
        return int(identifier), fallback_name
    except ValueError:
        return None, identifier


@router.message(Command("dfsync"))
async def command_sync(message: Message) -> None:
    services = await _require_admin(message)
    if not services:
        return
    await services.moderation.get_settings(message)
    await message.reply("✅ Данные синхронизированы")


@router.message(Command("dfaddwl"))
async def command_add_whitelist(message: Message) -> None:
    services = await _require_admin(message)
    if not services:
        return
    raw = message.text.split(maxsplit=1)
    target_id, target_name = _extract_target(message, raw[1] if len(raw) > 1 else None)
    identifier = raw[1] if len(raw) > 1 else None
    if target_id is None:
        resolved_id, resolved_name = await _resolve_user_id(services, message.chat.id, identifier, target_name)
        if resolved_id is None:
            await message.reply("Не удалось определить пользователя для добавления в белый список")
            return
        target_id, target_name = resolved_id, resolved_name
    await services.users.set_whitelist(message.chat.id, target_id, True)
    await message.reply(f"Пользователь {target_name} добавлен в белый список ссылок")


@router.message(Command("dfdelwl"))
async def command_delete_whitelist(message: Message) -> None:
    services = await _require_admin(message)
    if not services:
        return
    raw = message.text.split(maxsplit=1)
    target_id, target_name = _extract_target(message, raw[1] if len(raw) > 1 else None)
    identifier = raw[1] if len(raw) > 1 else None
    if target_id is None:
        resolved_id, resolved_name = await _resolve_user_id(services, message.chat.id, identifier, target_name)
        if resolved_id is None:
            await message.reply("Не удалось определить пользователя для удаления из белого списка")
            return
        target_id, target_name = resolved_id, resolved_name
    await services.users.set_whitelist(message.chat.id, target_id, False)
    await message.reply(f"Пользователь {target_name} удалён из белого списка ссылок")


@router.message(Command("dfwhitelist"))
async def command_list_whitelist(message: Message) -> None:
    services = await _require_admin(message)
    if not services:
        return
    entries = await services.users.list_whitelisted(message.chat.id)
    if not entries:
        await message.reply("Белый список пуст")
        return
    lines = [f"• <code>{entry.user_id}</code> (репутация {entry.reputation})" for entry in entries]
    await message.reply("Белый список:\n" + "\n".join(lines))


@router.message(Command("trust"))
async def command_trust(message: Message) -> None:
    services = await _require_admin(message)
    if not services:
        return
    raw = message.text.split(maxsplit=1)
    target_id, target_name = _extract_target(message, raw[1] if len(raw) > 1 else None)
    identifier = raw[1] if len(raw) > 1 else None
    if target_id is None:
        resolved_id, resolved_name = await _resolve_user_id(services, message.chat.id, identifier, target_name)
        if resolved_id is None:
            await message.reply("Не удалось определить пользователя")
            return
        target_id, target_name = resolved_id, resolved_name
    state = await services.users.get_state(message.chat.id, target_id)
    await services.users.set_trust(message.chat.id, target_id, not state.is_trusted)
    status = "добавлен в доверенные" if not state.is_trusted else "исключён из доверенных"
    await message.reply(f"Пользователь {target_name} {status}")


@router.message(Command("warn"))
async def command_warn(message: Message) -> None:
    services = await _require_admin(message)
    if not services:
        return
    if not message.reply_to_message or not message.reply_to_message.from_user:
        await message.reply("Предупреждать можно только ответом на сообщение")
        return
    warned = await services.users.add_warning(message.chat.id, message.reply_to_message.from_user.id)
    await message.reply(
        f"⚠️ {message.reply_to_message.from_user.full_name} получил предупреждение ({warned})."
    )


@router.message(Command("unwarn"))
async def command_unwarn(message: Message) -> None:
    services = await _require_admin(message)
    if not services:
        return
    if not message.reply_to_message or not message.reply_to_message.from_user:
        await message.reply("Снимать предупреждение нужно ответом на сообщение")
        return
    await services.users.reset_warnings(message.chat.id, message.reply_to_message.from_user.id)
    await message.reply("Предупреждения обнулены")


@router.message(Command("setflood"))
async def command_set_flood(message: Message) -> None:
    services = await _require_admin(message)
    if not services:
        return
    parts = message.text.split()
    if len(parts) < 4:
        await message.reply("Использование: /setflood <лимит> <секунд> <mute|ban|delete>")
        return
    limit, seconds, punishment = parts[1:4]
    try:
        limit_int = int(limit)
        seconds_int = int(seconds)
        if punishment not in {"mute", "ban", "delete"}:
            raise ValueError
    except ValueError:
        await message.reply("Параметры указаны неверно")
        return
    settings = await services.moderation.get_settings(message)
    settings.flood.message_limit = limit_int
    settings.flood.interval_seconds = seconds_int
    settings.flood.punishment = punishment
    await services.chats.save_settings(message.chat.id, settings)
    await message.reply(
        f"Антифлуд обновлён: {limit_int} сообщений за {seconds_int} секунд, действие {punishment}"
    )


@router.message(Command("setnightmode"))
async def command_set_night_mode(message: Message) -> None:
    services = await _require_admin(message)
    if not services:
        return
    parts = message.text.split()
    if len(parts) < 3:
        await message.reply("Использование: /setnightmode <HH:MM> <HH:MM> [delete|mute|off]")
        return
    start_str, end_str = parts[1:3]
    action = parts[3] if len(parts) > 3 else "delete"
    if action == "off":
        settings = await services.moderation.get_settings(message)
        settings.night_mode.enabled = False
        await services.chats.save_settings(message.chat.id, settings)
        await message.reply("Ночной режим отключен")
        return
    try:
        start = time.fromisoformat(start_str)
        end = time.fromisoformat(end_str)
        if action not in {"delete", "mute"}:
            raise ValueError
    except ValueError:
        await message.reply("Параметры указаны неверно")
        return
    settings = await services.moderation.get_settings(message)
    settings.night_mode.enabled = True
    settings.night_mode.start = start
    settings.night_mode.end = end
    settings.night_mode.action = action
    await services.chats.save_settings(message.chat.id, settings)
    await message.reply(f"Ночной режим {start_str}-{end_str} ({action}) активирован")



@router.message(Command("setwelcome"))
async def command_set_welcome(message: Message) -> None:
    services = await _require_admin(message)
    if not services:
        return
    settings = await services.moderation.get_settings(message)
    parts = message.text.split(maxsplit=1)
    if message.reply_to_message and message.reply_to_message.text:
        settings.welcome.text = message.reply_to_message.text
    elif len(parts) > 1:
        settings.welcome.text = parts[1]
    else:
        await message.reply("Передайте текст приветствия ответом или в команде")
        return
    await services.chats.save_settings(message.chat.id, settings)
    await message.reply("Приветствие обновлено")


@router.message(Command("togglewelcome"))
async def command_toggle_welcome(message: Message) -> None:
    services = await _require_admin(message)
    if not services:
        return
    settings = await services.moderation.get_settings(message)
    settings.welcome.enabled = not settings.welcome.enabled
    await services.chats.save_settings(message.chat.id, settings)
    state = "включено" if settings.welcome.enabled else "выключено"
    await message.reply(f"Приветствие {state}")


@router.message(Command("toggleprofanity"))
async def command_toggle_profanity(message: Message) -> None:
    services = await _require_admin(message)
    if not services:
        return
    settings = await services.moderation.get_settings(message)
    settings.profanity.enabled = not settings.profanity.enabled
    await services.chats.save_settings(message.chat.id, settings)
    await message.reply(f"Антимат {'включён' if settings.profanity.enabled else 'выключен'}")


@router.message(Command("addprofanity"))
async def command_add_profanity(message: Message) -> None:
    services = await _require_admin(message)
    if not services:
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply("Укажите слово")
        return
    settings = await services.moderation.get_settings(message)
    word = parts[1].strip().lower()
    if word not in settings.profanity.dictionary:
        settings.profanity.dictionary.append(word)
        settings.profanity.enabled = True
        await services.chats.save_settings(message.chat.id, settings)
    await message.reply("Слово добавлено в словарь мата")


@router.message(Command("addstopword"))
async def command_add_stopword(message: Message) -> None:
    services = await _require_admin(message)
    if not services:
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply("Укажите слово для стоп-листа")
        return
    settings = await services.moderation.get_settings(message)
    word = parts[1].strip().lower()
    if word not in settings.stop_words.lists[0].words:
        settings.stop_words.lists[0].words.append(word)
        settings.stop_words.enabled = True
        await services.chats.save_settings(message.chat.id, settings)
    await message.reply("Стоп-слово добавлено")


@router.message(Command("delstopword"))
async def command_del_stopword(message: Message) -> None:
    services = await _require_admin(message)
    if not services:
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply("Укажите слово для удаления")
        return
    settings = await services.moderation.get_settings(message)
    word = parts[1].strip().lower()
    if word in settings.stop_words.lists[0].words:
        settings.stop_words.lists[0].words.remove(word)
        await services.chats.save_settings(message.chat.id, settings)
    await message.reply("Стоп-слово удалено")


@router.message(Command("liststopwords"))
async def command_list_stopwords(message: Message) -> None:
    services = await _require_admin(message)
    if not services:
        return
    settings = await services.moderation.get_settings(message)
    words = settings.stop_words.lists[0].words
    if not words:
        await message.reply("В стоп-листе пока пусто")
        return
    await message.reply("Стоп-слова\n" + "\n".join(words))


@router.message(Command("setreportchat"))
async def command_set_report_chat(message: Message) -> None:
    services = await _require_admin(message)
    if not services:
        return
    settings = await services.moderation.get_settings(message)
    if message.reply_to_message and message.reply_to_message.forward_from_chat:
        target = message.reply_to_message.forward_from_chat.id
    else:
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            settings.reports.destination_chat_id = message.chat.id
            await services.chats.save_settings(message.chat.id, settings)
            await message.reply("Чат отчётов сброшен на текущий")
            return
        try:
            target = int(parts[1])
        except ValueError:
            await message.reply("Укажите ID чата для отчётов")
            return
    settings.reports.destination_chat_id = target
    settings.reports.enabled = True
    await services.chats.save_settings(message.chat.id, settings)
    await message.reply(f"Чат отчётов установлен: <code>{target}</code>")




@router.message(Command("togglesilent"))
async def command_toggle_silent(message: Message) -> None:
    services = await _require_admin(message)
    if not services:
        return
    settings = await services.moderation.get_settings(message)
    settings.silent_mode.enabled = not settings.silent_mode.enabled
    await services.chats.save_settings(message.chat.id, settings)
    await message.reply(f"Тихий режим {'включён' if settings.silent_mode.enabled else 'выключен'}")


@router.message(Command("settimezone"))
async def command_set_timezone(message: Message) -> None:
    services = await _require_admin(message)
    if not services:
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply("Укажите идентификатор временной зоны, например Europe/Moscow")
        return
    tz_name = parts[1].strip()
    settings = await services.moderation.get_settings(message)
    settings.timezone = tz_name
    await services.chats.save_settings(message.chat.id, settings)
    await message.reply(f"Часовой пояс обновлён: {tz_name}")

@router.message(Command("setlinkmode"))
async def command_set_link_mode(message: Message) -> None:
    services = await _require_admin(message)
    if not services:
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply("Использование: /setlinkmode <block|allow|trust>")
        return
    mode = parts[1].strip().lower()
    settings = await services.moderation.get_settings(message)
    if mode == "block":
        settings.link_guard.block_all = True
        settings.link_guard.allow_trusted = False
        response = "Ссылки полностью заблокированы"
    elif mode == "allow":
        settings.link_guard.block_all = False
        response = "Ссылки разрешены, работают только стоп-листы"
    elif mode == "trust":
        settings.link_guard.allow_trusted = True
        response = "Ссылки доступны для доверенных пользователей"
    else:
        await message.reply("Неизвестный режим")
        return
    await services.chats.save_settings(message.chat.id, settings)
    await message.reply(response)
@router.message(Command("setrules"))
async def command_set_rules(message: Message) -> None:
    services = await _require_admin(message)
    if not services:
        return
    settings = await services.moderation.get_settings(message)
    if message.reply_to_message and message.reply_to_message.text:
        settings.rules.text = message.reply_to_message.text
    else:
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            await message.reply("Передайте текст правил ответом на сообщение или в команде")
            return
        settings.rules.text = parts[1]
    await services.chats.save_settings(message.chat.id, settings)
    await message.reply("Правила обновлены")


@router.message(Command("rules"))
async def command_show_rules(message: Message) -> None:
    services = message.bot["services"]
    settings = await services.moderation.get_settings(message)
    if not settings.rules.text:
        await message.reply("Правила ещё не заданы")
        return
    await message.reply(settings.rules.text)


@router.message(Command("moderatorinfo"))
async def command_show_info(message: Message) -> None:
    services = message.bot["services"]
    settings = await services.moderation.get_settings(message)
    lines = [
        "📋 Настройки:",
        f"• Антифлуд: {'вкл' if settings.flood.enabled else 'выкл'}, лимит {settings.flood.message_limit}/{settings.flood.interval_seconds}s",
        f"• Антимат: {'вкл' if settings.profanity.enabled else 'выкл'}",
        f"• Стоп-слова: {'вкл' if settings.stop_words.enabled else 'выкл'}",
        f"• Ночной режим: {'вкл' if settings.night_mode.enabled else 'выкл'}",
        f"• Ссылки: {'запрет' if settings.link_guard.block_all else 'по спискам'}",
        f"• Подписка: {settings.subscription.tier}",
    ]
    await message.reply("\n".join(lines))
