# CareerOS — Phase-by-Phase Implementation Plan

**Version:** 0.5.0
**Last updated:** May 2026
**Format:** Instructions only — no code. Pass each task to VS Code Claude extension.

---

## How to Use This Document

Each phase has numbered tasks in execution order.
Each task is a self-contained instruction block you paste into VS Code Claude.
Complete all tasks in a phase before starting the next phase.
Test checkpoints are marked clearly — do not skip them.

---

---

# PHASE 3 — Data Pipeline (Active)

**Goal:** Automatic, domain-diverse, 24-hour-fresh job ingestion
from all sources without any hardcoded company lists.

**Done already:**
- GreenhouseScraper (greenhouse.py)
- LeverScraper (lever.py)
- JobNormalizer (rule-based, sync)
- IngestionPipeline with deduplication
- careeros ingest-jobs CLI command (tested, working)

**Phase complete when:**
`careeros ingest` runs without arguments, discovers companies
automatically, ingests fresh jobs from all sources, shows a domain
breakdown in the output, and is idempotent on re-run.

---

## Task 3.1 — config/settings.py

**File to create:** `config/settings.py`

**What it does:**
Central configuration for the entire CareerOS system using
pydantic-settings. Reads from environment variables and .env file.
No hardcoded values except sensible defaults.

**What to include:**
- Database connection string
- Groq API key and base URL (free LLM for development)
- OpenAI API key (for embeddings in Phase 4)
- LLM provider flag: "groq" | "anthropic" | "ollama"
- LLM model name (default: llama-3.3-70b-versatile)
- LLM max concurrency for batch normalization (default: 20)
- Embedding model name and dimensions
- Scraping concurrency limit (default: 10)
- DB batch size for inserts (default: 50)
- Freshness window in hours (default: 24)
- Number of company slugs to sample per ATS per run (default: 500)
- Domain-balanced sampling toggle (default: True)
- Sitemap URLs for Greenhouse, Lever, and Ashby
- Feed source URLs for Simplify, YC, and Jobright
- APScheduler settings: hour and minute for daily trigger (default: 2am)
- A module-level singleton: settings = Settings()
- A module docstring explaining this is the single source of truth
  for all configuration

**No sources.json. All source URLs live here.**

---

## Task 3.2 — .env.example

**File to create:** `config/.env.example`

**What it does:**
Template showing every environment variable CareerOS needs.
This file is committed to git. The real .env is gitignored.

**What to include:**
- DATABASE_URL with placeholder value
- GROQ_API_KEY with placeholder (get free key at console.groq.com)
- OPENAI_API_KEY with placeholder (needed for Phase 4 embeddings)
- LLM_PROVIDER defaulting to "groq"
- LLM_MODEL defaulting to "llama-3.3-70b-versatile"
- FRESHNESS_HOURS defaulting to 24
- SLUGS_PER_ATS defaulting to 500
- A comment at the top explaining: copy this file to .env and fill values
- A comment explaining Groq is free during development

**Also update your real .env file with:**
- GROQ_API_KEY=your_actual_key (get from console.groq.com, free)
- LLM_PROVIDER=groq
- LLM_MODEL=llama-3.3-70b-versatile

---

## Task 3.3 — core/collectors/base.py (update)

**File to update:** `core/collectors/base.py`

**What changes:**
Add a ScraperRegistry class to the existing file.
Do not remove or change BaseScraper or RawJob — only add.

**What ScraperRegistry does:**
- Stores a mapping of source_name → scraper class
- register(name, cls): adds a scraper to the registry
- get(name): returns the scraper class for a given source name
- all_names(): returns list of all registered source names
- Raises a clear KeyError with helpful message if name not found

**Why:** The pipeline and CLI will import from the registry instead
of importing scraper classes directly. Adding a new source should mean:
1. Build one scraper class
2. Add one registry entry
3. No pipeline rewrite

---

## Task 3.4 — core/collectors/ats_scrapers.py (new file)

Create the file `core/collectors/ats_scrapers.py` for the CareerOS project.

This file contains all ATS scrapers (company slug → jobs) in one place
with a self-registering registry. The individual greenhouse.py, lever.py,
and ashby.py files have been deleted — build everything fresh here.

SCRAPER REQUIREMENTS (apply to all three scrapers)

All three scrapers must:
- Extend BaseScraper from core.collectors.base
- Use httpx.AsyncClient for all HTTP calls
- Accept optional httpx.AsyncClient in __init__ for testing
- Implement async context manager (__aenter__ / __aexit__)
  that opens and closes the httpx client
- Implement scrape_company(slug) and scrape_companies(slugs)
- Gate scrape_companies with asyncio.Semaphore(settings.scrape_concurrency)
  using asyncio.gather for concurrency
- Use tenacity for retry: max 3 attempts, exponential backoff
  starting at 1 second, retry on httpx.TimeoutException and
  httpx.HTTPStatusError with 5xx status only
- Apply 24-hour freshness filter: check posted_at timestamp for
  each job before creating a RawJob — if older than
  settings.freshness_hours, skip that job entirely
- On 404: log warning "company not found slug={slug}", return []
- On any other error: log error, return [] — never raise
- Set scraped_at = datetime.now(UTC) on each RawJob
- Logger names: careeros.collectors.greenhouse,
                careeros.collectors.lever,
                careeros.collectors.ashby

**GreenhouseScraper**

SOURCE = "greenhouse"

API endpoint:
  GET https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true

Response shape:
  { "jobs": [ { "id": int, "title": str, "absolute_url": str,
    "location": {"name": str}, "content": str (HTML),
    "updated_at": str (ISO 8601), "first_published": str (ISO 8601) } ] }

Field mapping:
  external_id  = str(job["id"])
  source_url   = job["absolute_url"]
  raw_payload  = full job dict
  posted_at    = parse job["first_published"] or job["updated_at"]

24h filter: parse posted_at from first_published field (ISO 8601 string).
If missing: accept the job (benefit of doubt).

**LeverScraper**

SOURCE = "lever"

API endpoints (try US first, fall back to EU):
  GET https://api.lever.co/v0/postings/{slug}?mode=json
  GET https://api.eu.lever.co/v0/postings/{slug}?mode=json

