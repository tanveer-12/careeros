"""Orchestration layer: scrape → normalize → store.

IngestionPipeline wires the three layers together without owning any of them.
Each layer is injected so they can be swapped or mocked independently in tests.

Deduplication is handled at the DB layer via INSERT ... ON CONFLICT DO NOTHING
on the (source, external_id) unique constraint, making all runs idempotent.
"""

from __future__ import annotations

import logging
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy.dialects.postgresql import insert

from core.collectors.base import BaseScraper, RawJob
from core.normalization.job_normalizer import JobNormalizer, NormalizedJob
from database.models.jobs import EmploymentType, Job, JobSource, WorkLocation

logger = logging.getLogger("lumia.pipeline")

_BATCH_SIZE = 50


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class IngestionResult:
    fetched: int    # total RawJobs returned by scraper
    inserted: int   # new rows written to DB
    skipped: int    # duplicates skipped (ON CONFLICT DO NOTHING)
    failed: int     # DB errors
    companies: int  # number of companies scraped
    stale_filtered: int = 0  # jobs dropped by the 24-hour freshness filter
    domain_counts: dict[str, int] = field(default_factory=dict)

    def __str__(self) -> str:
        return (
            f"companies={self.companies} fetched={self.fetched} "
            f"inserted={self.inserted} skipped={self.skipped} "
            f"failed={self.failed} stale_filtered={self.stale_filtered}"
        )


# ---------------------------------------------------------------------------
# Source config for MultiSourcePipeline
# ---------------------------------------------------------------------------

@dataclass
class SourceConfig:
    name: str
    scraper: BaseScraper
    slugs: list[str] = field(default_factory=list)
    is_feed: bool = False  # True for feed-based scrapers that don't use slugs


# ---------------------------------------------------------------------------
# Pipelines
# ---------------------------------------------------------------------------

class IngestionPipeline:
    """Scrape → normalize → upsert pipeline for job postings."""

    def __init__(
        self,
        scraper: BaseScraper,
        normalizer: JobNormalizer,
        session_factory,  # async_session context manager from database.session
    ) -> None:
        self._scraper = scraper
        self._normalizer = normalizer
        self._session_factory = session_factory

    async def run(self, company_slugs: list[str]) -> IngestionResult:
        logger.info("Starting ingestion for %d companies", len(company_slugs))

        async with self._scraper:
            raw_jobs: list[RawJob] = await self._scraper.scrape_companies(company_slugs)
        fetched = len(raw_jobs)

        normalized: list[NormalizedJob] = await self._normalizer.normalize_batch(raw_jobs)

        inserted = 0
        skipped = 0
        failed = 0
        stale_filtered = 0

        for i, batch in enumerate(_batched(normalized, _BATCH_SIZE), start=1):
            try:
                batch_inserted, batch_skipped, batch_stale = await self._store_batch(batch)
                inserted += batch_inserted
                skipped += batch_skipped
                stale_filtered += batch_stale
                logger.info(
                    "Batch %d: inserted %d, skipped %d, stale_filtered %d",
                    i, batch_inserted, batch_skipped, batch_stale,
                )
            except Exception:
                logger.exception("Batch %d failed (%d jobs)", i, len(batch))
                failed += len(batch)

        domain_counts = dict(Counter(job.domain or "unknown" for job in normalized))
        _log_domain_breakdown(normalized)

        result = IngestionResult(
            fetched=fetched,
            inserted=inserted,
            skipped=skipped,
            failed=failed,
            companies=len(company_slugs),
            stale_filtered=stale_filtered,
            domain_counts=domain_counts,
        )
        logger.info("Ingestion complete: %s", result)
        return result

    async def _store_batch(self, jobs: list[NormalizedJob]) -> tuple[int, int, int]:
        """Insert a batch of normalized jobs. Returns (inserted, skipped_duplicate, stale_filtered)."""
        rows = [_to_row(job) for job in jobs]

        async with self._session_factory() as session:
            stmt = (
                insert(Job)
                .values(rows)
                .on_conflict_do_nothing(index_elements=["source", "external_id"])
                .returning(Job.id)
            )
            result = await session.execute(stmt)
            inserted = len(result.fetchall())
            await session.commit()

        return inserted, len(jobs) - inserted, 0


class MultiSourcePipeline:
    """Runs multiple scrapers in sequence, collecting an IngestionResult per source."""

    def __init__(
        self,
        sources: list[SourceConfig],
        normalizer: JobNormalizer,
        session_factory,
    ) -> None:
        self._sources = sources
        self._normalizer = normalizer
        self._session_factory = session_factory

    async def run(self) -> dict[str, IngestionResult]:
        results: dict[str, IngestionResult] = {}
        for source in self._sources:
            pipeline = IngestionPipeline(
                scraper=source.scraper,
                normalizer=self._normalizer,
                session_factory=self._session_factory,
            )
            slugs = [] if source.is_feed else source.slugs
            logger.info("Running source: %s", source.name)
            result = await pipeline.run(slugs)
            results[source.name] = result
            logger.info("Source %s complete: %s", source.name, result)
        return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _log_domain_breakdown(jobs: list[NormalizedJob]) -> None:
    if not jobs:
        return
    counts = Counter(job.domain or "unknown" for job in jobs)
    total = len(jobs)
    top = counts.most_common(6)
    parts = ", ".join(f"{domain}={count/total:.0%}" for domain, count in top)
    logger.info("Domain breakdown (top 6): %s", parts)


def _to_row(job: NormalizedJob) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "source": JobSource(job.source),
        "external_id": job.external_id,
        "source_url": job.source_url,
        "raw_payload": job.raw_payload,
        "scraped_at": job.scraped_at,
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "work_location": WorkLocation(job.work_location) if job.work_location else None,
        "employment_type": EmploymentType(job.employment_type) if job.employment_type else None,
        "description": job.description,
        "skills": job.skills or None,
        "domain": job.domain,
        "seniority": job.seniority,
        "salary_min": job.salary_min,
        "salary_max": job.salary_max,
        "salary_currency": job.salary_currency,
        "posted_at": getattr(job, "posted_at", None),
    }


def _batched(items: list, n: int):
    for i in range(0, len(items), n):
        yield items[i : i + n]


