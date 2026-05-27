"""Backfill skill-enrichment columns for existing jobs.

Reads raw_payload from rows where skills_final IS NULL or empty, runs the
shared skill enricher, and writes the results back. Safe to re-run — jobs
whose skills_final is already populated are skipped.

Usage:
    python scripts/backfill_skills.py
    python scripts/backfill_skills.py --dry-run   # print counts only, no writes
    python scripts/backfill_skills.py --batch 200
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Ensure the repo root is on sys.path when run directly
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import select, update, func

import database.models  # noqa: F401 — populate SQLAlchemy mapper registry
from database.models.jobs import Job
from database.session import async_session
from core.normalization.skill_enricher import enrich_skills
from core.normalization.job_normalizer import _strip_html, _HIMALAYAS_CATEGORY_MAP, _infer_seniority

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
_log = logging.getLogger("lumia.backfill_skills")


def _categories_from_payload(source: str, raw_payload: dict) -> list[str]:
    if source == "himalayas":
        return (raw_payload.get("categories") or []) + (raw_payload.get("parentCategories") or [])
    if source == "remotive":
        cat = raw_payload.get("category") or ""
        return [cat] if cat else []
    return []


async def backfill(batch_size: int = 100, dry_run: bool = False) -> None:
    # skills_source_version is set on every enrichment run, even when zero skills
    # are found — so it's the only reliable "not yet processed" signal.
    # Checking skills_final emptiness causes infinite loops for jobs with no skills.
    _needs_backfill = Job.skills_source_version == None  # noqa: E711

    async with async_session() as session:
        count_q = select(func.count()).select_from(Job).where(_needs_backfill)
        total: int = (await session.execute(count_q)).scalar_one()

    _log.info("Jobs needing backfill: %d", total)
    if total == 0 or dry_run:
        _log.info("dry_run=%s — exiting without writes", dry_run)
        return

    processed = 0

    while True:
        # No OFFSET — the WHERE clause removes processed rows each iteration,
        # so offset pagination would skip rows as the result set shrinks.
        async with async_session() as session:
            rows = (await session.execute(
                select(Job.id, Job.source, Job.title, Job.description,
                       Job.domain, Job.seniority, Job.raw_payload)
                .where(_needs_backfill)
                .order_by(Job.created_at)
                .limit(batch_size)
            )).all()

        if not rows:
            break

        updates: list[dict] = []
        for row in rows:
            job_id, source, title, description, domain, seniority, raw_payload = row
            # Fall back to title-inferred seniority if the column is not yet populated
            effective_seniority = seniority or _infer_seniority(title)
            categories = _categories_from_payload(source, raw_payload or {})
            enrichment = enrich_skills(title, description, categories, domain, effective_seniority)
            updates.append({
                "job_id": job_id,
                "skills_extracted": enrichment.extracted,
                "skills_normalized": enrichment.normalized,
                "skills_inferred": enrichment.inferred,
                "skills_final": enrichment.final,
                "skills_confidence": enrichment.confidence,
                "skills_source_version": enrichment.source_version,
                "skills": enrichment.final if enrichment.final else None,
            })

        async with async_session() as session:
            for u in updates:
                await session.execute(
                    update(Job)
                    .where(Job.id == u["job_id"])
                    .values(
                        skills_extracted=u["skills_extracted"],
                        skills_normalized=u["skills_normalized"],
                        skills_inferred=u["skills_inferred"],
                        skills_final=u["skills_final"],
                        skills_confidence=u["skills_confidence"],
                        skills_source_version=u["skills_source_version"],
                        skills=u["skills"],
                    )
                )
            await session.commit()

        processed += len(rows)
        _log.info("Backfilled %d / %d", processed, total)

    _log.info("Backfill complete — %d jobs updated", processed)


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill skill-enrichment columns")
    parser.add_argument("--batch", type=int, default=100, help="Rows per DB batch (default 100)")
    parser.add_argument("--dry-run", action="store_true", help="Count eligible rows, no writes")
    args = parser.parse_args()
    asyncio.run(backfill(batch_size=args.batch, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
