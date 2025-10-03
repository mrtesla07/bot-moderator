"""Register all routers with the dispatcher."""

from aiogram import Dispatcher

from . import admin, callbacks, messages


def register_handlers(dispatcher: Dispatcher) -> None:
    dispatcher.include_router(admin.router)
    dispatcher.include_router(callbacks.router)
    dispatcher.include_router(messages.router)
