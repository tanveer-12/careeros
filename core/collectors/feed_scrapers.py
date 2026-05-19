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
import random
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
    m = re.match(r"^(\d+)(h|d|w|mo?)$", s)  # mo? makes the 'o' optional
    if not m:
        return None
    value, unit = int(m.group(1)), m.group(2)
    if unit == "h":
        return now - timedelta(hours=value)
    if unit == "d":
        return now - timedelta(days=value)
    if unit == "w":
        return now - timedelta(weeks=value)
    if unit in ("m", "mo"):
        return now - timedelta(days=value * 30)
    return None


def _is_fresh(posted_at: datetime | None, cutoff: datetime) -> bool:
    if posted_at is None:
        return False  # can't verify freshness, reject
    return posted_at >= cutoff


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
    # no cutoff — Simplify age strings are unreliable, accept all jobs
        now = datetime.now(UTC) - timedelta(settings.freshness_window_hours)
        try:
            html = await self._fetch(settings.simplify_feed_url)
        except Exception as exc:
            _si_log.error("error fetching simplify feed: %s", exc)
            return []

        tree = HTMLParser(html)
        rows = tree.css("tbody tr")
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
# HiringCafeScraper
# ─────────────────────────────────────────────────────────────────────────────

_hc_log = logging.getLogger("careeros.collectors.hiringcafe")
_HC_MAX_PAGES = 10  # per department; 20*25 = 500 jobs max per department

_HC_DEPARTMENTS = [
    "Software Development",
    "Data Science",
    "Mechanical Engineering",
    "Electrical Engineering",
    "Healthcare",
    "Finance",
    "Product Management",
    "Marketing",
    "Sales",
    "Operations",
    "Design",
    "Civil Engineering",
    "Chemical Engineering",
    "Biotech",
    "Accounting",
]
_HC_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]
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
                headers={
                    "User-Agent": random.choice(_HC_USER_AGENTS),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Connection": "keep-alive",
                    "Upgrade-Insecure-Requests": "1",
                },
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
    async def _fetch(self, url: str, params: dict | None = None) -> str:
        await asyncio.sleep(random.uniform(1.0, 2.5))
        r = await self._client.get(
            url,
            params=params,
            headers={"User-Agent": random.choice(_HC_USER_AGENTS)},
        )
        r.raise_for_status()
        return r.text

    def _parse_page(self, html: str) -> tuple[list[dict], int, int]:
        """Returns (jobs, total_count, page_size). Returns empty on parse failure."""
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
    async def _scrape_department(
        self,
        department: str,
        sem: asyncio.Semaphore,
        cutoff: datetime,
        now: datetime,
    ) -> list[RawJob]:
        base_url = "https://hiring.cafe"
        results: list[RawJob] = []

        # fresh client per department — avoids connection pool corruption
        async with httpx.AsyncClient(
            timeout=30.0,
            headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
            },
            follow_redirects=True,
        ) as client:

            async def _fetch_page(n: int) -> str:
                await asyncio.sleep(random.uniform(1.0, 2.5))
                r = await client.get(
                    base_url,
                    params={"departments": department, "page": n},
                    headers={"User-Agent": random.choice(_HC_USER_AGENTS)},
                )
                r.raise_for_status()
                return r.text

            async with sem:
                try:
                    html = await _fetch_page(0)
                except Exception as exc:
                    _hc_log.warning("failed to fetch HiringCafe dept=%r page=0: %s", department, exc)
                    return []

            first_jobs, total, page_size = self._parse_page(html)
            total_pages = min(math.ceil(total / max(page_size, 1)), _HC_MAX_PAGES)

            for job in first_jobs:
                raw = self._to_raw_job(job, now, cutoff)
                if raw:
                    results.append(raw)

            if not results and first_jobs:
                _hc_log.debug("dept=%r page 0 has no fresh jobs, skipping", department)
                return []

            if total_pages <= 1:
                return results

            async def _fetch_page_guarded(n: int) -> list[RawJob]:
                async with sem:
                    try:
                        page_html = await _fetch_page(n)
                    except Exception as exc:
                        _hc_log.warning("failed to fetch HiringCafe dept=%r page=%d: %s", department, n, exc)
                        return []
                    jobs, _, _ = self._parse_page(page_html)
                    batch = [r for job in jobs if (r := self._to_raw_job(job, now, cutoff))]
                    if not batch and jobs:
                        return []
                    return batch

            pages = await asyncio.gather(
                *[_fetch_page_guarded(n) for n in range(1, total_pages)]
            )
            for batch in pages:
                results.extend(batch)

        _hc_log.info("dept=%r scraped %d fresh jobs", department, len(results))
        return results
    
    async def scrape_all(self) -> list[RawJob]:
        cutoff = datetime.now(UTC) - timedelta(hours=settings.freshness_window_hours)
        now = datetime.now(UTC)

        # 3 concurrent department fetches — be gentle, each spawns multiple page fetches
        sem = asyncio.Semaphore(2)

        dept_results = await asyncio.gather(*[
            self._scrape_department(dept, sem, cutoff, now)
            for dept in _HC_DEPARTMENTS
        ])

        # deduplicate across departments by objectID
        seen: set[str] = set()
        deduped: list[RawJob] = []
        for batch in dept_results:
            for job in batch:
                if job.external_id not in seen:
                    seen.add(job.external_id)
                    deduped.append(job)

        _hc_log.info(
            "HiringCafe total: %d unique fresh jobs across %d departments",
            len(deduped),
            len(_HC_DEPARTMENTS),
        )
        return deduped

    async def scrape_company(self, company_slug: str) -> list[RawJob]:
        raise NotImplementedError("HiringCafeScraper does not support per-company scraping")

    async def scrape_companies(self, company_slugs: list[str]) -> list[RawJob]:
        return await self.scrape_all()

