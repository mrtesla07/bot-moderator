"""Administrative commands for managing chat settings."""

from __future__ import annotations

from datetime import datetime, time, timedelta

import json
from io import BytesIO
import time as time_module

from aiogram import Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command
from aiogram.types import BotCommand, BotCommandScopeChat, BufferedInputFile, MenuButtonCommands, MenuButtonDefault, Message
from pydantic import ValidationError

from ..models.settings import ChatSettings, StopWordListConfig, StopWordsConfig
from ..services.container import ServiceContainer

router = Router(name="admin")

MAX_BACKUP_BYTES = 512 * 1024



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




def _ensure_stopword_lists(config: StopWordsConfig) -> None:
    if not config.lists:
        config.lists.append(StopWordListConfig())
    if len(config.lists) == 1:
        config.lists.append(StopWordListConfig(name="strict", action="ban"))


def _update_stopword_flag(config: StopWordsConfig) -> None:
    config.enabled = any(stop_list.words for stop_list in config.lists)


def _parse_stopword_argument(raw: str, config: StopWordsConfig) -> tuple[int, str, bool]:
    raw = raw.strip()
    if not raw:
        raise ValueError("Укажите слово после команды.")
    tokens = raw.split(maxsplit=1)
    index = 0
    remainder = raw
    explicit = False
    if tokens[0].isdigit():
        idx = int(tokens[0])
        if idx < 1 or idx > len(config.lists):
            raise ValueError("Неверный номер списка. Используйте 1 или 2.")
        if len(tokens) == 1:
            raise ValueError("После номера списка укажите слово.")
        index = idx - 1
        remainder = tokens[1]
        explicit = True
    word = remainder.strip().lower()
    if not word:
        raise ValueError("Укажите слово для добавления.")
    return index, word, explicit


def _stopword_action_description(stop_list: StopWordListConfig) -> str:
    if stop_list.action == "mute":
        return f"мут на {stop_list.mute_minutes} мин"
    if stop_list.action == "ban":
        return "бан"
    return "удаление"

def _humanize_delta(delta: timedelta) -> str:
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return f"{seconds} с"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} мин"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} ч {minutes % 60} мин"
    days = hours // 24
    return f"{days} д {hours % 24} ч"

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




@router.message(Command("dfbackup"))
async def command_backup_settings(message: Message) -> None:
    services = await _require_admin(message)
    if not services:
        return
    settings = await services.chats.get_settings(message.chat.id)
    data = settings.model_dump(mode="json")
    payload = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    filename = f"moderator_settings_{message.chat.id}.json"
    document = BufferedInputFile(payload, filename=filename)
    chat_title = getattr(message.chat, "title", None) or getattr(message.chat, "full_name", None) or str(message.chat.id)
    await message.answer_document(document=document, caption=f"Дамп настроек для {chat_title}")


@router.message(Command("dfrestore"))
async def command_restore_settings(message: Message) -> None:
    services = await _require_admin(message)
    if not services:
        return
    source_payload: str | None = None
    reply = message.reply_to_message
    if reply and reply.document:
        document = reply.document
        if document.file_size and document.file_size > MAX_BACKUP_BYTES:
            await message.reply("Файл слишком большой, максимум 512 КБ.")
            return
        buffer = BytesIO()
        try:
            await services.bot.download(document, destination=buffer)
        except Exception:
            await message.reply("Не удалось скачать файл из Telegram.")
            return
        try:
            source_payload = buffer.getvalue().decode("utf-8")
        except UnicodeDecodeError:
            await message.reply("Файл должен быть в кодировке UTF-8.")
            return
    elif reply and reply.text:
        source_payload = reply.text.strip()
    elif reply and reply.caption:
        source_payload = reply.caption.strip()
    else:
        parts = (message.text or "").split(maxsplit=1)
        if len(parts) > 1:
            source_payload = parts[1].strip()
    if not source_payload:
        await message.reply("Пришлите файл резервной копии в ответ на команду или вставьте JSON.")
        return
    try:
        data = json.loads(source_payload)
    except json.JSONDecodeError as exc:
        await message.reply(f"Не удалось разобрать JSON: {exc}")
        return
    try:
        new_settings = ChatSettings.model_validate(data)
    except ValidationError as exc:
        await message.reply(f"Настройки не прошли проверку: {exc}")
        return
    current_settings = await services.chats.get_settings(message.chat.id)
    new_settings.subscription = current_settings.subscription
    await services.chats.save_settings(message.chat.id, new_settings)
    cache = getattr(services.moderation, "_settings_cache", None)
    if isinstance(cache, dict):
        cache[message.chat.id] = (new_settings, time_module.time())
    await message.reply("Настройки восстановлены.")