Response shape: root is a JSON array (not wrapped in a key)
  [ { "id": str (UUID), "text": str, "hostedUrl": str,
      "categories": {"location": str, "team": str},
      "createdAt": int (unix milliseconds),
      "descriptionPlain": str } ]

Field mapping:
  external_id  = job["id"]
  source_url   = job["hostedUrl"]
  raw_payload  = full job dict
  posted_at    = datetime.fromtimestamp(job["createdAt"] / 1000, UTC)

24h filter: convert createdAt (unix ms) to datetime, compare to cutoff.

EU fallback: if US endpoint returns 404, try EU endpoint before
giving up. If both 404: return []. Log which endpoint succeeded.

**AshbyScraper**

SOURCE = "ashby"

IMPORTANT: Ashby uses POST, not GET.

API endpoint:
  POST https://api.ashbyhq.com/posting-api/job-board/{slug}
  Headers: Content-Type: application/json
  Body: {}  (empty JSON object)

Response shape:
  { "success": bool,
    "jobs": [ { "id": str, "title": str, "locationName": str,
      "employmentType": str, "isRemote": bool,
      "descriptionHtml": str, "publishedAt": str (ISO 8601),
      "jobUrl": str } ] }

Field mapping:
  external_id  = job["id"]
  source_url   = job["jobUrl"]
  raw_payload  = full job dict
  posted_at    = parse job["publishedAt"] (ISO 8601)

On success=False: company not found, return [].
On success=True: process jobs array.

24h filter: parse publishedAt (ISO 8601 string), compare to cutoff.

**ATS_REGISTRY**

At the bottom of the file, after all three classes:

ATS_REGISTRY: dict[str, type[BaseScraper]] = {
    "greenhouse": GreenhouseScraper,
    "lever":      LeverScraper,
    "ashby":      AshbyScraper,
}

The pipeline and CLI import ATS_REGISTRY only.
They never import the scraper classes directly.

**Imports needed**

from config.settings import settings
from core.collectors.base import BaseScraper, RawJob
Standard library: asyncio, datetime, logging, re
Third party: httpx, tenacity


Also update cli/commands/ingest.py

Find the _build_scraper() function.
Change imports from:
  from core.collectors.greenhouse import GreenhouseScraper
  from core.collectors.lever import LeverScraper
To:
  from core.collectors.ats_scrapers import ATS_REGISTRY

Change _build_scraper(source) to:
  if source not in ATS_REGISTRY:
      console.print(f"Unknown source: {source}")
      raise typer.Exit(1)
  return ATS_REGISTRY[source]()


## Task 3.6 — core/collectors/feed_scrapers.py (new file)

**File to create:** `core/collectors/feed_scrapers.py`

**What it does:**
All feed-based scrapers that aggregate across thousands of companies
without needing company slugs. One file, all feeds, one registry.

**Two scrapers to build:**

SimplifyScraper:
  - Source: GitHub raw markdown (simplify_url from settings)
  - The file is a README with an HTML table of job postings
  - Parse with selectolax: find all tbody tr rows
  - Each row has 5 cells: company, role, location, apply_link, age
  - Age cell contains strings like "5d", "2w", "today", "3h"
  - Convert age to absolute datetime then apply 24h filter
  - external_id: slugify company+role string (re.sub non-alphanumeric)
  - source_url: first href found in apply cell
  - raw_payload: {"company": ..., "role": ..., "location": ..., "age": ...}
  - scrape_all() is the primary method, scrape_company() raises NotImplementedError

HiringCafeScraper:
  - Source: hiring.cafe (hiringcafe_feed_url from settings)
  - Page embeds job data as JSON in script#__NEXT_DATA__ tag
  - Parse HTML with selectolax, find that script tag, json.loads()
  - Navigate to: data["props"]["pageProps"]["ssrHits"]
  - Also read ssrTotalCount and ssrPageSize to determine pagination
  - Paginate up to 40 pages; use Semaphore(3) for concurrent page fetches
  - Freshness filter: v5_processed_job_data["estimated_publish_date_millis"] (unix ms)
  - external_id: str(job["objectID"])
  - source_url: job["apply_url"]
  - raw_payload: full job dict (includes v5_processed_job_data, enriched_company_data,
    job_information — these are used directly by the normalizer)
  - scrape_all() primary, scrape_company() raises NotImplementedError
  - User-Agent header required: "Mozilla/5.0 (compatible; CareerOS/1.0)"

**Both scrapers:**
- Extend BaseScraper
- Implement async context manager (manages httpx client lifecycle)
- Use tenacity retry: max 3 attempts, exponential backoff, on timeout + 5xx
- Use Semaphore from settings.scrape_concurrency
- Log with careeros.collectors.{source_name}
- scrape_companies() calls scrape_all() (ignores slug list for feeds)

**FEED_REGISTRY dict at bottom:**
Maps "simplify", "hiringcafe" to their classes.

---

## Task 3.7 — core/normalization/job_normalizer.py (rewrite)

File to rewrite: core/normalization/job_normalizer.py
What changes: LLM extraction is removed entirely. Normalization is split by source — HiringCafe jobs use pre-enriched fields directly from the API response; all other sources use fast rule-based extraction. No external API calls, no rate limits, no cost.
Keep from existing file:

NormalizedJob dataclass (same fields, no changes)
HTML cleaning logic using selectolax
work_location rule-based extraction
employment_type rule-based extraction
salary regex extraction

Remove from existing file:

All hardcoded SKILL_KEYWORDS list
All hardcoded domain keyword matching
All hardcoded seniority keyword matching
All LLM client code, LLMExtraction dataclass, _extract_with_llm()


Add: HiringCafe direct field mapping
HiringCafe's raw_payload is pre-enriched. Map fields directly — no inference needed:
pythonv5   = raw.raw_payload.get("v5_processed_job_data") or {}
enr  = raw.raw_payload.get("enriched_company_data") or {}
info = raw.raw_payload.get("job_information") or {}

title          = info.get("title", "")
company        = v5.get("company_name", "")
location       = v5.get("formatted_workplace_location", "")
seniority      = v5.get("seniority_level", "")          # already normalized string
workplace_type = v5.get("workplace_type", "")            # remote / hybrid / onsite
skills         = v5.get("technical_tools") or []         # list[str], up to 15
salary_min     = v5.get("yearly_min_compensation")       # int or null
salary_max     = v5.get("yearly_max_compensation")       # int or null
industries     = enr.get("industries") or []
domain         = industries[0] if industries else "other"
company_size   = enr.get("nb_employees")                 # int or null
funding_stage  = enr.get("latest_funding_type", "")