# ─────────────────────────────────────────────────────────────────────────────
# DevITJobsScraper
# ─────────────────────────────────────────────────────────────────────────────

_di_log = logging.getLogger("careeros.collectors.devitjobs")
_DI_FEED_URL = "https://devitjobs.uk/job_feed.xml"


def _parse_devit_date(value: str) -> datetime | None:
    """Parse DevITJobs date format: DD.MM.YYYY"""
    if not value:
        return None
    try:
        return datetime.strptime(value.strip(), "%d.%m.%Y").replace(tzinfo=UTC)
    except ValueError:
        try:
            # fallback: try ISO just in case they ever change format
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None


class DevITJobsScraper(BaseScraper):
    """Scrapes DevITJobs XML feed.

    8.9MB feed covering UK + global IT/dev jobs.
    Applies 24h freshness filter on pubdate field.
    Date format is DD.MM.YYYY.
    """

    source_name = "devitjobs"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client
        self._owns_client = client is None

    async def __aenter__(self) -> DevITJobsScraper:
        if self._owns_client:
            self._client = httpx.AsyncClient(
                timeout=60.0,  # large XML file, needs more time
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
    async def _fetch(self) -> str:
        r = await self._client.get(_DI_FEED_URL)
        r.raise_for_status()
        return r.text

    def _parse_feed(self, xml: str, now: datetime, cutoff: datetime) -> list[RawJob]:
        try:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(xml)
        except ET.ParseError as exc:
            _di_log.warning("failed to parse DevITJobs XML: %s", exc)
            return []

        results: list[RawJob] = []
        for job in root.findall("job"):

            def text(tag: str) -> str:
                el = job.find(tag)
                return (el.text or "").strip() if el is not None else ""

            external_id = text("id") or job.get("id", "")
            if not external_id:
                continue

            posted_at = _parse_devit_date(text("pubdate"))
            if not _is_fresh(posted_at, cutoff):
                continue

            title      = text("title") or text("name")
            company    = text("company") or text("company-name")
            location   = text("location")
            country    = text("country")
            salary     = text("salary")
            job_type   = text("jobtype") or text("job-type")
            source_url = text("apply_url") or text("url") or text("link")
            category   = job.get("category", "")

            results.append(RawJob(
                source=self.source_name,
                external_id=external_id,
                source_url=source_url,
                raw_payload={
                    "title":    title,
                    "company":  company,
                    "location": location,
                    "country":  country,
                    "salary":   salary,
                    "job_type": job_type,
                    "category": category,
                    "posted_at": text("pubdate"),
                },
                company_slug=_slugify(company) if company else "",
                scraped_at=now,
            ))

        return results

    async def scrape_all(self) -> list[RawJob]:
        cutoff = datetime.now(UTC) - timedelta(settings.freshness_window_hours)
        now    = datetime.now(UTC)
        try:
            xml = await self._fetch()
        except Exception as exc:
            _di_log.error("error fetching DevITJobs feed: %s", exc)
            return []

        results = self._parse_feed(xml, now, cutoff)
        _di_log.info("DevITJobs scraped %d fresh jobs", len(results))
        return results

    async def scrape_company(self, slug: str) -> list[RawJob]:
        raise NotImplementedError

    async def scrape_companies(self, slugs: list[str]) -> list[RawJob]:
        return await self.scrape_all()
    
# ─────────────────────────────────────────────────────────────────────────────
# TheMuseScraper
# ─────────────────────────────────────────────────────────────────────────────

_tm_log = logging.getLogger("careeros.collectors.themuse")
_TM_PAGES = 10        # 10 pages * 20 jobs = 200 jobs per run
_TM_PER_PAGE = 20

_TM_SENIORITY_MAP = {
    "internship":   "intern",
    "entry":        "entry",
    "mid":          "mid",
    "senior":       "senior",
    "manager":      "senior",
    "director":     "executive",
    "vp":           "executive",
    "executive":    "executive",
}


class TheMuseScraper(BaseScraper):
    """Scrapes TheMuse public API for domain-diverse job samples.

    No date filtering available server-side — used as a random sample
    source for domain diversity, not recency. Deduplication handled by DB.
    """

    source_name = "themuse"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client
        self._owns_client = client is None

    async def __aenter__(self) -> TheMuseScraper:
        if self._owns_client:
            self._client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
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
    async def _fetch_page(self, page: int) -> list[dict]:
        r = await self._client.get(
            "https://www.themuse.com/api/public/jobs",
            params={"page": page, "per_page": _TM_PER_PAGE},
        )
        r.raise_for_status()
        return r.json().get("results", [])

    async def scrape_all(self) -> list[RawJob]:
        now = datetime.now(UTC)
        sem = asyncio.Semaphore(3)

        async def _fetch(page: int) -> list[RawJob]:
            async with sem:
                try:
                    items = await self._fetch_page(page)
                except Exception as exc:
                    _tm_log.warning("failed to fetch TheMuse page %d: %s", page, exc)
                    return []
                results = []
                for job in items:
                    raw = self._to_raw_job(job, now)
                    if raw:
                        results.append(raw)
                return results

        pages = await asyncio.gather(*[_fetch(p) for p in range(1, _TM_PAGES + 1)])
        results = [job for batch in pages for job in batch]
        _tm_log.info("TheMuse scraped %d jobs", len(results))
        return results

    def _to_raw_job(self, job: dict, now: datetime) -> RawJob | None:
        external_id = str(job.get("id", ""))
        if not external_id:
            return None

        source_url = (job.get("refs") or {}).get("landing_page", "")
        company    = (job.get("company") or {}).get("name", "")
        locations  = job.get("locations") or []
        location   = locations[0].get("name", "") if locations else ""
        levels     = job.get("levels") or []
        level_name = levels[0].get("short_name", "").lower() if levels else ""
        pub_str    = job.get("publication_date", "")

        return RawJob(
            source=self.source_name,
            external_id=external_id,
            source_url=source_url,
            raw_payload={
                "title":      job.get("name", ""),
                "company":    company,
                "location":   location,
                "level":      level_name,
                "categories": [c.get("name") for c in (job.get("categories") or [])],
                "posted_at":  pub_str,   # stored here, not as RawJob field
            },
            company_slug=_slugify(company) if company else "",
            scraped_at=now,
        )

    async def scrape_company(self, slug: str) -> list[RawJob]:
        raise NotImplementedError

    async def scrape_companies(self, slugs: list[str]) -> list[RawJob]:
        return await self.scrape_all()


# ─────────────────────────────────────────────────────────────────────────────
# JobicyScraper
# ─────────────────────────────────────────────────────────────────────────────

_jc_log = logging.getLogger("careeros.collectors.jobicy")


class JobicyScraper(BaseScraper):
    """Scrapes Jobicy free public API. No auth required.

    Small volume (~100 jobs) but clean category/industry data.
    Applies 24h freshness filter on pubDate.
    """

    source_name = "jobicy"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client
        self._owns_client = client is None

    async def __aenter__(self) -> JobicyScraper:
        if self._owns_client:
            self._client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
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
    async def _fetch(self) -> list[dict]:
        r = await self._client.get(
            "https://jobicy.com/api/v2/remote-jobs",
            params={"count": 100},
        )
        r.raise_for_status()
        return r.json().get("jobs", [])

    async def scrape_all(self) -> list[RawJob]:
        cutoff = datetime.now(UTC) - timedelta(hours=settings.freshness_window_hours)
        now    = datetime.now(UTC)
        try:
            items = await self._fetch()
        except Exception as exc:
            _jc_log.error("error fetching Jobicy jobs: %s", exc)
            return []

        results: list[RawJob] = []
        for job in items:
            raw = self._to_raw_job(job, now, cutoff)
            if raw:
                results.append(raw)

        _jc_log.info("Jobicy scraped %d fresh jobs", len(results))
        return results

    def _to_raw_job(
        self, job: dict, now: datetime, cutoff: datetime
    ) -> RawJob | None:
        external_id = str(job.get("id", ""))
        if not external_id:
            return None

        pub_str   = job.get("pubDate", "")
        posted_at: datetime | None = None
        if pub_str:
            try:
                posted_at = datetime.fromisoformat(pub_str)
            except ValueError:
                pass

        if not _is_fresh(posted_at, cutoff):
            return None

        industries = job.get("jobIndustry") or []
        domain     = industries[0] if industries else "other"
        levels     = job.get("jobLevel") or []
        seniority  = levels[0].lower() if levels else ""

        return RawJob(
            source=self.source_name,
            external_id=external_id,
            source_url=job.get("url", ""),
            raw_payload={
                "title":     job.get("jobTitle", ""),
                "company":   job.get("companyName", ""),
                "location":  job.get("jobGeo", ""),
                "domain":    domain,
                "seniority": seniority,
                "type":      (job.get("jobType") or [""])[0],
            },
            company_slug=_slugify(job.get("companyName", "")),
            scraped_at=now,
        )

    async def scrape_company(self, slug: str) -> list[RawJob]:
        raise NotImplementedError

    async def scrape_companies(self, slugs: list[str]) -> list[RawJob]:
        return await self.scrape_all()

# ─────────────────────────────────────────────────────────────────────────────
# Registry
# ─────────────────────────────────────────────────────────────────────────────

FEED_REGISTRY: dict[str, type[BaseScraper]] = {
    "simplify":    SimplifyScraper,
    "themuse":    TheMuseScraper,
    "jobicy":     JobicyScraper,
    "devitjobs":  DevITJobsScraper,
}
