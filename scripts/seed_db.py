"""Smoke-test script: write one Job row and read it back from PostgreSQL.

Usage:
    python scripts/seed_db.py
"""

# load_dotenv must run before database.session is imported,
# because session.py reads DATABASE_URL at module level.
from dotenv import load_dotenv

load_dotenv()

import asyncio

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

import database.models  # noqa: F401 — populate the mapper registry
from database.base import Base
from database.models.jobs import Job, JobSource, JobStatus
from database.session import async_session, engine


async def create_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def insert_job() -> None:
    job = Job(
        source=JobSource.greenhouse,
        external_id="test-001",
        source_url="https://example.com/jobs/1",
        raw_payload={"title": "Data Engineer", "company": "Acme"},
        title="Data Engineer",
        company="Acme Corp",
        status=JobStatus.raw,
    )
    try:
        async with async_session() as session:
            session.add(job)
            await session.commit()  # populate job.id before commit
            await session.refresh(job)
            print(f"✓ Inserted job {job.id}")
    except IntegrityError as e:
        print("! Job test-001 already exists — skipping insert")


async def fetch_jobs() -> None:
    async with async_session() as session:
        result = await session.execute(select(Job))
        jobs = result.scalars().all()
    print(f"✓ Found {len(jobs)} job(s)")
    for j in jobs:
        print(f"  • {j.title} @ {j.company}")


async def main() -> None:
    await create_tables()
    await insert_job()
    await fetch_jobs()


if __name__ == "__main__":
    asyncio.run(main())