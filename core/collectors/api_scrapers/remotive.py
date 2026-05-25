"""Remotive API scraper — fetches remote jobs from remotive.com/api/remote-jobs."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

import httpx

from config.settings import settings
from core.collectors.base import BaseScraper, RawJob

_log = logging.getLogger("lumia.collectors.remotive")

_CATEGORIES_URL = "https://remotive.com/api/remote-jobs/categories"

# Fallback used when the categories endpoint is unavailable.
_FALLBACK_CATEGORY_SLUGS: list[str] = [
    "software-dev", "customer-support", "design", "finance-legal",
    "human-resources", "marketing", "product", "project-management",
    "qa", "sales-business", "devops-sysadmin", "data", "teaching",
    "writing", "all-others",
]


class RemotiveScraper(BaseScraper):
    source_name = "remotive"

    def __init__(self) -> None:
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "RemotiveScraper":
        self._client = httpx.AsyncClient(timeout=30.0)
        return self

    async def __aexit__(self, *_) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def fetch_jobs_page(
        self,
        *,
        category: str | None = None,
        search: str | None = None,
        company_name: str | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        """GET https://remotive.com/api/remote-jobs and return the jobs list."""
        params: dict[str, object] = {}
        if category:
            params["category"] = category
        if search:
            params["search"] = search
        if company_name:
            params["company_name"] = company_name
        if limit is not None:
            params["limit"] = limit

        resp = await self._client.get(settings.REMOTIVE_API_URL, params=params)
        resp.raise_for_status()
        return resp.json().get("jobs", [])

    async def _fetch_category_slugs(self) -> list[str]:
        try:
            resp = await self._client.get(_CATEGORIES_URL)
            resp.raise_for_status()
            cats = resp.json().get("jobs", [])
            slugs = [c["slug"] for c in cats if c.get("slug")]
            if slugs:
                _log.info("Fetched %d categories from API", len(slugs))
                return slugs
        except Exception as exc:
            _log.warning("Categories endpoint failed (%s) — using fallback list", exc)
        return _FALLBACK_CATEGORY_SLUGS

    async def get_fresh_jobs(self) -> list[dict]:
        """Return all jobs across every Remotive category, deduplicated by id."""
        slugs = await self._fetch_category_slugs()
        results = await asyncio.gather(
            *[self.fetch_jobs_page(category=slug) for slug in slugs],
            return_exceptions=True,
        )
        seen: set[str] = set()
        jobs: list[dict] = []
        for batch in results:
            if isinstance(batch, Exception):
                _log.warning("Category fetch failed: %s", batch)
                continue
            for job in batch:
                eid = str(job.get("id", ""))
                if eid and eid not in seen:
                    seen.add(eid)
                    jobs.append(job)
        _log.info("get_fresh_jobs: %d unique jobs across %d categories", len(jobs), len(slugs))
        return jobs

    def _to_raw_job(self, job: dict) -> RawJob:
        return RawJob(
            source=self.source_name,
            external_id=str(job["id"]),
            source_url=job.get("url", ""),
            raw_payload=job,
            company_slug=job.get("company_name", ""),
            scraped_at=datetime.now(timezone.utc),
        )

    async def scrape_company(self, company_slug: str) -> list[RawJob]:
        jobs = await self.fetch_jobs_page(company_name=company_slug)
        return [self._to_raw_job(j) for j in jobs]

    async def scrape_companies(self, company_slugs: list[str]) -> list[RawJob]:
        if not company_slugs:
            return [self._to_raw_job(j) for j in await self.get_fresh_jobs()]

        seen: set[str] = set()
        result: list[RawJob] = []
        for slug in company_slugs:
            for job in await self.fetch_jobs_page(company_name=slug):
                eid = str(job["id"])
                if eid not in seen:
                    seen.add(eid)
                    result.append(self._to_raw_job(job))
        return result