Add: rule-based extraction for non-HiringCafe sources
Used for Simplify, YC, Jobright (low volume, no pre-enriched data).
Source-specific title/company/location extraction:
pythonsimplify:  title=raw_payload["role"],          company=raw_payload["company"]
yc:        title=raw_payload["title"],         company=raw_payload["companyName"]
jobright:  title=raw_payload["job"]["jobTitle"], company=raw_payload["company"]["companyName"]
Seniority — keyword match on title (in priority order):
intern, internship              → "intern"
new grad, entry, junior, jr     → "entry"
senior, sr, lead                → "senior"
staff                           → "staff"
principal                       → "principal"
director, vp, head, chief, cto  → "executive"
(no match)                      → "mid"
Domain — keyword match on title:
software, backend, frontend, fullstack, devops, sre, platform  → "software engineering"
data, analytics, ml, machine learning, ai, scientist           → "data & ai"
mechanical, manufacturing, embedded, hardware, electrical      → "engineering"
finance, accounting, banking, investment, trading              → "finance"
health, medical, clinical, biotech, pharma, nursing            → "healthcare"
product, pm, program manager                                   → "product"
design, ux, ui                                                 → "design"
marketing, growth, seo, content                                → "marketing"
(no match)                                                     → "other"
Skills — not extracted for non-HiringCafe sources. Set to []. Skills data is only reliable when it comes from a structured ATS field, not free-text titles.

Add: async normalize(raw: RawJob) -> NormalizedJob

Branch on raw.source:

"hiringcafe" → use HiringCafe direct mapping above
all others → use rule-based extraction above


Run existing rule-based extractors for work_location, employment_type, salary on all sources (these are reliable from any free-text field)
Return NormalizedJob with all fields populated

Add: async normalize_batch(raws: list[RawJob]) -> list[NormalizedJob]

Run normalize() concurrently with asyncio.gather
Gate with asyncio.Semaphore(settings.normalizer_max_concurrency)
On individual failure: log error, append NormalizedJob with null domain/seniority/skills, continue — never stop the batch
Return list in same order as input

normalize() is async. Pipeline must await it.

---

## Task 3.8 — core/workflows/pipeline.py (update)

**File to update:** `core/workflows/pipeline.py`

**What changes:**

1. Normalizer is now async:
   Replace any sync normalize() loop with:
   normalized = await normalizer.normalize_batch(raw_jobs)
   normalize_batch() handles its own concurrency internally.

2. Add 24-hour safety-net filter in _store_batch():
   Before inserting each job, check posted_at.
   If posted_at is set and older than settings.freshness_hours: skip.
   Increment a skipped_stale counter separate from skipped_duplicate.

3. Add domain breakdown logging after each run:
   Count jobs by domain field, calculate percentages.
   Log the top 6 domains and their percentages.
   This is how you verify domain diversity is working.

4. Add MultiSourcePipeline class (alongside existing IngestionPipeline):
   Accepts: list of source configs (name + scraper + slug list or feed flag)
   run() method: runs each source, collects IngestionResult per source
   Returns: dict[source_name → IngestionResult]
   Logs per-source results.

5. IngestionResult dataclass: add stale_filtered field (int)
   to track how many jobs were dropped by the 24h filter.

**Do not remove IngestionPipeline — keep it for single-source use.**

---

## Task 3.9 — cli/commands/ingest.py (update)

Task 3.9 — cli/commands/ingest.py (update)
File to update: cli/commands/ingest.py
What changes:

Add new command function ingest_all() (keep ingest_jobs intact):

No required arguments
Optional --sources flag: comma-separated source names to run (default: all sources)
Optional --dry-run flag: scrape and normalize but do not write to DB


ingest_all() flow:

Import FEED_REGISTRY from core.collectors.feed_scrapers
No SitemapDiscovery, no ATS_REGISTRY — feed scrapers are the entire pipeline
Build source configs for all enabled feed sources: Simplify, HiringCafe
Run MultiSourcePipeline
Print per-source Rich table showing:
Source | Scraped | Normalized | Inserted | Skipped | Stale
Print domain breakdown table


Register ingest_all in cli/main.py as "ingest" command:

careeros ingest — new primary command
careeros ingest-jobs — keep for backward compatibility

---

## Task 3.10 — core/scheduler/daily_ingest.py (new file)

**File to create:** `core/scheduler/daily_ingest.py`

**What it does:**
Runs careeros ingest automatically every day at 2am without
requiring any manual trigger. Uses APScheduler.

**What to include:**
- APScheduler BackgroundScheduler setup
- Job: run the full multi-source ingestion pipeline
- Schedule: daily at settings.ingest_hour:settings.ingest_minute
- Start function: start_scheduler() → starts scheduler in background
- Stop function: stop_scheduler() → graceful shutdown
- Logging: log when scheduler starts, when job runs, when job completes
- Error handling: if a scheduled run fails, log the full traceback
  and continue — do not crash the scheduler
- The scheduled job calls the same pipeline as careeros ingest
  (no duplication — both CLI and scheduler use same pipeline code)

**Not wired up yet in Phase 3:**
The scheduler will be started from the FastAPI app in Phase 9.
For now it exists as a standalone module that can be imported.

---

## Phase 3 Test Sequence

Run these in order after completing all tasks above.

**Test 1 — Settings load correctly:**
```
python -c "from config.settings import settings; print(settings.database_url[:20])""
```
Should print the start of your DB URL without error.

**Test 2 — Normalizer works (rule-based, no LLM):**
```
python -c "
import asyncio
from core.normalization.job_normalizer import JobNormalizer
from core.collectors.base import RawJob
from datetime import datetime, timezone
raw = RawJob(
    source='yc',
    external_id='test-001',
    source_url='https://example.com',
    raw_payload={
        'title': 'Senior Mechanical Engineer',
        'companyName': 'Relativity Space',
        'location': 'Long Beach, CA',
    },
    company_slug='relativity-space',
    scraped_at=datetime.now(timezone.utc),
)
n = JobNormalizer()
result = asyncio.run(n.normalize(raw))
print('domain:', result.domain)
print('seniority:', result.seniority)
print('skills:', result.skills)
"
```
Expected: domain=engineering, seniority=senior, skills=[] (rule-based, no skills for non-HiringCafe).

