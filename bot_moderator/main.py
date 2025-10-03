"""Entry point for running the bot."""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from .config import get_settings
from .core.application import Application


async def main() -> None:
    """Configure logging, bootstrap the application and start polling."""

    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    bot = Bot(token=settings.bot_token, parse_mode=ParseMode.HTML)
    dispatcher = Dispatcher(storage=MemoryStorage())

    app = Application(settings=settings, dispatcher=dispatcher, bot=bot)
    await app.initialize()

    await bot.delete_webhook(drop_pending_updates=True)
    await dispatcher.start_polling(bot)


def run() -> None:
    """Synchronous wrapper used by CLI."""

    asyncio.run(main())


if __name__ == "__main__":
    run()