@router.message(Command("dfnocommand"))
async def command_toggle_commands(message: Message) -> None:
    services = await _require_admin(message)
    if not services:
        return
    settings = await services.moderation.get_settings(message)
    config = settings.command_menu
    bot = message.bot
    scope = BotCommandScopeChat(chat_id=message.chat.id)
    try:
        if not config.hidden:
            commands = await bot.get_my_commands(scope=scope)
            if not commands:
                commands = await bot.get_my_commands()
            config.backup_commands = [
                {"command": cmd.command, "description": cmd.description}
                for cmd in commands
            ]
            await bot.set_my_commands([], scope=scope)
            await bot.set_chat_menu_button(MenuButtonDefault())
            config.hidden = True
            response = "Меню команд скрыто до повторного вызова команды."
        else:
            if config.backup_commands:
                restored = [
                    BotCommand(command=item["command"], description=item["description"])
                    for item in config.backup_commands
                ]
                await bot.set_my_commands(restored, scope=scope)
            else:
                await bot.delete_my_commands(scope=scope)
            await bot.set_chat_menu_button(MenuButtonCommands())
            config.hidden = False
            config.backup_commands = []
            response = "Меню команд восстановлено."
    except TelegramBadRequest as exc:
        await message.reply(f"Не удалось обновить меню: {exc}")
        return
    await services.chats.save_settings(message.chat.id, settings)
    await message.reply(response)

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







@router.message(Command("dfrequests"))
async def command_list_join_requests(message: Message) -> None:
    services = await _require_admin(message)
    if not services:
        return
    requests = await services.join_requests.list_pending(message.chat.id)
    if not requests:
        await message.reply("Активных заявок нет.")
        return
    now = datetime.utcnow()
    lines: list[str] = []
    limit = 10
    for req in requests[:limit]:
        age = now - (req.created_at or now)
        lines.append(f"• <code>{req.user_id}</code> · {_humanize_delta(age)}")
        payload = req.questionnaire_answers or {}
        answers = payload.get("answers") or []
        questions = payload.get("questions") or []
        if answers:
            for question, answer in zip(questions, answers):
                lines.append(f"    {question}: {answer}")
        else:
            lines.append("    Ответы: ещё не получены.")
    if len(requests) > limit:
        lines.append(f"… и ещё {len(requests) - limit} заявок")
    await message.reply("\n".join(lines))


def _parse_user_id_argument(message: Message) -> int | None:
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        return None
    arg = parts[1].strip()
    if not arg:
        return None
    try:
        return int(arg.split(maxsplit=1)[0])
    except ValueError:
        return None


@router.message(Command("dfapprove"))
async def command_approve_request(message: Message) -> None:
    services = await _require_admin(message)
    if not services:
        return
    user_id = _parse_user_id_argument(message)
    if user_id is None:
        await message.reply("Укажите ID пользователя: /dfapprove <user_id>.")
        return
    request = await services.join_requests.get_request(message.chat.id, user_id)
    if not request or request.status != "pending":
        await message.reply("Активная заявка не найдена.")
        return
    try:
        await message.bot.approve_chat_join_request(message.chat.id, user_id)
    except TelegramBadRequest as exc:
        await message.reply(f"Не удалось одобрить заявку: {exc}")
        return
    await services.join_requests.set_status(message.chat.id, user_id, "approved")
    await message.reply(f"Заявка пользователя <code>{user_id}</code> одобрена.")
    try:
        await message.bot.send_message(user_id, f"Ваша заявка в чат {message.chat.title} одобрена.")
    except TelegramForbiddenError:
        pass


