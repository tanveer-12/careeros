"""Himalayas API scraper — fetches remote jobs from himalayas.app/jobs/api.

Pagination: GET /jobs/api?offset=N&limit=20  (API hard cap: 20 per request)
All jobs on Himalayas are remote-only, so work_location is always "remote".
Rate limit: data is cached every 24 h; add a small delay between requests.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

import httpx

from config.settings import settings
from core.collectors.base import BaseScraper, RawJob

_log = logging.getLogger("lumia.collectors.himalayas")


class HimalayasScraper(BaseScraper):
    source_name = "himalayas"

    def __init__(self) -> None:
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "HimalayasScraper":
        self._client = httpx.AsyncClient(
            timeout=30.0,
            headers={"User-Agent": "lumia/0.1 (job-ingestion; +https://github.com/tanveer-12/lumia)"},
        )
        return self

    async def __aexit__(self, *_) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _fetch_batch(self, offset: int) -> tuple[list[dict], int] | None:
        """Fetch one batch at the given offset. Returns (jobs, totalCount), or None to stop."""
        resp = await self._client.get(
            settings.HIMALAYAS_API_URL,
            params={"offset": offset, "limit": settings.HIMALAYAS_PAGE_LIMIT},
        )
        if resp.status_code in (403, 429):
            # offset=0 means a genuine block (rate-limited or access denied); raise so caller knows
            if offset == 0:
                body = resp.text[:300]
                raise httpx.HTTPStatusError(
                    f"Himalayas API blocked at offset=0 (status {resp.status_code}). "
                    f"If you just ran a dry-run, wait a few minutes before ingesting. Body: {body}",
                    request=resp.request,
                    response=resp,
                )
            _log.warning(
                "Himalayas returned %d at offset=%d — pagination cap reached, stopping (collected so far will be used)",
                resp.status_code, offset,
            )
            return None
        resp.raise_for_status()
        data = resp.json()
        jobs = data.get("jobs", [])
        total_count = data.get("totalCount", len(jobs))
        return jobs, total_count

    async def get_fresh_jobs(self) -> list[dict]:
        """Fetch all jobs by walking offset-based pages, deduplicating by guid."""
        limit = settings.HIMALAYAS_PAGE_LIMIT
        all_jobs: list[dict] = []
        seen_guids: set[str] = set()
        offset = 0

        while True:
            result = await self._fetch_batch(offset)
            if result is None:
                break  # pagination cap hit — use what we have
            batch, total_count = result
            if not batch:
                break
            for job in batch:
                guid = job.get("guid") or ""
                if guid and guid in seen_guids:
                    continue
                if guid:
                    seen_guids.add(guid)
                all_jobs.append(job)
            _log.info("Himalayas offset=%d: +%d jobs (%d unique / %d total)", offset, len(batch), len(all_jobs), total_count)
            offset += limit
            if offset >= total_count:
                break
            await asyncio.sleep(0.15)  # stay well under the rate limit

        _log.info("get_fresh_jobs: %d unique jobs fetched from Himalayas", len(all_jobs))
        return all_jobs

    def _to_raw_job(self, job: dict) -> RawJob:
        # guid is a stable URL used as the unique job identifier in this API
        job_id = str(job.get("guid") or "")
        url = job.get("applicationLink") or job.get("guid") or ""
        company_slug = job.get("companySlug") or job.get("companyName") or ""

        return RawJob(
            source=self.source_name,
            external_id=job_id,
            source_url=url,
            raw_payload=job,
            company_slug=str(company_slug),
            scraped_at=datetime.now(timezone.utc),
        )

    async def scrape_company(self, company_slug: str) -> list[RawJob]:
        """Filter fresh jobs by company name or slug (Himalayas has no per-company endpoint)."""
        slug_lower = company_slug.lower()
        jobs = await self.get_fresh_jobs()
        matched: list[RawJob] = []
        for job in jobs:
            name = (job.get("companyName") or "").lower()
            cs = (job.get("companySlug") or "").lower()
            if slug_lower in name or slug_lower in cs:
                matched.append(self._to_raw_job(job))
        return matched

    async def scrape_companies(self, company_slugs: list[str]) -> list[RawJob]:
        """Fetch all jobs (no slugs) or filter by company name/slug if provided."""
        raw = await self.get_fresh_jobs()
        if not company_slugs:
            return [self._to_raw_job(j) for j in raw]

        slugs_lower = {s.lower() for s in company_slugs}
        result: list[RawJob] = []
        seen: set[str] = set()
        for job in raw:
            name = (job.get("companyName") or "").lower()
            cs = (job.get("companySlug") or "").lower()
            if any(s in name or s in cs for s in slugs_lower):
                eid = str(job.get("guid") or "")
                if eid and eid not in seen:
                    seen.add(eid)
                    result.append(self._to_raw_job(job))
        return result