**Test 3 — HiringCafe normalizer uses pre-enriched fields:**
```
python -c "
import asyncio
from core.normalization.job_normalizer import JobNormalizer
from core.collectors.base import RawJob
from datetime import datetime, timezone
raw = RawJob(
    source='hiringcafe',
    external_id='test-hc-001',
    source_url='https://example.com',
    raw_payload={
        'job_information': {'title': 'Senior Mechanical Engineer'},
        'v5_processed_job_data': {
            'company_name': 'Boeing',
            'seniority_level': 'senior',
            'workplace_type': 'onsite',
            'technical_tools': ['SolidWorks', 'FEA', 'GD&T'],
            'yearly_min_compensation': 120000,
            'yearly_max_compensation': 160000,
        },
        'enriched_company_data': {
            'industries': ['aerospace'],
            'nb_employees': 150000,
            'latest_funding_type': 'public',
        },
    },
    company_slug='boeing',
    scraped_at=datetime.now(timezone.utc),
)
n = JobNormalizer()
result = asyncio.run(n.normalize(raw))
print('domain:', result.domain)
print('seniority:', result.seniority)
print('skills:', result.skills)
print('salary_min:', result.salary_min)
"
```
Expected: domain=aerospace, seniority=senior, skills=['SolidWorks', 'FEA', 'GD&T'], salary_min=120000.

**Test 4 — Feed scraper works:**
```
careeros ingest --sources simplify --dry-run
```
Should show jobs with varied domains, age-filtered to 24h.

**Test 5 — Full ingest dry run:**
```
careeros ingest --dry-run
```
Should show discovery counts, scraping counts, domain breakdown.
No DB writes.

**Test 6 — Full ingest to DB:**
```
careeros ingest
```
Then immediately:
```
careeros ingest
```
Second run: all jobs skipped (idempotency confirmed).

**Test 7 — Domain diversity validation:**
Open pgAdmin. Run:
```sql
SELECT domain, COUNT(*) as job_count
FROM jobs
GROUP BY domain
ORDER BY job_count DESC
LIMIT 20;
```
Should show at least 8 distinct domains including non-tech ones.
If all results are "software engineering" or "other", the LLM
extraction or sampling is not working correctly.

---
# Phase 3.01 - Resume Ingestion Bridge

Goal: A resume file becomes a structured DB object that can immediately participate in your existing job intelligence system.

Phase complete when: You can run a single CLI command with a DOCX resume and see a resume_id stored in Postgres with extracted skills and raw text.

Task 1 — Resume parsing (extend existing core logic, do not create new architecture layer)

You add resume parsing capability directly inside your existing system without introducing a new subsystem.

What it does:
Convert DOCX resume into structured data usable by embeddings and ranking.

Inputs:

DOCX file path only (ignore PDF for now)
Keep interface simple and file-driven

Outputs:

raw_text (trimmed version of resume)
skills (light extraction)
experience_years (rough heuristic estimate)
current_or_last_role (if detectable)

Constraints:

No LLM usage here
No section-perfect parsing required
No dependency explosion (keep it lightweight)

Logic:

Extract full text from DOCX
Normalize whitespace and remove artifacts
Simple keyword-based skills extraction (use a static minimal list like Python, SQL, ML, Docker, AWS, C++, Java)
Experience estimate using year patterns (e.g., “2020–2024” → ~4 years)

Important rule:
Do not try to “perfect parse resumes”. You are building signal, not formatting correctness.

Task 2 — Resume persistence into existing DB schema

You extend your existing data model usage (do NOT redesign schema yet).

What happens:
Resume becomes a first-class entity in your system like a job.

Stored fields:

raw_text
skills (jsonb)
experience_years
created_at
source = "cli"

Output:
resume_id returned immediately after insert

Constraint:

No new tables unless absolutely required (reuse existing schema patterns if possible)
No normalization pipeline yet for resumes

Task 3 — CLI-based “frontend replacement”

You create a single command that acts as your product input layer.

Command behavior:

Accept DOCX file path
Run parser
Store resume
Print structured summary

Output example:

Resume successfully ingested
resume_id: 12
skills: Python, SQL, AWS, Docker
experience: ~3.5 years
status: ready_for_embedding

This CLI becomes your temporary “frontend”.

Critical constraint:
Do NOT build web upload yet. This CLI is your product interface.

Phase 3.01 Test Check:

DOCX resume parsed correctly
Resume stored in DB
resume_id generated and retrievable
Output reproducible on re-run (idempotent insert or duplicate-safe behavior)
---

# PHASE 4 — Unified Embeddings Layer (Jobs + Resume)

**Goal:**  
Every job and every resume exists in the same vector space so semantic comparison becomes reliable and deterministic.

**Phase complete when:**
- All eligible jobs in `jobs` have embeddings in `job_embeddings`
- Any resume can be embedded via CLI command
- Cosine similarity between resume and jobs produces meaningful ranking:
  same-domain jobs > adjacent-domain jobs > unrelated jobs

---

## Core Design Rule (Do Not Break)

There is ONLY ONE embedding system:

- Same model
- Same preprocessing logic
- Same truncation rules
- Same vector space

Jobs and resumes are just different inputs to the same embedding function.

---

# Task 4.1 — Job Embedding System

**File:** `core/embeddings/job_embedder.py`

---

## What it does

Generates embeddings for all normalized jobs that do not yet have embeddings and stores them in Postgres.

Must be:
- batch-based
- async-safe
- idempotent
- token-safe

---

## JobEmbedder Class

### Responsibilities
- Fetch unembedded jobs
- Construct embedding input text
- Batch embedding API calls
- Store embeddings in DB
- Mark jobs as embedded
- Handle partial failures safely

---

## embed_jobs() Flow

### Step 1 — Fetch jobs

Select:
- `status = 'normalized'`
- NOT EXISTS in `job_embeddings` for current model

---

### Step 2 — Construct embedding input text

