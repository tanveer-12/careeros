"""
All ATS scrapers (Greenhouse, Lever, Ashby) for CareerOS.

Scrapers are collected in ATS_REGISTRY at the bottom of this file.
The pipeline and CLI import ATS_REGISTRY only — never the individual classes.
Adding a new ATS source = one new class + one ATS_REGISTRY entry.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from config.settings import settings
from core.collectors.base import BaseScraper, RawJob

UTC = timezone.utc


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TimeoutException):
        return True
    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code >= 500:
        return True
    return False


# ─────────────────────────────────────────────────────────────────────────────
# GreenhouseScraper
# ─────────────────────────────────────────────────────────────────────────────

_gh_log = logging.getLogger("careeros.collectors.greenhouse")


class GreenhouseScraper(BaseScraper):
    source_name = "greenhouse"
    _BASE = "https://boards-api.greenhouse.io/v1/boards"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client
        self._owns_client = client is None

    async def __aenter__(self) -> GreenhouseScraper:
        if self._owns_client:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self

    async def __aexit__(self, *args) -> None:
        if self._owns_client and self._client:
            await self._client.aclose()

    @retry(
        retry=retry_if_exception(_is_retryable),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def _fetch(self, slug: str) -> list[dict]:
        r = await self._client.get(f"{self._BASE}/{slug}/jobs?content=true")
        r.raise_for_status()
        return r.json().get("jobs", [])

    async def scrape_company(self, slug: str) -> list[RawJob]:
        cutoff = datetime.now(UTC) - timedelta(hours=settings.freshness_window_hours)
        try:
            jobs_data = await self._fetch(slug)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                _gh_log.warning("company not found slug=%s", slug)
                return []
            _gh_log.error("HTTP error scraping slug=%s: %s", slug, exc)
            return []
        except Exception as exc:
            _gh_log.error("error scraping slug=%s: %s", slug, exc)
            return []

        now = datetime.now(UTC)
        results: list[RawJob] = []
        for job in jobs_data:
            raw_date = job.get("first_published") or job.get("updated_at")
            posted_at: datetime | None = None
            if raw_date:
                try:
                    posted_at = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
                except ValueError:
                    pass
            if posted_at is not None and posted_at < cutoff:
                continue
            results.append(RawJob(
                source=self.source_name,
                external_id=str(job["id"]),
                source_url=job["absolute_url"],
                raw_payload=job,
                company_slug=slug,
                scraped_at=now,
            ))
        return results

    async def scrape_companies(self, slugs: list[str]) -> list[RawJob]:
        sem = asyncio.Semaphore(settings.scraping_concurrency)

        async def _guarded(slug: str) -> list[RawJob]:
            async with sem:
                return await self.scrape_company(slug)

        batches = await asyncio.gather(*(_guarded(s) for s in slugs))
        return [job for batch in batches for job in batch]


# ─────────────────────────────────────────────────────────────────────────────
# LeverScraper
# ─────────────────────────────────────────────────────────────────────────────

_lv_log = logging.getLogger("careeros.collectors.lever")


class LeverScraper(BaseScraper):
    source_name = "lever"
    _US_BASE = "https://api.lever.co/v0/postings"
    _EU_BASE = "https://api.eu.lever.co/v0/postings"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client
        self._owns_client = client is None

    async def __aenter__(self) -> LeverScraper:
        if self._owns_client:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self

    async def __aexit__(self, *args) -> None:
        if self._owns_client and self._client:
            await self._client.aclose()

    @retry(
        retry=retry_if_exception(_is_retryable),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def _fetch_url(self, url: str) -> list[dict]:
        r = await self._client.get(url)
        r.raise_for_status()
        return r.json()

    async def _fetch(self, slug: str) -> list[dict]:
        try:
            data = await self._fetch_url(f"{self._US_BASE}/{slug}?mode=json")
            _lv_log.debug("US endpoint succeeded for slug=%s", slug)
            return data
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 404:
                raise
        # US was 404 — try EU before giving up
        data = await self._fetch_url(f"{self._EU_BASE}/{slug}?mode=json")
        _lv_log.debug("EU endpoint succeeded for slug=%s", slug)
        return data

    async def scrape_company(self, slug: str) -> list[RawJob]:
        cutoff = datetime.now(UTC) - timedelta(hours=settings.freshness_window_hours)
        try:
            jobs_data = await self._fetch(slug)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                _lv_log.warning("company not found slug=%s", slug)
                return []
            _lv_log.error("HTTP error scraping slug=%s: %s", slug, exc)
            return []
        except Exception as exc:
            _lv_log.error("error scraping slug=%s: %s", slug, exc)
            return []

        now = datetime.now(UTC)
        results: list[RawJob] = []
        for job in jobs_data:
            posted_at: datetime | None = None
            created_ms = job.get("createdAt")
            if created_ms is not None:
                try:
                    posted_at = datetime.fromtimestamp(created_ms / 1000, UTC)
                except (ValueError, OSError):
                    pass
            if posted_at is not None and posted_at < cutoff:
                continue
            results.append(RawJob(
                source=self.source_name,
                external_id=job["id"],
                source_url=job["hostedUrl"],
                raw_payload=job,
                company_slug=slug,
                scraped_at=now,
            ))
        return results

    async def scrape_companies(self, slugs: list[str]) -> list[RawJob]:
        sem = asyncio.Semaphore(settings.scraping_concurrency)

        async def _guarded(slug: str) -> list[RawJob]:
            async with sem:
                return await self.scrape_company(slug)

        batches = await asyncio.gather(*(_guarded(s) for s in slugs))
        return [job for batch in batches for job in batch]


# ─────────────────────────────────────────────────────────────────────────────
# AshbyScraper
# ─────────────────────────────────────────────────────────────────────────────

_ab_log = logging.getLogger("careeros.collectors.ashby")


class AshbyScraper(BaseScraper):
    source_name = "ashby"
    _BASE = "https://api.ashbyhq.com/posting-api/job-board"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client
        self._owns_client = client is None

    async def __aenter__(self) -> AshbyScraper:
        if self._owns_client:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self

    async def __aexit__(self, *args) -> None:
        if self._owns_client and self._client:
            await self._client.aclose()

    @retry(
        retry=retry_if_exception(_is_retryable),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def _fetch(self, slug: str) -> dict:
        r = await self._client.post(
            f"{self._BASE}/{slug}",
            json={},
            headers={"Content-Type": "application/json"},
        )
        r.raise_for_status()
        return r.json()

    async def scrape_company(self, slug: str) -> list[RawJob]:
        cutoff = datetime.now(UTC) - timedelta(hours=settings.freshness_window_hours)
        try:
            data = await self._fetch(slug)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                _ab_log.warning("company not found slug=%s", slug)
                return []
            _ab_log.error("HTTP error scraping slug=%s: %s", slug, exc)
            return []
        except Exception as exc:
            _ab_log.error("error scraping slug=%s: %s", slug, exc)
            return []

        if not data.get("success"):
            _ab_log.warning("company not found slug=%s", slug)
            return []

        now = datetime.now(UTC)
        results: list[RawJob] = []
        for job in data.get("jobs", []):
            posted_at: datetime | None = None
            raw_date = job.get("publishedAt")
            if raw_date:
                try:
                    posted_at = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
                except ValueError:
                    pass
            if posted_at is not None and posted_at < cutoff:
                continue
            results.append(RawJob(
                source=self.source_name,
                external_id=job["id"],
                source_url=job["jobUrl"],
                raw_payload=job,
                company_slug=slug,
                scraped_at=now,
            ))
        return results

    async def scrape_companies(self, slugs: list[str]) -> list[RawJob]:
        sem = asyncio.Semaphore(settings.scraping_concurrency)

        async def _guarded(slug: str) -> list[RawJob]:
            async with sem:
                return await self.scrape_company(slug)

        batches = await asyncio.gather(*(_guarded(s) for s in slugs))
        return [job for batch in batches for job in batch]


# ─────────────────────────────────────────────────────────────────────────────
# Registry
# ─────────────────────────────────────────────────────────────────────────────

ATS_REGISTRY: dict[str, type[BaseScraper]] = {
    "greenhouse": GreenhouseScraper,
    "lever":      LeverScraper,
    "ashby":      AshbyScraper,
}
