"""Callback query handlers (captcha confirmation, etc.)."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery

from ..services.container import ServiceContainer
from .messages import apply_actions

router = Router(name="callbacks")


@router.callback_query(F.data.startswith("cap|"))
async def handle_captcha(callback: CallbackQuery) -> None:
    if not callback.message:
        await callback.answer()
        return
    services: ServiceContainer = callback.bot["services"]
    result = await services.moderation.resolve_captcha(
        chat_id=callback.message.chat.id,
        user_id=callback.from_user.id,
        payload=callback.data,
    )
    settings = await services.chats.get_settings(callback.message.chat.id)
    await apply_actions(callback.message, result, settings)
    if any(rule == "captcha_success" for rule in result.triggered_rules):
        await callback.answer("Проверка пройдена")
        try:
            await callback.message.delete()
        except Exception:  # noqa: BLE001
            pass
    elif any(rule == "captcha_failure" for rule in result.triggered_rules):
        await callback.answer("Проверка не пройдена", show_alert=True)
    else:
        await callback.answer("Попробуйте ещё раз", show_alert=False)
