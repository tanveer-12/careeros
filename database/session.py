"""Single database connection entrypoint for CareerOS async I/O."""

import os
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config.settings import settings
_url = settings.database_url
if not _url:
    raise RuntimeError(
        "DATABASE_URL environment variable is not set. "
        "Expected format: postgresql+asyncpg://user:password@host/dbname"
    )

engine = create_async_engine(_url)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


@asynccontextmanager
async def async_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
