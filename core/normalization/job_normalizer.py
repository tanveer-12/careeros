"""
Normalizer: rule-based field extraction for all sources.

HiringCafe jobs use pre-enriched fields from the API response directly.
All other sources (Simplify) use fast keyword-based extraction.
No external API calls, no rate limits, no cost.

Rule-based: work_location · employment_type · salary · HTML strip · seniority · domain
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime

from selectolax.parser import HTMLParser

from config.settings import settings
from core.collectors.base import RawJob

_log = logging.getLogger("careeros.normalization")

_WHITESPACE_RE = re.compile(r"\s+")

# Matches common salary patterns: $120k–$150k, €80,000, $200,000 USD
_SALARY_RE = re.compile(
    r"(?P<sym>[€£¥₹$])\s*"
    r"(?P<lo>[\d,]+(?:\.\d+)?)\s*(?P<lok>[kK])?"
    r"(?:\s*[-–—to]+\s*(?:[€£¥₹$])?\s*"
    r"(?P<hi>[\d,]+(?:\.\d+)?)\s*(?P<hik>[kK])?)?",
)
_CURRENCY_SYMBOL_MAP = {"$": "USD", "€": "EUR", "£": "GBP", "¥": "JPY", "₹": "INR"}
_CURRENCY_CODE_RE = re.compile(r"\b(USD|EUR|GBP|CAD|AUD)\b", re.IGNORECASE)


# ── Dataclass ─────────────────────────────────────────────────────────────────

@dataclass
class NormalizedJob:
    source: str
    external_id: str
    source_url: str
    raw_payload: dict
    scraped_at: datetime
    title: str | None
    company: str | None
    location: str | None
    work_location: str | None    # "remote" | "hybrid" | "onsite"
    employment_type: str | None  # "full_time" | "part_time" | "contract" | "internship" | "other"
    description: str | None      # HTML-stripped plain text
    skills: list[str] = field(default_factory=list)
    domain: str | None = None
    seniority: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str | None = None


# ── Rule-based helpers ────────────────────────────────────────────────────────

def _strip_html(html: str) -> str | None:
    if not html:
        return None
    text = HTMLParser(html).text(separator=" ")
    text = _WHITESPACE_RE.sub(" ", text).strip()
    return text or None


def _slug_to_company(slug: str) -> str | None:
    if not slug:
        return None
    return re.sub(r"[-_]", " ", slug).title()


def _infer_work_location(location: str | None) -> str | None:
    if not location:
        return None
    lower = location.lower()
    if "remote" in lower:
        return "remote"
    if "hybrid" in lower:
        return "hybrid"
    return "onsite"


def _infer_employment_type(title: str | None) -> str | None:
    if not title:
        return "full_time"
    lower = title.lower()
    if "contract" in lower or "contractor" in lower:
        return "contract"
    if "part-time" in lower or "part time" in lower:
        return "part_time"
    if "intern" in lower:
        return "internship"
    return "full_time"


def _parse_salary_num(num_str: str, k_group: str | None) -> int:
    val = float(num_str.replace(",", ""))
    if k_group:
        val *= 1000
    return int(val)


def _extract_salary(text: str | None) -> tuple[int | None, int | None, str | None]:
    if not text:
        return None, None, None

    m = _SALARY_RE.search(text)
    if not m:
        return None, None, None

    salary_min = _parse_salary_num(m.group("lo"), m.group("lok"))
    salary_max = (
        _parse_salary_num(m.group("hi"), m.group("hik")) if m.group("hi") else None
    )
    if salary_max is not None and salary_max < salary_min:
        salary_min, salary_max = salary_max, salary_min

    currency = _CURRENCY_SYMBOL_MAP.get(m.group("sym"), "USD")
    code_m = _CURRENCY_CODE_RE.search(text)
    if code_m:
        currency = code_m.group(1).upper()

    return salary_min, salary_max, currency


# ── Seniority + domain keyword inference ──────────────────────────────────────

# Checked in priority order — first match wins.
_SENIORITY_RULES: list[tuple[list[str], str]] = [
    (["intern", "internship"], "intern"),
    (["new grad", "entry", "junior", "jr"], "entry"),
    (["senior", "sr", "lead"], "senior"),
    (["staff"], "staff"),
    (["principal"], "principal"),
    (["director", "vp", "head", "chief", "cto"], "executive"),
]

_DOMAIN_RULES: list[tuple[list[str], str]] = [
    # software
    (["software", "backend", "frontend", "fullstack", "full stack",
      "devops", "sre", "platform", "web developer", "web engineer",
      "cloud", "mobile", "ios", "android", "react", "python",
      "java ", "golang", "ruby", "php", "typescript", ".net",
      "firmware", "systems engineer", "infrastructure"], "software engineering"),
    # data & ai
    (["data", "analytics", "ml ", "machine learning", "ai ", "scientist",
      "deep learning", "nlp", "computer vision", "data engineer",
      "business intelligence", "bi ", "etl", "spark", "hadoop"], "data & ai"),
    # mechanical / hardware engineering
    (["automation", "controls engineer", "optical", "industrial mechanic",
      "maintenance", "equipment engineer", "systems lead",
      "mechanical", "manufacturing", "embedded", "hardware",
      "electrical", "electronics", "robotics", "aerospace",
      "automotive", "civil", "structural", "materials", "cad"], "engineering"),
    # finance
    (["wealth management", "financial advisor", "finance", "accounting",
      "banker", "banking", "investment", "trading", "quant",
      "actuar", "tax ", "audit", "controller", "treasury", "payroll"], "finance"),
    # healthcare
    (["veterinary", "nurse", "rn ", "lvn", "physician", "psychiatrist",
      "pediatric", "doctor", "therapist", "radiolog", "patholog",
      "dentist", "pharmacist", "health", "medical", "clinical",
      "biotech", "pharma", "life science", "healthcare"], "healthcare"),
    # product
    (["product manager", "product owner", "pm ", " pm,",
      "program manager", "scrum", "agile coach"], "product"),
    # design
    (["design", "ux", "ui ", "u/x", "user experience",
      "user interface", "graphic", "visual design",
      "brand design", "motion design"], "design"),
    # marketing
    (["marketing", "growth", "seo", "content", "copywriter",
      "social media", "brand manager", "campaign", "demand gen",
      "performance market"], "marketing"),
    # sales
    (["sales", "account executive", "account manager",
      "business development", "bdr", "sdr", "revenue",
      "customer success"], "sales"),
    # operations
    (["operations", "supply chain", "logistics", "warehouse",
      "procurement", "facilities", "office manager",
      "document control", "strategy & ops", "delivery"], "operations"),
    # legal / compliance
    (["legal", "counsel", "attorney", "lawyer", "compliance",
      "paralegal", "regulatory"], "legal"),
    # hr / people
    (["recruiter", "recruiting", "talent", "human resources",
      "hr ", "people ops", "compensation", "benefits"], "hr"),
    # customer support
    (["customer support", "customer service", "help desk",
      "technical support", "support engineer", "success manager"], "support"),
    # hospitality / retail / service
    (["host", "hostess", "shift lead", "resort", "hotel",
      "restaurant", "barista", "cashier", "retail",
      "store associate", "customer service"], "hospitality & retail"),
    # art / creative
    (["art direction", "creative director", "animator",
      "illustrator", "photographer", "videographer",
      "content creator", "writer", "editor"], "creative"),
    # management
    (["manager", "director", "head of", "vp ", "vice president",
      "chief", "cto", "cfo", "coo", "ceo", "lead "], "management"),
]


def _infer_seniority(title: str | None) -> str:
    if not title:
        return "mid"
    lower = title.lower()
    for keywords, level in _SENIORITY_RULES:
        if any(kw in lower for kw in keywords):
            return level
    return "mid"


def _infer_domain(title: str | None) -> str:
    if not title:
        return "other"
    lower = title.lower()
    for keywords, domain in _DOMAIN_RULES:
        if any(kw in lower for kw in keywords):
            return domain
    return "other"


# ── Main normalizer ───────────────────────────────────────────────────────────

class JobNormalizer:

    async def normalize(self, raw: RawJob) -> NormalizedJob:
        p = raw.raw_payload

        if raw.source == "hiringcafe":
            v5   = p.get("v5_processed_job_data") or {}
            enr  = p.get("enriched_company_data") or {}
            info = p.get("job_information") or {}

            title          = info.get("title") or None
            company        = v5.get("company_name") or None
            location       = v5.get("formatted_workplace_location") or None
            seniority      = v5.get("seniority_level") or None
            workplace_type = v5.get("workplace_type") or None
            skills         = list(v5.get("technical_tools") or [])
            salary_min     = v5.get("yearly_min_compensation")
            salary_max     = v5.get("yearly_max_compensation")
            industries     = enr.get("industries") or []
            domain         = industries[0] if industries else "other"

            work_location   = _infer_work_location(workplace_type or location)
            employment_type = _infer_employment_type(title)
            description     = None
            salary_currency = "USD" if (salary_min is not None or salary_max is not None) else None

        else:
            # defaults — may be overridden per source below
            raw_desc  = None
            domain    = None
            seniority = None

            if raw.source == "simplify":
                title    = p.get("role") or None
                company  = p.get("company") or None
                location = p.get("location") or None

            elif raw.source == "themuse":
                title    = p.get("title") or None
                company  = p.get("company") or None
                location = p.get("location") or None

            elif raw.source == "jobicy":
                title     = p.get("title") or None
                company   = p.get("company") or None
                location  = p.get("location") or None
                domain    = (p.get("domain") or "other").lower()    # pre-set by source
                seniority = (p.get("seniority") or "mid").lower()   # pre-set by source

            elif raw.source == "devitjobs":
                title    = p.get("title") or None
                company  = p.get("company") or None
                location = p.get("location") or None

            else:
                title    = p.get("title") or None
                company  = _slug_to_company(getattr(raw, "company_slug", None))
                location = None

            description     = _strip_html(raw_desc or "")
            skills          = []
            work_location   = _infer_work_location(location)
            employment_type = _infer_employment_type(title)
            salary_min, salary_max, salary_currency = _extract_salary(description)

            # fall back to inference if source didn't pre-set these
            if seniority is None:
                seniority = _infer_seniority(title)
            if domain is None:
                domain = _infer_domain(title)

        return NormalizedJob(
            source=raw.source,
            external_id=raw.external_id,
            source_url=raw.source_url,
            raw_payload=raw.raw_payload,
            scraped_at=raw.scraped_at,
            title=title,
            company=company,
            location=location,
            work_location=work_location,
            employment_type=employment_type,
            description=description,
            skills=skills,
            domain=domain,
            seniority=seniority,
            salary_min=salary_min,
            salary_max=salary_max,
            salary_currency=salary_currency,
        )

    async def normalize_batch(self, raws: list[RawJob]) -> list[NormalizedJob]:
        sem = asyncio.Semaphore(settings.normalizer_max_concurrency)

        async def _guarded(raw: RawJob) -> NormalizedJob | None:
            async with sem:
                try:
                    return await self.normalize(raw)
                except Exception as exc:
                    _log.error(
                        "normalize failed for source=%s external_id=%s: %s",
                        raw.source, raw.external_id, exc,
                    )
                    return None

        results = await asyncio.gather(*(_guarded(r) for r in raws))

        normalized: list[NormalizedJob] = []
        for raw, result in zip(raws, results):
            if result is None:
                normalized.append(NormalizedJob(
                    source=raw.source,
                    external_id=raw.external_id,
                    source_url=raw.source_url,
                    raw_payload=raw.raw_payload,
                    scraped_at=raw.scraped_at,
                    title=None,
                    company=None,
                    location=None,
                    work_location=None,
                    employment_type=None,
                    description=None,
                ))
            else:
                normalized.append(result)

        return normalized