For each job: title + company + location + description[:500] + skills
Rules:
- Always preserve: title, company, location
- Truncate description first
- Skills last priority
- Keep format consistent across all jobs

---

### Step 3 — Token safety (critical)

Use `tiktoken`

Constraint:
- Max 8000 tokens per input

If overflow:
1. truncate description
2. then truncate skills
3. NEVER remove title/company/location

---

### Step 4 — Batch embedding

- Batch size: 100 jobs
- Use embedding API batch endpoint
- Process sequential batches

---

### Step 5 — Store results

Insert into:

`job_embeddings`

Fields:
- job_id
- embedding (vector)
- model_name
- created_at

Also update:
- `jobs.status = 'embedded'`

---

### Step 6 — Idempotency

Skip embedding if:
- `(job_id, model_name)` already exists

---

### Step 7 — Logging

Log:
- total jobs found
- batches processed
- embeddings created
- failures (if any)

Pipeline must continue even if one batch fails.

---

# Task 4.2 — Resume Embedding System

**File:** `core/embeddings/resume_embedder.py`

---

## What it does

Embeds a single resume into the same vector space as jobs for similarity search and ranking.

---

## ResumeEmbedder Class

### Responsibilities
- Fetch resume from DB
- Build embedding input text
- Generate embedding
- Store in DB
- Ensure idempotency

---

## embed_resume(resume_id)

---

### Step 1 — Fetch resume

From DB:
- raw_text
- skills
- experience_years
- current/last role (if available)

---

### Step 2 — Construct embedding text
role + skills + raw_text[:1000]
Rules:
- role and skills are highest signal
- raw_text is secondary context
- truncate aggressively if needed

---

### Step 3 — Token safety

Same `tiktoken` logic as jobs:

- Max 8000 tokens
- Preserve:
  - role
  - skills
- truncate raw_text first

---

### Step 4 — Generate embedding

- Must use SAME embedding model as job embedder
- Ensures cosine similarity is meaningful

---

### Step 5 — Store embedding

Insert into:

`resume_embeddings`

Fields:
- resume_id
- embedding
- model_name
- created_at

Also update:
- `resumes.is_embedded = true`

---

### Step 6 — Idempotency

Skip if embedding already exists for:
- resume_id + model_name

---

### Step 7 — Output logs

Print:
- resume_id
- embedding success
- token usage estimate
- extracted skills (debug only)

---

# Task 4.3 — Embedding Consistency Contract

This is a strict system rule.

---

## Rule 1 — Single model

All embeddings must use the same model.

---

## Rule 2 — Same preprocessing philosophy

Jobs:structured metadata → description → skills
---

## Rule 3 — Preserve high-signal fields

Jobs:
- title
- company
- location

Resumes:
- role
- skills

Everything else is secondary.

---

## Rule 4 — No LLM in embedding layer

Embedding layer must remain deterministic.

No classification, no reasoning, no enrichment.

---

# Task 4.4 — CLI Execution Hooks

No frontend yet — CLI is the interface.

---

## Command 1 — Embed jobs

```bash
python -m core.embeddings.job_embedder
```

---

## Task 4.3 — pyproject.toml update

**What to add:**
Add tiktoken to dependencies.
Confirm openai is already there.
Run uv pip install -e . after updating.

---

## Phase 4 Test Sequence

**Test 1 — Embed a sample of jobs:**
```
python -c "
import asyncio
from core.embeddings.job_embedder import JobEmbedder
e = JobEmbedder()
asyncio.run(e.embed_jobs())
"
```
Should log: N jobs embedded across M batches.

**Test 2 — Verify in DB:**
```sql
SELECT COUNT(*) FROM job_embeddings;
SELECT j.title, j.domain, length(je.embedding::text) as vec_length
FROM jobs j
JOIN job_embeddings je ON je.job_id = j.id
LIMIT 5;
```
Should show embeddings exist and are non-null.

**Test 3 — Cosine similarity sanity check:**
```sql
SELECT j1.title, j2.title,
       1 - (je1.embedding <=> je2.embedding) as similarity
FROM job_embeddings je1, job_embeddings je2
JOIN jobs j1 ON j1.id = je1.job_id
JOIN jobs j2 ON j2.id = je2.job_id
WHERE j1.domain = 'mechanical engineering'
  AND j2.domain = 'investment banking'
LIMIT 5;
```
Similarity should be low (< 0.5) between very different domains.
Compare two mechanical engineering jobs — similarity should be high (> 0.7).

---

---

# PHASE 5 — Market Clustering (Agent 1 Complete)

**Goal:** Jobs grouped into 10-15 meaningful role clusters.
Clusters are named, have top skills, and cover all domains in the DB.

**Phase complete when:**
role_clusters table has 10-15 rows with meaningful LLM-generated labels.
At least 2-3 clusters are non-tech (finance, healthcare, engineering, etc.)
depending on what's in the DB.

---

## Task 5.1 — core/clustering/kmeans.py

**File to create:** `core/clustering/kmeans.py`

**What it does:**
Clusters all job embeddings into K groups using KMeans.
Generates a new ClusteringRun with centroids and memberships.

**What to include:**
- ClusteringEngine class
- run_clustering(k=10) method:
    1. Fetch all job_embeddings from DB (job_id + embedding vector)
    2. Convert to numpy matrix
    3. L2-normalize all vectors (normalize each row to unit length)
    4. Run KMeans(n_clusters=k, random_state=42, n_init=10)
    5. Insert ClusteringRun row
    6. For each cluster (0 to k-1):
         centroid = cluster center vector (already L2-normalized space)
         job_ids in this cluster
         top_skills: count skill occurrences across all jobs in cluster,
                     return top 10 most common
         Insert RoleCluster row (label is empty string for now)
         Insert JobClusterMembership row for each job with distance
    7. Call label_clusters() to generate LLM labels
    8. Return ClusteringRun ID
- label_clusters(run_id) method:
    For each cluster in the run:
      Collect: cluster label_hint (top skills + sample job titles)
      Call LLM (Groq): "Given these job titles and skills from the same
      cluster, generate a 3-5 word professional label for this career area"
      Update role_clusters.label with the generated label
      Log: "Cluster {index}: {label}"
- Should be idempotent: check if a run already exists for today,
  skip if so (or add --force flag)

