"""
Hybrid async normalizer: rule-based field extraction + LLM for domain/seniority/skills.

Rule-based (free, instant):  work_location · employment_type · salary · HTML strip
LLM-based (Groq during dev): domain · seniority · skills

Provider is controlled entirely by LLM_PROVIDER + LLM_MODEL env vars.
build_llm_client() is the only place provider-specific logic lives.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime

import openai
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

# Full domain taxonomy that the LLM must map to.
_DOMAIN_TAXONOMY = """
Technology: software engineering, backend engineering, frontend engineering,
  mobile engineering, full stack engineering, platform engineering,
  infrastructure engineering, data engineering, machine learning engineering,
  ai research, data science, analytics engineering, business intelligence,
  security engineering, embedded systems, firmware engineering,
  robotics engineering, computer vision, nlp engineering,
  developer relations, technical program management, qa engineering

Physical Engineering: mechanical engineering, electrical engineering, civil engineering,
  structural engineering, aerospace engineering, manufacturing engineering,
  industrial engineering, systems engineering, hardware engineering,
  process engineering, materials engineering, controls engineering,
  automation engineering, chemical engineering

Biomedical & Life Sciences: biomedical engineering, biochemistry, pharmaceutical,
  clinical research, regulatory affairs, medical devices, genomics, bioinformatics,
  lab sciences, research science, applied research, environmental science

Product & Design: product management, technical product management, ux design,
  product design, visual design, brand design, motion design, industrial design,
  user research, content design

Finance & Accounting: investment banking, private equity, venture capital,
  asset management, hedge fund, equity research, financial analysis,
  corporate finance, accounting, audit, tax, risk management, trading,
  quantitative finance, financial technology, insurance, actuarial

Business & Strategy: strategy, management consulting, business operations,
  revenue operations, program management, project management, chief of staff,
  supply chain, logistics, procurement, real estate

Sales & Growth: sales, enterprise sales, sales engineering, business development,
  partnerships, growth, customer success, account management

Marketing & Communications: marketing, product marketing, demand generation,
  content marketing, brand, communications, public relations, social media, seo

People & Talent: human resources, recruiting, talent acquisition, people operations,
  compensation and benefits, learning and development

Legal & Compliance: legal, compliance, privacy, intellectual property, contracts

Healthcare & Clinical: healthcare administration, clinical operations, nursing,
  physician, pharmacy, public health, health informatics, medical writing

Education: education, curriculum design, instructional design, edtech

Government & Nonprofit: government, policy, nonprofit, social impact

Fallback: other
""".strip()

_SYSTEM_PROMPT = f"""You are a job posting classifier. Extract structured metadata from job postings.

Return ONLY valid JSON — no markdown, no explanation, no code blocks.

JSON schema:
{{"domain": "<exact value from taxonomy>", "seniority": "<intern|entry|mid|senior|staff|principal|executive>", "skills": ["skill1", ...]}}

Domain taxonomy:
{_DOMAIN_TAXONOMY}

Seniority guide:
  intern     = internship, co-op, student
  entry      = 0-2 years, analyst, associate, junior, new grad
  mid        = 2-5 years, no explicit seniority modifier
  senior     = senior, sr., lead (IC role)
  staff      = staff-level IC or small-team manager
  principal  = principal, director, senior manager
  executive  = VP, SVP, C-suite, Partner, Managing Director
  Note: "VP" at a bank is staff/principal (IC), not executive.
        "Associate" in consulting is entry, not mid.

