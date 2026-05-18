"""Daily ingestion scheduler.

Runs the full multi-source pipeline on a cron schedule using APScheduler's
BackgroundScheduler (thread-based, safe alongside an asyncio event loop).

The job function mirrors `careeros ingest` exactly — both paths share the same
pipeline code (MultiSourcePipeline). No duplication.

Wired into the FastAPI app in Phase 9. For now this module can be imported
and started standalone.

    from core.scheduler.daily_ingest import start_scheduler, stop_scheduler
    start_scheduler()  # non-blocking; runs in background thread
"""

from __future__ import annotations

import asyncio
import logging
import traceback

from apscheduler.schedulers.background import BackgroundScheduler

from config.settings import settings

_log = logging.getLogger("careeros.scheduler")

_scheduler: BackgroundScheduler | None = None


# ---------------------------------------------------------------------------
# Job
# ---------------------------------------------------------------------------

def _run_ingestion_job() -> None:
    """Entry point called by APScheduler. Bridges sync→async via asyncio.run()."""
    _log.info("Scheduled ingestion job starting")
    try:
        asyncio.run(_pipeline_run())
        _log.info("Scheduled ingestion job completed")
    except Exception:
        # Log full traceback but do NOT re-raise — a crash here would kill the scheduler.
        _log.error("Scheduled ingestion job failed:\n%s", traceback.format_exc())


async def _pipeline_run() -> None:
    """Runs the full multi-source pipeline (same sources as `careeros ingest`)."""
    from core.collectors.feed_scrapers import FEED_REGISTRY
    from core.normalization.job_normalizer import JobNormalizer
    from core.workflows.pipeline import MultiSourcePipeline, SourceConfig
    from database.session import async_session

    source_configs: list[SourceConfig] = [
        SourceConfig(name=feed, scraper=FEED_REGISTRY[feed](), is_feed=True)
        for feed in FEED_REGISTRY
    ]

    normalizer = JobNormalizer()
    pipeline = MultiSourcePipeline(source_configs, normalizer, async_session)
    results = await pipeline.run()

    total_fetched = sum(r.fetched for r in results.values())
    total_inserted = sum(r.inserted for r in results.values())
    _log.info(
        "Pipeline complete: fetched=%d inserted=%d across %d source(s)",
        total_fetched,
        total_inserted,
        len(results),
    )
    for name, result in results.items():
        _log.info("  %s: %s", name, result)


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

def start_scheduler() -> None:
    """Start the background scheduler. Safe to call multiple times (idempotent)."""
    global _scheduler

    if _scheduler is not None and _scheduler.running:
        _log.warning("Scheduler is already running — ignoring start_scheduler() call")
        return

    _scheduler = BackgroundScheduler()
    _scheduler.add_job(
        _run_ingestion_job,
        trigger="cron",
        hour=settings.scheduler_hour,
        minute=settings.scheduler_minute,
        id="daily_ingest",
        name="Daily multi-source job ingestion",
        misfire_grace_time=3600,  # tolerate up to 1h late start (e.g. server was down)
        coalesce=True,            # run at most once if multiple firings were missed
    )
    _scheduler.start()
    _log.info(
        "Scheduler started — daily ingest scheduled at %02d:%02d UTC",
        settings.scheduler_hour,
        settings.scheduler_minute,
    )


def stop_scheduler() -> None:
    """Gracefully shut down the scheduler, waiting for any running job to finish."""
    global _scheduler

    if _scheduler is None or not _scheduler.running:
        return

    _scheduler.shutdown(wait=True)
    _log.info("Scheduler stopped")
    _scheduler = None