@router.message(Command("dfreject"))
async def command_reject_request(message: Message) -> None:
    services = await _require_admin(message)
    if not services:
        return
    parts = (message.text or "").split(maxsplit=2)
    if len(parts) < 2:
        await message.reply("Укажите ID пользователя: /dfreject <user_id> [причина].")
        return
    try:
        user_id = int(parts[1])
    except ValueError:
        await message.reply("ID пользователя должен быть числом.")
        return
    reason = parts[2].strip() if len(parts) > 2 else ""
    request = await services.join_requests.get_request(message.chat.id, user_id)
    if not request or request.status != "pending":
        await message.reply("Активная заявка не найдена.")
        return
    try:
        await message.bot.decline_chat_join_request(message.chat.id, user_id)
    except TelegramBadRequest as exc:
        await message.reply(f"Не удалось отклонить заявку: {exc}")
        return
    await services.join_requests.set_status(message.chat.id, user_id, "rejected")
    await message.reply(f"Заявка пользователя <code>{user_id}</code> отклонена.")
    if reason:
        try:
            await message.bot.send_message(user_id, f"Заявка в чат {message.chat.title} отклонена: {reason}")
        except TelegramForbiddenError:
            pass

@router.message(Command("dfcleaner"))
async def command_clean_states(message: Message) -> None:
    services = await _require_admin(message)
    if not services:
        return
    states = await services.users.list_states(message.chat.id)
    if not states:
        await message.reply("Нет сохранённых записей пользователей.")
        return
    bot = message.bot
    start = time_module.time()
    to_remove_missing: set[int] = set()
    to_remove_left: set[int] = set()
    try:
        for state in states:
            try:
                member = await bot.get_chat_member(message.chat.id, state.user_id)
            except TelegramForbiddenError:
                await message.reply("Нужны права администратора, чтобы читать список участников.")
                return
            except TelegramBadRequest:
                to_remove_missing.add(state.user_id)
                continue
            status = getattr(member, "status", None)
            if status in {"left", "kicked"}:
                to_remove_left.add(state.user_id)
    except TelegramBadRequest as exc:  # fallback if chat is inaccessible
        await message.reply(f"Не удалось проверить участников: {exc}")
        return
    removed_total = 0
    removed_total += await services.users.delete_states(message.chat.id, list(to_remove_missing))
    removed_total += await services.users.delete_states(message.chat.id, [uid for uid in to_remove_left if uid not in to_remove_missing])
    elapsed = time_module.time() - start
    summary_lines = [
        "Очистка завершена.",
        f"Удалено записей: {removed_total} (покинули чат: {len(to_remove_left)}, не найдены: {len(to_remove_missing)}).",
        f"Проверено записей: {len(states)} за {elapsed:.1f} с.",
    ]
    await message.reply("\n".join(summary_lines))
@router.message(Command("dfcleandeleted"))
async def command_clean_deleted(message: Message) -> None:
    services = await _require_admin(message)
    if not services:
        return
    states = await services.users.list_states(message.chat.id)
    if not states:
        await message.reply("Нет сохранённых записей пользователей.")
        return
    bot = message.bot
    deleted_ids: set[int] = set()
    try:
        for state in states:
            try:
                member = await bot.get_chat_member(message.chat.id, state.user_id)
            except TelegramForbiddenError:
                await message.reply("Нужны права администратора, чтобы читать список участников.")
                return
            except TelegramBadRequest:
                continue
            if getattr(member.user, "is_deleted", False):
                deleted_ids.add(state.user_id)
    except TelegramBadRequest as exc:
        await message.reply(f"Не удалось проверить участников: {exc}")
        return
    removed = await services.users.delete_states(message.chat.id, list(deleted_ids))
    if removed:
        await message.reply(f"Удалено записей удалённых аккаунтов: {removed}.")
    else:
        await message.reply("Удалённых аккаунтов в базе не найдено.")

