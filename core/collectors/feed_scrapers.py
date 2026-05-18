"""
Feed-based scrapers for CareerOS: Simplify, YC, Jobright.

Feed scrapers aggregate jobs across thousands of companies without needing
company slugs. Their primary entry point is scrape_all(); scrape_companies()
is wired to call it so the pipeline treats them identically to ATS scrapers.

FEED_REGISTRY at the bottom is the only import the pipeline needs.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import re
from datetime import datetime, timedelta, timezone

import httpx
from selectolax.parser import HTMLParser
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from config.settings import settings
from core.collectors.base import BaseScraper, RawJob

UTC = timezone.utc


# ── Shared utilities ──────────────────────────────────────────────────────────

def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TimeoutException):
        return True
    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code >= 500:
        return True
    return False


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _parse_simplify_age(age: str) -> datetime | None:
    """Parse Simplify age strings: '5d', '2w', 'today', '3h'."""
    s = age.strip().lower()
    now = datetime.now(UTC)
    if s in ("today", "0d", "just now", ""):
        return now
    m = re.match(r"^(\d+)([hdwm])$", s)
    if not m:
        return None
    value, unit = int(m.group(1)), m.group(2)
    if unit == "h":
        return now - timedelta(hours=value)
    if unit == "d":
        return now - timedelta(days=value)
    if unit == "w":
        return now - timedelta(weeks=value)
    if unit == "m":
        return now - timedelta(days=value * 30)
    return None


def _parse_yc_age(created_at: str) -> datetime | None:
    """Parse YC relative age strings: '3 hours ago', '2 days ago'."""
    s = created_at.strip().lower()
    now = datetime.now(UTC)
    if any(k in s for k in ("just now", "today", "moments")):
        return now
    m = re.match(r"(\d+)\s+(second|minute|hour|day|week|month)s?\s+ago", s)
    if not m:
        return None
    value, unit = int(m.group(1)), m.group(2)
    deltas: dict[str, timedelta] = {
        "second": timedelta(seconds=value),
        "minute": timedelta(minutes=value),
        "hour":   timedelta(hours=value),
        "day":    timedelta(days=value),
        "week":   timedelta(weeks=value),
        "month":  timedelta(days=value * 30),
    }
    return now - deltas[unit]


def _is_fresh(posted_at: datetime | None, cutoff: datetime) -> bool:
    return posted_at is None or posted_at >= cutoff


# ─────────────────────────────────────────────────────────────────────────────
# SimplifyScraper
# ─────────────────────────────────────────────────────────────────────────────

_si_log = logging.getLogger("careeros.collectors.simplify")


class SimplifyScraper(BaseScraper):
    source_name = "simplify"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client
        self._owns_client = client is None

    async def __aenter__(self) -> SimplifyScraper:
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
    async def _fetch(self, url: str) -> str:
        r = await self._client.get(url)
        r.raise_for_status()
        return r.text

    async def scrape_all(self) -> list[RawJob]:
        cutoff = datetime.now(UTC) - timedelta(hours=settings.freshness_window_hours)
        try:
            html = await self._fetch(settings.simplify_feed_url)
        except Exception as exc:
            _si_log.error("error fetching simplify feed: %s", exc)
            return []

        tree = HTMLParser(html)
        rows = tree.css("tbody tr")
        now = datetime.now(UTC)
        results: list[RawJob] = []

        for row in rows:
            cells = row.css("td")
            if len(cells) < 5:
                continue
            company  = cells[0].text(strip=True)
            role     = cells[1].text(strip=True)
            location = cells[2].text(strip=True)
            age_str  = cells[4].text(strip=True)

            apply_node = cells[3].css_first("a")
            source_url = apply_node.attributes.get("href", "") if apply_node else ""

            posted_at = _parse_simplify_age(age_str)
            if not _is_fresh(posted_at, cutoff):
                continue

            if not company or not role:
                continue

            results.append(RawJob(
                source=self.source_name,
                external_id=_slugify(f"{company}-{role}"),
                source_url=source_url,
                raw_payload={"company": company, "role": role,
                             "location": location, "age": age_str},
                company_slug=_slugify(company),
                scraped_at=now,
            ))

        return results

    async def scrape_company(self, company_slug: str) -> list[RawJob]:
        raise NotImplementedError("SimplifyScraper does not support per-company scraping")

    async def scrape_companies(self, company_slugs: list[str]) -> list[RawJob]:
        sem = asyncio.Semaphore(settings.scraping_concurrency)
        async with sem:
            return await self.scrape_all()


# ─────────────────────────────────────────────────────────────────────────────
# YCScraper
# ─────────────────────────────────────────────────────────────────────────────

_yc_log = logging.getLogger("careeros.collectors.yc")
_YC_BASE = "https://www.ycombinator.com"


class YCScraper(BaseScraper):
    source_name = "yc"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client
        self._owns_client = client is None

    async def __aenter__(self) -> YCScraper:
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
    async def _fetch(self, url: str) -> str:
        r = await self._client.get(url)
        r.raise_for_status()
        return r.text

    def _extract_job_postings(self, html: str) -> list[dict]:
        marker = '"jobPostings":'
        idx = html.find(marker)
        if idx == -1:
            _yc_log.warning("jobPostings marker not found in YC page")
            return []
        value_start = idx + len(marker)
        while value_start < len(html) and html[value_start] in " \t\n\r":
            value_start += 1
        try:
            postings, _ = json.JSONDecoder().raw_decode(html, value_start)
            return postings if isinstance(postings, list) else []
        except json.JSONDecodeError as exc:
            _yc_log.warning("failed to decode YC jobPostings JSON: %s", exc)
            return []

    async def scrape_all(self) -> list[RawJob]:
        cutoff = datetime.now(UTC) - timedelta(hours=settings.freshness_window_hours)
        try:
            html = await self._fetch(settings.yc_jobs_feed_url)
        except Exception as exc:
            _yc_log.error("error fetching YC jobs page: %s", exc)
            return []

        postings = self._extract_job_postings(html)
        now = datetime.now(UTC)
        results: list[RawJob] = []

        for item in postings:
            company = item.get("companyName", "")
            title   = item.get("title", "")

            raw_url = item.get("url") or item.get("applyUrl", "")
            source_url = (
                f"{_YC_BASE}{raw_url}" if raw_url.startswith("/") else raw_url
            )

            created_at_str = item.get("createdAt", "")
            posted_at = _parse_yc_age(created_at_str) if created_at_str else None
            if not _is_fresh(posted_at, cutoff):
                continue

            external_id = str(item["id"]) if "id" in item else _slugify(f"{company}-{title}")

            results.append(RawJob(
                source=self.source_name,
                external_id=external_id,
                source_url=source_url,
                raw_payload=item,
                company_slug=_slugify(company),
                scraped_at=now,
            ))

        return results

    async def scrape_company(self, company_slug: str) -> list[RawJob]:
        raise NotImplementedError("YCScraper does not support per-company scraping")

    async def scrape_companies(self, company_slugs: list[str]) -> list[RawJob]:
        sem = asyncio.Semaphore(settings.scraping_concurrency)
        async with sem:
            return await self.scrape_all()


# ─────────────────────────────────────────────────────────────────────────────
# JobrightScraper
# ─────────────────────────────────────────────────────────────────────────────

_jr_log = logging.getLogger("careeros.collectors.jobright")


class JobrightScraper(BaseScraper):
    source_name = "jobright"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client
        self._owns_client = client is None

    async def __aenter__(self) -> JobrightScraper:
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
    async def _fetch(self, url: str) -> str:
        r = await self._client.get(url)
        r.raise_for_status()
        return r.text

    def _extract_job_list(self, html: str) -> list[dict]:
        tree = HTMLParser(html)
        script = tree.css_first("script#__NEXT_DATA__")
        if not script:
            _jr_log.warning("__NEXT_DATA__ script tag not found in Jobright page")
            return []
        try:
            data = json.loads(script.text())
            return data["props"]["pageProps"]["jobList"]
        except (json.JSONDecodeError, KeyError) as exc:
            _jr_log.warning("failed to extract Jobright jobList: %s", exc)
            return []

    async def scrape_all(self) -> list[RawJob]:
        cutoff = datetime.now(UTC) - timedelta(hours=settings.freshness_window_hours)
        try:
            html = await self._fetch(settings.jobright_feed_url)
        except Exception as exc:
            _jr_log.error("error fetching Jobright page: %s", exc)
            return []

        job_list = self._extract_job_list(html)
        now = datetime.now(UTC)
        results: list[RawJob] = []

        for item in job_list:
            job_result     = item.get("jobResult", {})
            company_result = item.get("companyResult", {})

            publish_time = job_result.get("publishTime", "")
            posted_at: datetime | None = None
            if publish_time:
                try:
                    posted_at = datetime.fromisoformat(
                        publish_time.replace("Z", "+00:00")
                    )
                except ValueError:
                    pass
            if not _is_fresh(posted_at, cutoff):
                continue

            company    = company_result.get("companyName", "")
            source_url = job_result.get("applyLink") or job_result.get("url", "")
            external_id = str(item["jobId"]) if "jobId" in item else _slugify(
                f"{company}-{job_result.get('jobTitle', '')}"
            )

            results.append(RawJob(
                source=self.source_name,
                external_id=external_id,
                source_url=source_url,
                raw_payload={"job": job_result, "company": company_result},
                company_slug=_slugify(company),
                scraped_at=now,
            ))

        return results

    async def scrape_company(self, company_slug: str) -> list[RawJob]:
        raise NotImplementedError("JobrightScraper does not support per-company scraping")

    async def scrape_companies(self, company_slugs: list[str]) -> list[RawJob]:
        sem = asyncio.Semaphore(settings.scraping_concurrency)
        async with sem:
            return await self.scrape_all()


# ─────────────────────────────────────────────────────────────────────────────
# HiringCafeScraper
# ─────────────────────────────────────────────────────────────────────────────

_hc_log = logging.getLogger("careeros.collectors.hiringcafe")
_HC_MAX_PAGES = 40  # safety cap; fresh 24h window rarely exceeds this


class HiringCafeScraper(BaseScraper):
    """Scrapes hiring.cafe by parsing __NEXT_DATA__ JSON embedded in each page.

    The /_next/data/ hash endpoint changes on every deployment and is unstable;
    parsing the SSR script tag is the only reliable extraction path.
    """

    source_name = "hiringcafe"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client
        self._owns_client = client is None

    async def __aenter__(self) -> HiringCafeScraper:
        if self._owns_client:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers={"User-Agent": "Mozilla/5.0 (compatible; CareerOS/1.0)"},
                follow_redirects=True,
            )
        return self

    async def __aexit__(self, *args) -> None:
        if self._owns_client and self._client:
            await self._client.aclose()

    @retry(
        retry=retry_if_exception(_is_retryable),
        wait=wait_exponential(multiplier=1, min=2, max=15),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def _fetch(self, url: str) -> str:
        r = await self._client.get(url)
        r.raise_for_status()
        return r.text

    def _parse_page(self, html: str) -> tuple[list[dict], int, int]:
        """Returns (jobs, total_count, page_size). Returns empty list on parse failure."""
        tree = HTMLParser(html)
        script = tree.css_first("script#__NEXT_DATA__")
        if not script:
            _hc_log.warning("__NEXT_DATA__ script tag not found in HiringCafe page")
            return [], 0, 1
        try:
            data = json.loads(script.text())
            pp = data["props"]["pageProps"]
            return pp["ssrHits"], pp["ssrTotalCount"], pp.get("ssrPageSize", 25)
        except (json.JSONDecodeError, KeyError) as exc:
            _hc_log.warning("failed to parse HiringCafe __NEXT_DATA__: %s", exc)
            return [], 0, 1

    def _to_raw_job(
        self, job: dict, now: datetime, cutoff: datetime
    ) -> RawJob | None:
        try:
            millis = (job.get("v5_processed_job_data") or {}).get(
                "estimated_publish_date_millis"
            )
            posted_at = datetime.fromtimestamp(millis / 1000, tz=UTC) if millis else None
        except (TypeError, ValueError):
            posted_at = None

        if posted_at is not None and posted_at < cutoff:
            return None

        external_id = str(job.get("objectID") or "")
        if not external_id:
            return None

        source_url = job.get("apply_url") or ""
        company = (job.get("v5_processed_job_data") or {}).get("company_name", "")

        return RawJob(
            source=self.source_name,
            external_id=external_id,
            source_url=source_url,
            raw_payload=job,
            company_slug=_slugify(company) if company else "",
            scraped_at=now,
        )

    async def scrape_all(self) -> list[RawJob]:
        cutoff = datetime.now(UTC) - timedelta(hours=settings.freshness_window_hours)
        now = datetime.now(UTC)
        base_url = settings.hiringcafe_feed_url.rstrip("/")

        try:
            html = await self._fetch(base_url)
        except Exception as exc:
            _hc_log.error("error fetching HiringCafe page 1: %s", exc)
            return []

        first_jobs, total, page_size = self._parse_page(html)
        total_pages = min(math.ceil(total / max(page_size, 1)), _HC_MAX_PAGES)

        results: list[RawJob] = []
        for job in first_jobs:
            raw = self._to_raw_job(job, now, cutoff)
            if raw:
                results.append(raw)

        if total_pages <= 1:
            return results

        sem = asyncio.Semaphore(3)

        async def _fetch_page(n: int) -> list[RawJob]:
            async with sem:
                url = f"{base_url}?page={n}"
                try:
                    page_html = await self._fetch(url)
                except Exception as exc:
                    _hc_log.warning("failed to fetch HiringCafe page %d: %s", n, exc)
                    return []
                jobs, _, _ = self._parse_page(page_html)
                return [r for job in jobs if (r := self._to_raw_job(job, now, cutoff))]

        pages = await asyncio.gather(*[_fetch_page(n) for n in range(2, total_pages + 1)])
        for batch in pages:
            results.extend(batch)

        _hc_log.info("HiringCafe scraped %d fresh jobs across %d pages", len(results), total_pages)
        return results

    async def scrape_company(self, company_slug: str) -> list[RawJob]:
        raise NotImplementedError("HiringCafeScraper does not support per-company scraping")

    async def scrape_companies(self, company_slugs: list[str]) -> list[RawJob]:
        return await self.scrape_all()


# ─────────────────────────────────────────────────────────────────────────────
# Registry
# ─────────────────────────────────────────────────────────────────────────────

FEED_REGISTRY: dict[str, type[BaseScraper]] = {
    "simplify":    SimplifyScraper,
    "yc":          YCScraper,
    "jobright":    JobrightScraper,
    "hiringcafe":  HiringCafeScraper,
}