---

## Phase 5 Test Sequence

**Test 1 — Run clustering:**
```
python -c "
import asyncio
from core.clustering.kmeans import ClusteringEngine
e = ClusteringEngine()
run_id = asyncio.run(e.run_clustering(k=10))
print('Run ID:', run_id)
"
```

**Test 2 — Inspect clusters:**
```sql
SELECT cluster_index, label, job_count, top_skills
FROM role_clusters
WHERE run_id = 'your-run-id'
ORDER BY cluster_index;
```
Verify: labels are meaningful, job_counts sum to total jobs,
at least some clusters are non-tech if DB has domain-diverse data.

**Test 3 — Verify memberships:**
```sql
SELECT rc.label, COUNT(*) as member_count
FROM job_cluster_memberships jcm
JOIN role_clusters rc ON rc.id = jcm.cluster_id
GROUP BY rc.label
ORDER BY member_count DESC;
```

---

---

# PHASE 6 — Profile Matching (Agent 2)

**Goal:** Upload a resume, get ranked career clusters with skill gaps,
fit scores, and LLM reasoning.

**Phase complete when:**
After running careeros analyze with a real resume.pdf,
the rankings table has one row per cluster with cosine_similarity,
fit_category, skill_gaps, and reasoning populated.

---

## Task 6.1 — Resume parser (inside career_mapper.py or separate)

**What it does:**
Parses a PDF resume into structured fields.

**What to include:**
- parse_resume(pdf_path) function:
    Use pypdf to extract plain text from all pages
    Call LLM (Groq) to extract structured fields:
      job_titles: list of job titles held
      skills: list of skills mentioned
      years_experience: estimated total years
      education: highest degree + field
      summary: 2-sentence summary of background
    Return a dict with these fields + raw_text
- Insert into resumes table (variant=base)
- Return resume_id

---

## Task 6.2 — core/ranking/career_mapper.py

**File to create:** `core/ranking/career_mapper.py`

**What it does:**
Compares a resume against all role clusters.
Produces ranked fit scores with skill gaps and reasoning.

**What to include:**
- CareerMapper class
- map_resume(resume_id, run_id) method:
    1. Fetch resume from DB, check is_embedded
       If not embedded: call ResumeEmbedder.embed_resume() first
    2. Fetch all role_clusters for run_id
    3. For each cluster:
         cosine_similarity = dot(resume_embedding, cluster_centroid)
         (both are already L2-normalized, so dot product = cosine)
    4. Sort clusters by cosine_similarity descending
    5. Assign rank (1 = best)
    6. Assign fit_category:
         >= 0.75 → strong
         0.50-0.74 → adjacent
         < 0.50 → weak
    7. For each cluster (strong + adjacent only — skip weak):
         Call LLM (Groq) for skill gap analysis:
           Input: resume skills + cluster top_skills + cluster label
           Output: skill_gaps (in cluster, not in resume)
                   skill_matches (in both)
                   reasoning (2-3 sentence explanation)
    8. Insert Ranking rows for all clusters
    9. Return list of Ranking objects sorted by rank

---

## Phase 6 Test Sequence

**Test 1 — Parse a real resume:**
```
python -c "
import asyncio
from core.ranking.career_mapper import CareerMapper
m = CareerMapper()
resume_id = asyncio.run(m.parse_resume('path/to/your/resume.pdf'))
print('Resume ID:', resume_id)
"
```

**Test 2 — Run full mapping:**
```
python -c "
import asyncio
from core.ranking.career_mapper import CareerMapper
m = CareerMapper()
rankings = asyncio.run(m.map_resume('your-resume-id', 'your-run-id'))
for r in rankings[:5]:
    print(r.rank, r.cluster_label, f'{r.cosine_similarity:.3f}', r.fit_category)
"
```

**Test 3 — Verify rankings table:**
```sql
SELECT r.rank, rc.label, r.cosine_similarity, r.fit_category,
       r.skill_gaps, r.skill_matches
FROM rankings r
JOIN role_clusters rc ON rc.id = r.cluster_id
WHERE r.resume_id = 'your-resume-id'
ORDER BY r.rank;
```

---

---

# PHASE 7 — Strategy Engine (Agent 3)

**Goal:** Convert ranked clusters into a specific, actionable plan
with job targets, resume variants, and a weekly roadmap.

**Phase complete when:**
execution_plans and execution_actions tables are populated.
exports/ folder contains career_report.xlsx and resume variant files.

---

## Task 7.1 — core/strategy/execution_engine.py

**File to create:** `core/strategy/execution_engine.py`

**What it does:**
Reads rankings and generates a complete execution plan.
Three possible paths based on fit scores.

**What to include:**

- ExecutionEngine class
- generate_plan(resume_id, run_id, user_goal, timeline) -> ExecutionPlan:

  Path selection logic (rule-based, not LLM):
    If any strong clusters exist → Path A (apply now)
    If no strong but adjacent clusters exist → Path B (build then apply)
    If only weak clusters → Path C (pivot)
    User can override via user_goal and timeline input

  Path A — Apply now:
    Select top 3 strong-fit clusters
    Fetch top 5 fresh jobs (posted_at > now - 24h) per cluster
    Call LLM: generate tailored resume variant for each cluster
    Call LLM: generate 4-week action plan focused on applying
    weekly_actions: apply to N jobs, tweak resume, follow up

  Path B — Build then apply:
    Select top 2 adjacent clusters
    Identify skill gaps (already in rankings)
    Call LLM: generate skill roadmap (what to learn, in what order)
    Call LLM: generate 8-week action plan: weeks 1-4 learning,
              weeks 5-8 applying with new skills
    weekly_actions: specific learning tasks + application targets

  Path C — Pivot:
    User stated a specific target cluster (even if weak fit)
    Call LLM: generate 12-week plan from current profile to target
    weekly_actions: learning, projects, networking, applications

  For all paths:
    Insert ExecutionPlan row (full plan as JSONB)
    Insert ExecutionAction rows (one per weekly action item)
    Write resume variants to exports/resumes/
    Write career_report.json to exports/json/
    Write career_report.xlsx to exports/excel/ (4 tabs:
      Overview, Top Jobs, Resume Variants, Weekly Plan)

---

## Phase 7 Test Sequence

