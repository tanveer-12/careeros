"""Normalizer: Remotive-only field extraction.

Rule-based: employment_type · salary · HTML strip · seniority · domain
All Remotive jobs are remote — work_location is always "remote".
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime

from selectolax.parser import HTMLParser

from core.collectors.base import RawJob

_log = logging.getLogger("lumia.normalization")

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


# ── Dataclass ──────────────────────────────────────────────────────────────────

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
    work_location: str | None    # always "remote" for Remotive
    employment_type: str | None  # "full_time" | "part_time" | "contract" | "internship" | "freelance"
    description: str | None      # HTML-stripped plain text
    skills: list[str] = field(default_factory=list)
    domain: str | None = None
    seniority: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str | None = None


# ── Helpers ────────────────────────────────────────────────────────────────────

def _strip_html(raw: str) -> str | None:
    if not raw:
        return None
    text = HTMLParser(raw).text(separator=" ")
    text = _WHITESPACE_RE.sub(" ", text).strip()
    return text or None


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


# ── Seniority + domain inference ───────────────────────────────────────────────

_SENIORITY_RULES: list[tuple[list[str], str]] = [
    (["intern", "internship"], "intern"),
    (["new grad", "entry", "junior", "jr"], "entry"),
    (["senior", "sr", "lead"], "senior"),
    (["staff"], "staff"),
    (["principal"], "principal"),
    (["director", "vp", "head", "chief", "cto"], "executive"),
]

_DOMAIN_RULES: list[tuple[list[str], str]] = [
    (["software", "backend", "frontend", "fullstack", "full stack",
      "devops", "sre", "platform", "web developer", "web engineer",
      "cloud", "mobile", "ios", "android", "react", "python",
      "java ", "golang", "ruby", "php", "typescript", ".net",
      "firmware", "systems engineer", "infrastructure"], "software engineering"),
    (["data", "analytics", "ml ", "machine learning", "ai ", "scientist",
      "deep learning", "nlp", "computer vision", "data engineer",
      "business intelligence", "bi ", "etl", "spark", "hadoop"], "data & ai"),
    (["mechanical", "manufacturing", "embedded", "hardware",
      "electrical", "electronics", "robotics", "aerospace",
      "automotive", "civil", "structural", "materials", "cad"], "engineering"),
    (["finance", "accounting", "banking", "investment", "trading",
      "quant", "actuar", "tax ", "audit", "controller", "treasury", "payroll"], "finance"),
    (["nurse", "physician", "doctor", "therapist", "health", "medical",
      "clinical", "biotech", "pharma", "healthcare"], "healthcare"),
    (["product manager", "product owner", "pm ", " pm,",
      "program manager", "scrum", "agile coach"], "product"),
    (["design", "ux", "ui ", "user experience", "user interface",
      "graphic", "visual design"], "design"),
    (["marketing", "growth", "seo", "content", "copywriter",
      "social media", "campaign", "demand gen"], "marketing"),
    (["sales", "account executive", "account manager",
      "business development", "bdr", "sdr", "revenue",
      "customer success"], "sales"),
    (["operations", "supply chain", "logistics", "warehouse",
      "procurement", "facilities", "office manager"], "operations"),
    (["legal", "counsel", "attorney", "lawyer", "compliance",
      "paralegal", "regulatory"], "legal"),
    (["recruiter", "recruiting", "talent", "human resources",
      "hr ", "people ops", "compensation", "benefits"], "hr"),
    (["customer support", "customer service", "help desk",
      "technical support", "support engineer"], "support"),
    (["writer", "editor", "animator", "illustrator",
      "photographer", "videographer", "content creator"], "creative"),
]

_REMOTIVE_CATEGORY_MAP: dict[str, str] = {
    "software development": "software engineering",
    "devops / sysadmin":    "software engineering",
    "backend":              "software engineering",
    "frontend":             "software engineering",
    "qa":                   "software engineering",
    "data":                 "data & ai",
    "product":              "product",
    "design":               "design",
    "marketing":            "marketing",
    "sales / business":     "sales",
    "sales":                "sales",
    "finance / legal":      "finance",
    "human resources":      "hr",
    "project management":   "operations",
    "business":             "operations",
    "customer service":     "support",
    "writing":              "creative",
    "teaching / education": "other",
    "teaching":             "other",
    "all others":           "other",
}


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


# ── Normalizer ─────────────────────────────────────────────────────────────────

class JobNormalizer:

    async def normalize(self, raw: RawJob) -> NormalizedJob:
        p = raw.raw_payload

        title   = p.get("title") or None
        company = p.get("company_name") or None
        location = p.get("candidate_required_location") or None

        work_location   = "remote"
        employment_type = (p.get("job_type") or "full_time").lower() or "full_time"
        description     = _strip_html(p.get("description") or "")
        skills: list[str] = []

        salary_min, salary_max, salary_currency = _extract_salary(p.get("salary"))

        domain   = _REMOTIVE_CATEGORY_MAP.get(
            (p.get("category") or "").lower()
        ) or _infer_domain(title)
        seniority = _infer_seniority(title)

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
        async def _guarded(raw: RawJob) -> NormalizedJob | None:
            try:
                return await self.normalize(raw)
            except Exception as exc:
                _log.error(
                    "normalize failed for external_id=%s: %s",
                    raw.external_id, exc,
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
