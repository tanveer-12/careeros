"""Phase 3.01 schema migration — run once against an existing database.

Adds `source` column and widens `parsed_years_exp` to FLOAT on the resumes table.
Safe to re-run: IF NOT EXISTS / IF (type != float8) guards prevent duplicate work.

Usage:
    python scripts/migrate_resume_v301.py
"""

from dotenv import load_dotenv

load_dotenv()

import asyncio

from sqlalchemy import text

import database.models  # noqa: F401 — populate mapper registry
from database.base import Base
from database.session import engine


async def migrate() -> None:
    async with engine.begin() as conn:
        # Create any tables that don't exist yet (safe for fresh installs)
        await conn.run_sync(Base.metadata.create_all)

        # Add source column if missing
        await conn.execute(text("""
            ALTER TABLE resumes
            ADD COLUMN IF NOT EXISTS source VARCHAR(50) NOT NULL DEFAULT 'cli'
        """))

        # Widen parsed_years_exp from INTEGER to FLOAT if still integer
        result = await conn.execute(text("""
            SELECT data_type FROM information_schema.columns
            WHERE table_name = 'resumes' AND column_name = 'parsed_years_exp'
        """))
        row = result.fetchone()
        if row and row[0] in ("integer", "smallint", "bigint"):
            await conn.execute(text("""
                ALTER TABLE resumes
                ALTER COLUMN parsed_years_exp TYPE FLOAT
                USING parsed_years_exp::FLOAT
            """))
            print("  parsed_years_exp widened to FLOAT")
        else:
            print("  parsed_years_exp already FLOAT or not present — skipped")

    print("Migration complete.")


if __name__ == "__main__":
    asyncio.run(migrate())