**Test 1 — Generate a plan:**
```
python -c "
import asyncio
from core.strategy.execution_engine import ExecutionEngine
e = ExecutionEngine()
plan = asyncio.run(e.generate_plan(
    resume_id='your-resume-id',
    run_id='your-run-id',
    user_goal='get into data engineering',
    timeline='2 months'
))
print('Path:', plan.path)
print('Weekly actions:', len(plan.weekly_actions))
"
```

**Test 2 — Verify exports exist:**
```
ls exports/json/
ls exports/excel/
ls exports/resumes/
```

**Test 3 — Inspect execution_actions:**
```sql
SELECT week, day, action_type, description, status
FROM execution_actions
WHERE plan_id = 'your-plan-id'
ORDER BY week, day;
```

---

---

# PHASE 8 — CLI Polish

**Goal:** Four clean commands. Guided terminal conversation.
No complex flags or arguments. Works for non-technical domains too.

**Phase complete when:**
careeros analyze with a real resume.pdf leads to a guided
conversation in the terminal that produces a plan. All 4 commands work.

---

## Task 8.1 — core/conversation/prompts.py

**File to create:** `core/conversation/prompts.py`

**What it does:**
All LLM system prompts live here. No inline prompt strings anywhere
else in the codebase. One file, all prompts, easy to tune.

