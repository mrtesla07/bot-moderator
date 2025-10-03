"""Async database helpers for SQLModel."""

from __future__ import annotations

from pathlib import Path
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel


class Database:
    """Factory for async SQLModel sessions."""

    def __init__(self, url: str, storage_dir: str) -> None:
        self.url = url
        self.storage_dir = Path(storage_dir)
        if self.url.startswith("sqlite"):
            self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._engine: AsyncEngine | None = None
        self._sessionmaker: async_sessionmaker[AsyncSession] | None = None

    async def connect(self) -> None:
        """Initialise engine and session factory."""

        if self._engine:
            return
        self._engine = create_async_engine(self.url, future=True, echo=False)
        self._sessionmaker = async_sessionmaker(self._engine, class_=AsyncSession, expire_on_commit=False)
        async with self._engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

    async def disconnect(self) -> None:
        """Dispose engine."""

        if self._engine is None:
            return
        await self._engine.dispose()
        self._engine = None
        self._sessionmaker = None

    def sessionmaker(self) -> async_sessionmaker[AsyncSession]:
        if not self._sessionmaker:
            raise RuntimeError("Database is not connected")
        return self._sessionmaker

    async def session(self) -> AsyncIterator[AsyncSession]:
        """Context manager/generator for sessions."""

        session_factory = self.sessionmaker()
        async with session_factory() as session:
            yield session

    async def __aenter__(self) -> "Database":
        await self.connect()
        return self

    async def __aexit__(self, *exc_info) -> None:
        await self.disconnect()