@router.message(Command("addstopword"))
async def command_add_stopword(message: Message) -> None:
    services = await _require_admin(message)
    if not services:
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply("Формат: /addstopword [номер_списка] слово")
        return
    settings = await services.moderation.get_settings(message)
    config = settings.stop_words
    _ensure_stopword_lists(config)
    try:
        list_index, word, _ = _parse_stopword_argument(parts[1], config)
    except ValueError as exc:
        await message.reply(str(exc))
        return
    target_list = config.lists[list_index]
    if word in target_list.words:
        await message.reply(f"Слово уже присутствует в списке #{list_index + 1}.")
        return
    for other_index, stop_list in enumerate(config.lists):
        if other_index != list_index and word in stop_list.words:
            stop_list.words.remove(word)
    target_list.words.append(word)
    _update_stopword_flag(config)
    await services.chats.save_settings(message.chat.id, settings)
    await message.reply(f"Слово добавлено в список #{list_index + 1} ({_stopword_action_description(target_list)}).")

@router.message(Command("delstopword"))
async def command_del_stopword(message: Message) -> None:
    services = await _require_admin(message)
    if not services:
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply("Формат: /delstopword [номер_списка] слово")
        return
    settings = await services.moderation.get_settings(message)
    config = settings.stop_words
    _ensure_stopword_lists(config)
    try:
        list_index, word, explicit = _parse_stopword_argument(parts[1], config)
    except ValueError as exc:
        await message.reply(str(exc))
        return
    target_indices = [list_index] if explicit else list(range(len(config.lists)))
    removed_from: int | None = None
    for idx in target_indices:
        stop_list = config.lists[idx]
        if word in stop_list.words:
            stop_list.words.remove(word)
            removed_from = idx
            break
    if removed_from is None:
        await message.reply("Такого слова нет в стоп-листах.")
        return
    _update_stopword_flag(config)
    await services.chats.save_settings(message.chat.id, settings)
    await message.reply(f"Слово удалено из списка #{removed_from + 1} ({_stopword_action_description(config.lists[removed_from])}).")


@router.message(Command("liststopwords"))
async def command_list_stopwords(message: Message) -> None:
    services = await _require_admin(message)
    if not services:
        return
    settings = await services.moderation.get_settings(message)
    config = settings.stop_words
    _ensure_stopword_lists(config)
    lines: list[str] = []
    header_state = "включены" if config.enabled else "отключены"
    lines.append(f"Стоп-слова {header_state}. Порог предупреждений: {config.warn_threshold}.")
    for index, stop_list in enumerate(config.lists, start=1):
        action = _stopword_action_description(stop_list)
        header = f"Список #{index} ({action})"
        if stop_list.name and stop_list.name not in {"default", "soft", "strict"}:
            header += f" — {stop_list.name}"
        body = "\n".join(f"  • {word}" for word in stop_list.words) if stop_list.words else "  - пусто"
        lines.append(f"{header}\n{body}")
    lines.append("Используйте /addstopword и /delstopword с номером списка (1 или 2).")
    await message.reply("\n\n".join(lines))


@router.message(Command("setstoplimit"))
async def command_set_stop_limit(message: Message) -> None:
    services = await _require_admin(message)
    if not services:
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply("Формат: /setstoplimit <1-10>")
        return
    try:
        limit = int(parts[1])
    except ValueError:
        await message.reply("Лимит должен быть числом.")
        return
    if limit < 1 or limit > 10:
        await message.reply("Значение должно быть в диапазоне от 1 до 10.")
        return
    settings = await services.moderation.get_settings(message)
    settings.stop_words.warn_threshold = limit
    await services.chats.save_settings(message.chat.id, settings)
    await message.reply(f"Порог предупреждений по стоп-словам: {limit}.")


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