**What to include:**
- DISCOVERY_SYSTEM_PROMPT: guides conversation phase 1
  (understanding user's goal and timeline)
- PATH_SELECTION_SYSTEM_PROMPT: helps user choose A/B/C
- PLAN_GENERATION_SYSTEM_PROMPT: presents the generated plan
- EXECUTION_TRACKING_SYSTEM_PROMPT: tracks progress updates

All prompts include a {context} placeholder where user data is injected.
Context includes: top clusters, fit scores, skill gaps, fresh job count,
user goal, timeline. See system_design.md Section 11 for full structure.
All prompts must be domain-agnostic — no tech-specific language.

---

## Task 8.2 — core/conversation/session.py

**File to create:** `core/conversation/session.py`

**What it does:**
Manages conversation state across multiple messages.
Tracks which phase the conversation is in.

**What to include:**
- ConversationSession dataclass:
    session_id: str
    resume_id: str
    run_id: str
    phase: str  (discovery | path_selection | plan_generation | execution)
    history: list[dict]  (role + content message history)
    user_goal: str | None
    timeline: str | None
    selected_path: str | None  (A | B | C)
    plan_id: str | None
- next_message(user_input) -> str:
    Appends user message to history
    Determines which prompt to use based on phase
    Injects full context into prompt
    Calls LLM (Groq)
    Appends assistant response to history
    Advances phase when appropriate conditions are met
    Returns assistant response text
- Context injection: fetches live data from DB for each message
  (rankings, fresh job count, plan status)

---

## Task 8.3 — cli/commands/analyze.py

**File to create:** `cli/commands/analyze.py`

**What it does:**
The primary user-facing CLI command. Guided conversation in terminal.

**Flow:**
1. Prompt user for resume path (Rich prompt, not a flag)
2. Parse resume → embed → rank → generate initial plan (show progress bar)
3. Open ConversationSession
4. Enter conversation loop:
   - Print assistant message (Rich styled)
   - Read user input (Rich prompt)
   - Call session.next_message(input)
   - Print response
   - Repeat until user types "exit", "done", or "quit"
5. On exit: ask if user wants to export
   If yes: run export automatically

**UI requirements:**
- Use Rich for all output styling
- Assistant messages: left-aligned, subtle color
- User prompt: clearly marked "You:"
- Progress bars during analysis phases
- Never show raw JSON or stack traces to the user
- Friendly error messages if something fails

---

## Task 8.4 — cli/commands/status.py

**File to create:** `cli/commands/status.py`

**What it does:**
Shows current plan progress and this week's actions.

**Output:**
- Plan summary: path type, start date, overall progress
- This week's actions: list with status indicators (✓ done, → pending)
- Next action highlighted
- Days remaining in current week

---

## Task 8.5 — cli/commands/export.py

**File to create:** `cli/commands/export.py`

**What it does:**
Exports the current plan to files.

**What it exports:**
- exports/excel/career_report_{date}.xlsx
  Tab 1: Overview (clusters, fit scores, path selected)
  Tab 2: Top Jobs (title, company, location, source_url, fit score)
  Tab 3: Resume Variants (one section per cluster variant)
  Tab 4: Weekly Plan (week, day, action, status)
- exports/json/career_report_{date}.json (full plan as JSON)
- exports/resumes/ (PDF or text resume variants per cluster)

---

## Task 8.6 — cli/main.py (finalize)

**File to update:** `cli/main.py`

**Final 4 commands:**
- careeros ingest    → ingest_all from cli/commands/ingest.py
- careeros analyze   → analyze from cli/commands/analyze.py
- careeros status    → status from cli/commands/status.py
- careeros export    → export from cli/commands/export.py

Remove: careeros ingest-jobs (or keep as hidden alias)
Remove: careeros version (fold into --version flag on root app)

---

## Phase 8 Test Sequence

**Test 1 — Full flow end to end:**
```
careeros ingest
careeros analyze
```
Use a real resume. Walk through the conversation.
Verify the conversation references your actual clusters and skill gaps.
Verify domain-agnostic language (no tech-only assumptions).

**Test 2 — Status command:**
```
careeros status
```
Should show this week's actions from the generated plan.

**Test 3 — Export command:**
```
careeros export
```
Verify Excel file opens correctly with 4 tabs populated.

---

---

# PHASE 9 — Web App

**Goal:** Full web interface. Deployed on Railway.
Same intelligence as CLI, accessible to everyone.

**Phase complete when:**
https://your-app.railway.app works end to end:
resume upload → analysis → conversation → job dashboard → export.

---

## Task 9.1 — api/main.py (FastAPI app)

**File to create:** `api/main.py`

**What to include:**
- FastAPI app with CORS configured for Next.js frontend
- Lifespan handler: start APScheduler on startup, stop on shutdown
- Include all route routers
- Static file serving for exports/ folder
- Health check endpoint: GET /health
- Start the daily ingest scheduler on app startup

---

## Task 9.2 — api/routes/jobs.py

**File to create:** `api/routes/jobs.py`

**Endpoints:**
- GET /jobs: fresh jobs (last 24h), filterable by domain, work_location,
  seniority. Paginated. Returns job cards.
- GET /jobs/{id}: single job detail
- GET /jobs/clusters: all role clusters with job counts

---

## Task 9.3 — api/routes/resume.py

**File to create:** `api/routes/resume.py`

**Endpoints:**
- POST /resume/upload: accepts PDF file, parses, embeds, ranks
  Returns: resume_id, rankings summary
- GET /resume/{id}: resume detail + rankings
- GET /resume/{id}/rankings: full ranked cluster list

---

## Task 9.4 — api/routes/conversation.py

**File to create:** `api/routes/conversation.py`

**Endpoints:**
- POST /conversation/start: creates ConversationSession, returns session_id
  and first assistant message
- POST /conversation/{session_id}/message: sends user message,
  returns assistant response as Server-Sent Events stream
- GET /conversation/{session_id}/context: returns current context panel data
  (clusters, job cards, plan) for the right panel of the split screen

---

## Task 9.5 — Next.js scaffold (web/ folder)

**Directory to create:** `web/`

**What to include:**
- package.json with: next, react, react-dom, typescript,
  tailwindcss, @clerk/nextjs, lucide-react
- next.config.js: API proxy to FastAPI backend
- app/layout.tsx: root layout with ClerkProvider, Inter font
- app/page.tsx: landing page
- app/analyze/page.tsx: resume upload page
- app/session/page.tsx: split screen conversation UI
- app/jobs/page.tsx: job dashboard
- app/roadmap/page.tsx: learning path visualization
- app/profile/page.tsx: resume history and applications

---

## Task 9.6 — UI Components

**Files to create in web/components/:**

ConversationPanel.tsx:
  Chat thread with streaming message display.
  User input at bottom.
  Messages styled distinctly (user vs assistant).

ContextPanel.tsx:
  Right panel that switches content based on conversation phase.
  Phase 1: cluster fit score bars
  Phase 2: job cards for selected cluster
  Phase 3: weekly plan timeline
  Phase 4: resume download buttons

JobCard.tsx:
  Single job card: title, company, location, domain badge,
  seniority badge, posted_at relative time, apply link.

ClusterFitChart.tsx:
  Horizontal bar chart of cluster fit scores.
  Color coded: green (strong), yellow (adjacent), gray (weak).

WeeklyPlan.tsx:
  Week-by-week action list with status toggles.

---

## Task 9.7 — Clerk Auth

**What to configure:**
- Add Clerk to Next.js: wrap app in ClerkProvider
- Protect /session, /jobs, /roadmap, /profile routes
- Allow /analyze without auth (hook them before requiring signup)
- Pass Clerk JWT to FastAPI for authenticated endpoints
- FastAPI middleware: verify Clerk JWT on protected routes

---

## Task 9.8 — Railway Deployment

**What to set up:**
- railway.toml: define two services (api + web) or combined
- Procfile for FastAPI: uvicorn api.main:app
- Environment variables in Railway dashboard (same as .env)
- PostgreSQL addon: Railway provides managed Postgres
- Run schema.sql against Railway Postgres on first deploy
- Set CORS origin to Railway domain in FastAPI settings

---

## Phase 9 Test Sequence

**Test 1 — API health:**
```
curl https://your-app.railway.app/health
```

**Test 2 — Upload resume via API:**
```
curl -X POST https://your-app.railway.app/resume/upload \
  -F "file=@resume.pdf"
```

**Test 3 — Full web flow:**
Open https://your-app.railway.app
Upload resume → walk through conversation → check jobs page → export

---

---

# PHASE 10 — MCP Layer

**Goal:** CareerOS tools available in Claude Desktop.
Natural language interface over all CareerOS intelligence.

**Phase complete when:**
In Claude Desktop, you can say "what jobs match my background?"
and get a real answer from CareerOS data.

---

## Task 10.1 — mcp_server/server.py

**File to create:** `mcp_server/server.py`

**What it does:**
MCP server that exposes CareerOS as tools for Claude Desktop.
Uses the MCP Python SDK.

---

## Task 10.2 — mcp_server/tools/search_jobs.py

**Tool: search_jobs**
Input: query string, optional domain filter, optional seniority filter
Output: top 10 fresh jobs matching the query
Implementation: embed the query string, cosine search against job_embeddings,
filter by posted_at (last 24h), return formatted job list

---

## Task 10.3 — mcp_server/tools/rank_resume.py

**Tool: rank_resume**
Input: resume text (string)
Output: ranked cluster list with fit scores and skill gaps
Implementation: normalize and embed the resume text on the fly,
cosine similarity vs all cluster centroids, return rankings

---

## Task 10.4 — mcp_server/tools/generate_plan.py

**Tool: generate_plan**
Input: resume_id (or resume text), user_goal, timeline
Output: full execution plan summary
Implementation: calls ExecutionEngine.generate_plan()

---

## Task 10.5 — mcp_server/tools/get_status.py

**Tool: get_status**
Input: none (single-user context)
Output: current plan progress, this week's actions, next recommended action

---

## Phase 10 Test Sequence

**Test 1 — MCP server starts:**
```
python mcp_server/server.py
```
Should start without error.

**Test 2 — Claude Desktop integration:**
Add server to Claude Desktop MCP config.
Ask: "What jobs match a mechanical engineer with 3 years experience?"
Should return real jobs from CareerOS DB.

---

---

## Dependency Additions by Phase

```
Phase 3:
  anthropic         (for future prod switch — install now)
  groq              (or use openai SDK with groq base_url)
  apscheduler       daily scheduler

Phase 4:
  tiktoken          token counting for embedding truncation

Phase 5:
  numpy             already installed via scikit-learn
  scikit-learn      already in pyproject.toml

Phase 8:
  No new dependencies

Phase 9:
  # Backend
  python-multipart  file upload support in FastAPI
  sse-starlette     Server-Sent Events for streaming

  # Frontend (in web/package.json)
  next
  @clerk/nextjs
  tailwindcss
  lucide-react

Phase 10:
  mcp               MCP Python SDK
```

Add each to pyproject.toml as the phase begins.
Run uv pip install -e . after each addition.