Skills rules:
  - Max 15 skills
  - Concrete tools, languages, frameworks, methodologies only
  - No soft skills (no "communication", "teamwork", "leadership")
  - Domain-appropriate: DCF for finance, SolidWorks for mechanical, etc."""


# ── Dataclasses ───────────────────────────────────────────────────────────────

@dataclass
class LLMExtraction:
    domain: str
    seniority: str
    skills: list[str]


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


# ── LLM client factory ────────────────────────────────────────────────────────

def build_llm_client():
    """
    Returns an async LLM client for the configured provider.
    Groq and Ollama use the openai-compatible SDK.
    Anthropic uses its own SDK.
    """
    provider = settings.llm_provider
    if provider == "groq":
        return openai.AsyncOpenAI(
            base_url=settings.groq_base_url,
            api_key=settings.groq_api_key,
        )
    if provider == "ollama":
        return openai.AsyncOpenAI(
            base_url="http://localhost:11434/v1",
            api_key="ollama",
        )
    if provider == "anthropic":
        import anthropic  # optional dependency; only needed when provider=anthropic
        return anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    raise ValueError(f"Unknown LLM provider: {provider!r}. Must be groq | ollama | anthropic")


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


# ── Source-specific payload extraction ────────────────────────────────────────

def _extract_payload(
    raw: RawJob,
) -> tuple[str | None, str | None, str | None, str | None]:
    """Returns (title, company, location, raw_description) for any source."""
    p = raw.raw_payload
    s = raw.source

    if s == "greenhouse":
        title    = p.get("title")
        company  = _slug_to_company(raw.company_slug)
        location = (p.get("location") or {}).get("name")
        desc     = p.get("content")
    elif s == "lever":
        title    = p.get("text")
        company  = _slug_to_company(raw.company_slug)
        location = (p.get("categories") or {}).get("location")
        desc     = p.get("descriptionPlain") or p.get("description")
    elif s == "ashby":
        title    = p.get("title")
        company  = _slug_to_company(raw.company_slug)
        location = p.get("locationName")
        desc     = p.get("descriptionHtml")
    elif s == "simplify":
        title    = p.get("role")
        company  = p.get("company")
        location = p.get("location")
        desc     = None
    elif s == "yc":
        title    = p.get("title")
        company  = p.get("companyName")
        location = p.get("location")
        desc     = p.get("description")
    elif s == "jobright":
        job      = p.get("job") or {}
        comp     = p.get("company") or {}
        title    = job.get("jobTitle")
        company  = comp.get("companyName")
        location = job.get("jobLocation")
        desc     = None
    elif s == "hiringcafe":
        info     = p.get("job_information") or {}
        proc     = p.get("v5_processed_job_data") or {}
        title    = info.get("title")
        company  = proc.get("company_name")
        location = proc.get("formatted_workplace_location")
        desc     = None
    else:
        title    = p.get("title")
        company  = _slug_to_company(raw.company_slug)
        location = None
        desc     = None

    return title or None, company or None, location or None, desc or None


# ── LLM extraction ────────────────────────────────────────────────────────────

_FALLBACK_EXTRACTION = LLMExtraction(domain="other", seniority="mid", skills=[])

_VALID_SENIORITIES = {"intern", "entry", "mid", "senior", "staff", "principal", "executive"}


def _parse_llm_json(content: str) -> dict:
    content = content.strip()
    # Strip accidental markdown code fences
    content = re.sub(r"^```\w*\s*", "", content)
    content = re.sub(r"\s*```$", "", content)
    # Extract first JSON object if there's surrounding text
    m = re.search(r"\{.*\}", content, re.DOTALL)
    return json.loads(m.group() if m else content)


# ── Main normalizer ───────────────────────────────────────────────────────────

class JobNormalizer:

    def __init__(self, client=None) -> None:
        self._client = client or build_llm_client()
        self._llm_lock = asyncio.Lock()
        self._last_llm_call_at = 0.0

    async def _extract_with_llm(
        self, title: str, description: str
    ) -> LLMExtraction:
        await self._wait_for_llm_slot()
        description = description[: settings.llm_description_char_limit]
        user_msg = f"Title: {title}\n\nDescription:\n{description}"
        try:
            client = self._client
            # Detect anthropic SDK by checking for messages.create signature
            if hasattr(client, "messages") and not hasattr(client, "chat"):
                response = await client.messages.create(
                    model=settings.llm_model,
                    max_tokens=settings.llm_max_output_tokens,
                    system=_SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": user_msg}],
                )
                content = response.content[0].text
            else:
                response = await client.chat.completions.create(
                    model=settings.llm_model,
                    messages=[
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": user_msg},
                    ],
                    temperature=0,
                    max_tokens=settings.llm_max_output_tokens,
                )
                content = response.choices[0].message.content

            data = _parse_llm_json(content)
            return LLMExtraction(
                domain=str(data.get("domain", "other")).lower(),
                seniority=(
                    str(data.get("seniority", "mid")).lower()
                    if data.get("seniority", "mid").lower() in _VALID_SENIORITIES
                    else "mid"
                ),
                skills=[str(s) for s in (data.get("skills") or [])[:15]],
            )
        except Exception as exc:
            _log.error("LLM extraction failed for title=%r: %s", title, exc)
            return _FALLBACK_EXTRACTION
        
    async def _wait_for_llm_slot(self) -> None:
        delay = settings.llm_request_delay_seconds
        if delay <= 0:
            return

        async with self._llm_lock:
            now = asyncio.get_running_loop().time()
            elapsed = now - self._last_llm_call_at
            wait_for = delay - elapsed

            if wait_for > 0:
                await asyncio.sleep(wait_for)

            self._last_llm_call_at = asyncio.get_running_loop().time()


    async def normalize(self, raw: RawJob) -> NormalizedJob:
        title, company, location, raw_desc = _extract_payload(raw)
        description = _strip_html(raw_desc or "")
        text_for_rules = description or ""

        work_location   = _infer_work_location(location)
        employment_type = _infer_employment_type(title)
        salary_min, salary_max, salary_currency = _extract_salary(text_for_rules)

        llm = await self._extract_with_llm(title or "", description or "")

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
            skills=llm.skills,
            domain=llm.domain,
            seniority=llm.seniority,
            salary_min=salary_min,
            salary_max=salary_max,
            salary_currency=salary_currency,
        )

    async def normalize_batch(self, raws: list[RawJob]) -> list[NormalizedJob]:
        sem = asyncio.Semaphore(settings.llm_max_concurrency)

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
