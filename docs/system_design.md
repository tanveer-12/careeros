# CareerOS — System Design

**Version:** 0.5.0
**Status:** Active Development — Phase 3 (Data Pipeline)
**Last updated:** May 2026

---

## 0. Mission

CareerOS is not a job board. It is not a resume optimizer. It is not a chatbot.
CareerOS is a web-first product. The CLI exists as a developer and automation interface for running the same backend workflows locally.

It is a personal career intelligence system that answers three questions nobody
else answers well:

```
1. Where do I actually stand in today's job market?
2. What is the most efficient path to the job I want?
3. What should I do this week to get there?
```

Every existing platform takes your resume, ranks jobs by keyword match, and
leaves you to figure out the rest. CareerOS starts where they stop. It works
for software engineers, investment bankers, mechanical engineers, nurses,
consultants, and robotics researchers equally — zero domain bias by design.

---

## 1. Who This Is For

### Fresher / New Grad
```
Problem:
  Has skills but doesn't know which roles to target
  Applies randomly, gets no callbacks
  Doesn't know what to learn next

CareerOS gives them:
  "The market has 3 clusters you can realistically enter today"
  "Data Engineering: you're 65% there. Missing: dbt, Airflow, cloud platform"
  "8 companies posted new grad roles in this cluster today"
  "Learn X in 3 weeks → apply to these 5 → here's the tailored resume"
  Week-by-week: what to learn, what to build, what to apply to
```

### Mid-Level Professional (any domain)
```
Problem:
  Stuck at current level, unclear what moves the needle
  Resume is generic, not positioned for specific targets
  Doesn't know which companies are worth targeting

CareerOS gives them:
  "Your profile maps to Senior Financial Analyst and Corporate Strategy"
  "For Corporate Strategy: you need M&A exposure + one more vertical"
  "These 12 companies posted relevant roles in the last 24 hours"
  "Your resume positions you as a generalist — here's a variant per cluster"
```

---

## 2. Core Design Principles

### No Hardcoding
Company lists, job slugs, and domain mappings are never hardcoded.
Companies are discovered automatically from ATS public sitemaps.
Domains are extracted by LLM, not keyword dictionaries.
The system adapts to any industry without code changes.

### 24-Hour Freshness Window
CareerOS only ingests jobs posted within the last 24 hours.
This is not a job archive. It is a live market signal.
Every run reflects what employers want right now, today.
Older jobs are filtered at the scraper level before touching the DB.

### Domain Agnosticism
The intelligence layer makes zero assumptions about what field a user works in.
Clustering, ranking, and strategy work identically for a software engineer,
a financial analyst, a mechanical engineer, a clinical researcher, or a
marketing director. Domain diversity in the DB is enforced by the discovery layer.

### Zero Manual Maintenance
No CSV files. No slug lists. No keyword dictionaries to update.
The system self-maintains through sitemap discovery and LLM extraction.

### Free LLM During Development
All LLM calls use Groq (free tier) during development.
The LLM client is provider-agnostic — swap to production models
by changing two environment variables, zero code changes.

---

## 3. System Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│  LAYER 1 — DATA COLLECTION  (runs daily, fully automatic)            │
│                                                                      │
│  Discovery:  ATS sitemaps → company slugs (auto-discovered)          │
│  ATS:        Greenhouse · Lever · Ashby                              │
│  Feeds:      Simplify · YC · Jobright · HiringCafe                   │
│  Filter:     posted_at within last 24 hours only                     │
│  Normalize:  RawJob → NormalizedJob (rules + LLM)                    │
│  Store:      PostgreSQL with deduplication                           │
│                                                                      │
│  Output: fresh, normalized, domain-diverse jobs from today           │
└──────────────────────────────┬───────────────────────────────────────┘
                               │ Job[] (24h fresh)
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│  LAYER 2 — MARKET INTELLIGENCE  (Agent 1)                            │
│                                                                      │
│  jobs → embed → KMeans cluster → LLM label                          │
│                                                                      │
│  Output: 10–15 named clusters across ALL domains                     │
│  Clusters emerge from data — never predefined                        │
└──────────────────────────────┬───────────────────────────────────────┘
                               │ RoleCluster[]
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│  LAYER 3 — PROFILE INTELLIGENCE  (Agent 2)                           │
│                                                                      │
│  Resume → embed → cosine similarity vs centroids                     │
│         → LLM skill gap analysis per cluster                         │
│         → fit scoring: strong / adjacent / weak                      │
│                                                                      │
│  Output: Ranking[] with fit scores, gaps, reasoning                  │
└──────────────────────────────┬───────────────────────────────────────┘
                               │ Ranking[]
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│  LAYER 4 — STRATEGY ENGINE  (Agent 3)                                │
│                                                                      │
│  Path A: Apply now   → strong fit → today's jobs → tailored resume   │
│  Path B: Build then  → adjacent fit → skill roadmap → unlock roles   │
│  Path C: Pivot       → weak fit + high interest → 3-month plan       │
│                                                                      │
│  Output: ExecutionPlan with weekly actions, job targets, roadmap     │
└──────────────────────────────┬───────────────────────────────────────┘
                               │ ExecutionPlan
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│  LAYER 5 — INTERFACES                                                │
│                                                                      │
│  CLI (local, developer-first)    Web App (hosted, everyone)          │
│    careeros ingest                 Next.js 14 + FastAPI              │
│    careeros analyze                Conversational + dashboard        │
│    careeros status                 Anthropic-inspired UI             │
│    careeros export                                                   │
│                                   MCP Layer (Phase 10)              │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 4. Collector Architecture

### Structure

```
core/collectors/
    base.py           BaseScraper ABC · RawJob dataclass · ScraperRegistry
    ats_scrapers.py   GreenhouseScraper · LeverScraper · AshbyScraper
                      + ATS_REGISTRY dict
    feed_scrapers.py  SimplifyScraper · YCScraper · JobrightScraper
                      · HiringCafeScraper + FEED_REGISTRY dict
    discovery.py      SitemapDiscovery — auto-discovers company slugs
```

### Why Registry Pattern

Adding a new source = one new class + one dict entry. Nothing else changes.

```
ATS_REGISTRY  = { "greenhouse": ..., "lever": ..., "ashby": ... }
FEED_REGISTRY = { "simplify": ..., "yc": ..., "jobright": ... }

Pipeline asks registry: get_scraper("greenhouse") → correct class
Adding Workday later: add class to ats_scrapers.py + one line to ATS_REGISTRY
Pipeline, CLI, normalizer: zero changes required
```

### SitemapDiscovery

ATS platforms publish public XML sitemaps of every company on their platform.
CareerOS reads these to discover slugs automatically — no hardcoding ever.

```
Greenhouse:  https://boards.greenhouse.io/sitemap.xml
Lever:       https://jobs.lever.co/sitemap.xml
Ashby:       https://jobs.ashbyhq.com/sitemap.xml
```

Each sitemap has thousands of companies across every industry:
Goldman Sachs, Mayo Clinic, Boeing, Bain, Johnson Controls —
all discovered automatically. No human decides which companies to include.

### Domain Diversity Sampling

A naive alphabetical cut of 500 from the sitemap returns only A-C companies.
Discovery enforces proportional domain sampling using heuristic name signals:

```
40%  tech / software
15%  finance / fintech
15%  healthcare / biotech
10%  engineering / robotics / aerospace
10%  consulting / business
10%  media / consumer / other
```

No LLM needed for sampling — company name signals are sufficient.
("bank", "capital" → finance · "health", "bio" → healthcare · etc.)

---

## 5. The 24-Hour Freshness Rule

### Why

```
CareerOS is a live market signal, not an archive.

Old jobs in the DB cause:
  - User applies to a role already filled
  - Clusters reflect past market, not today's
  - Stale skills requirements mislead the strategy engine

24-hour window means:
  - Every recommended job is actively accepting applications
  - Clusters reflect what employers want RIGHT NOW
  - Market signal updates daily
```

### Two-Level Enforcement

```
Level 1 — Scraper level (primary):
  Each scraper checks posted_at before creating a RawJob
  Jobs older than 24h are dropped immediately
  Never touch memory, normalizer, or database

Level 2 — Pipeline level (safety net):
  Pipeline validates posted_at on every NormalizedJob before insert
  Catches anything the scraper missed
  Jobs without posted_at → accepted (unknown age = benefit of doubt)
```

### Feed Source Age Handling

Feed sources use relative age strings, not ISO timestamps:

```
"5h"    → now - 5 hours  → ACCEPTED
"today" → now            → ACCEPTED
"2d"    → now - 2 days   → REJECTED
"3w"    → now - 21 days  → REJECTED
missing → None           → ACCEPTED (benefit of doubt)
```

### Database Retention

```
Clustering:       uses ALL jobs in DB (history improves cluster quality)
Recommendations:  uses only jobs with posted_at > now - 24h
                  (enforced by query filter, not deletion)

Historical data accumulates. Fresh filter applies at query time only.
```

---

## 6. Normalization — Hybrid Approach

### Rule-Based (fast, free, no API cost)

```
work_location    keyword match on location string
                 "remote" → remote · "hybrid" → hybrid · else → onsite

employment_type  keyword match on title
                 "intern" → internship · "contract" → contract
                 "part-time" → part_time · default → full_time

salary           regex on description
                 "$120k–$150k" · "€80,000" · "120,000 USD"
                 → salary_min · salary_max · salary_currency

HTML cleaning    selectolax strips all tags, collapses whitespace
```

### LLM-Based (Groq during dev, swappable for prod)

```
domain      which field/industry is this role in?
            cannot be determined by keywords — context matters
            "Analyst" in finance ≠ marketing ≠ data

seniority   what level is this role?
            "VP" at a bank = mid-senior IC, not executive
            "Associate" in consulting = entry, not mid
            rules fail here — LLM understands context

skills      what skills does this role actually require?
            "DCF modeling" for finance · "SolidWorks" for mechanical
            "HubSpot" for marketing · no static list can cover this
```

### Domain Taxonomy (LLM maps to this)

```
Technology:
  software engineering, backend engineering, frontend engineering,
  mobile engineering, full stack engineering, platform engineering,
  infrastructure engineering, data engineering, machine learning engineering,
  ai research, data science, analytics engineering, business intelligence,
  security engineering, embedded systems, firmware engineering,
  robotics engineering, computer vision, nlp engineering,
  developer relations, technical program management, qa engineering

Physical Engineering:
  mechanical engineering, electrical engineering, civil engineering,
  structural engineering, aerospace engineering, manufacturing engineering,
  industrial engineering, systems engineering, hardware engineering,
  process engineering, materials engineering, controls engineering,
  automation engineering, chemical engineering

Biomedical & Life Sciences:
  biomedical engineering, biochemistry, pharmaceutical, clinical research,
  regulatory affairs, medical devices, genomics, bioinformatics, lab sciences,
  research science, applied research, environmental science

Product & Design:
  product management, technical product management, ux design, product design,
  visual design, brand design, motion design, industrial design,
  user research, content design

Finance & Accounting:
  investment banking, private equity, venture capital, asset management,
  hedge fund, equity research, financial analysis, corporate finance,
  accounting, audit, tax, risk management, trading, quantitative finance,
  financial technology, insurance, actuarial

Business & Strategy:
  strategy, management consulting, business operations, revenue operations,
  program management, project management, chief of staff,
  supply chain, logistics, procurement, real estate

Sales & Growth:
  sales, enterprise sales, sales engineering, business development,
  partnerships, growth, customer success, account management

Marketing & Communications:
  marketing, product marketing, demand generation, content marketing,
  brand, communications, public relations, social media, seo

People & Talent:
  human resources, recruiting, talent acquisition, people operations,
  compensation and benefits, learning and development

Legal & Compliance:
  legal, compliance, privacy, intellectual property, contracts

Healthcare & Clinical:
  healthcare administration, clinical operations, nursing, physician,
  pharmacy, public health, health informatics, medical writing

Education:
  education, curriculum design, instructional design, edtech

Government & Nonprofit:
  government, policy, nonprofit, social impact

Fallback: other
```

### Universal Seniority Taxonomy

```
intern      internship, co-op, student worker
entry       0-2 years, analyst, associate, junior, new grad, coordinator
mid         2-5 years, no seniority modifier, generalist titles
senior      senior, sr., lead (individual contributor)
staff       staff-level IC, manager of a small team
principal   principal, director, senior manager
executive   VP, SVP, EVP, C-suite, Partner, Managing Director

Note: "VP" at a bank = staff/principal (IC level), not executive
      "Associate" in consulting = entry (not mid)
      LLM understands these domain-specific conventions
```

---

## 7. LLM Configuration

### Development vs Production Split

```
Development (now):
  Provider:  Groq (free tier)
  Model:     llama-3.3-70b-versatile
  Cost:      $0
  Limits:    30 req/min · 14,400 req/day
  SDK:       openai-compatible (base_url swap only)

Production (Phase 9+):
  Extraction: Claude Haiku  (fast, cheap, structured output)
  Strategy:   Claude Sonnet (reasoning, resume generation)
  Cost:       ~$1-2/day for full pipeline at scale
```

### Provider-Agnostic Client

The LLM client is built as a factory. Switching providers = two env var changes.

```
LLM_PROVIDER = groq | anthropic | ollama
LLM_MODEL    = llama-3.3-70b-versatile | claude-haiku-4-5-20251001 | llama3.2

All LLM calls go through one factory function.
No provider-specific code scattered across files.
```

### Groq Setup

```
Sign up:  console.groq.com (free, no credit card)
API key:  starts with gsk_...
Add to .env: GROQ_API_KEY=gsk_...
```

---

## 8. Data Flow

```
[ Daily trigger — APScheduler 2am ]
        │
        ▼
[ SitemapDiscovery — discovery.py ]
  Fetch sitemap.xml from Greenhouse · Lever · Ashby
  Parse all <loc> URLs → extract slugs
  Apply domain-balanced sampling (500 per ATS, shuffled)
  Return: list[str] slugs, proportionally domain-diverse
        │
        ▼
[ ATS Scrapers — ats_scrapers.py ]
  For each slug: GET /jobs endpoint
  For each job: check posted_at < now - 24h → DROP
  Yield: RawJob[] (today's jobs only)

[ Feed Scrapers — feed_scrapers.py ]
  Simplify:   GET GitHub markdown → parse HTML table → age filter
  YC:         GET ycombinator.com → extract embedded JSON → age filter
  Jobright:   GET jobright.ai → extract __NEXT_DATA__ → age filter
  HiringCafe: TBD

  All feeds: relative age string → absolute datetime → 24h filter
        │
        │  httpx.AsyncClient · Semaphore(10) · tenacity retry
        ▼
[ RawJob ]
  source · external_id · source_url · raw_payload · scraped_at · posted_at
        │
        │  JobNormalizer.normalize_batch()
        │  Rules: work_location · employment_type · salary · HTML strip
        │  LLM:   domain · seniority · skills (Groq llama-3.3-70b)
        │  Concurrency: Semaphore(20) for LLM calls
        ▼
[ NormalizedJob ]
  All fields populated · posted_at validated (24h safety net)
        │
        │  pipeline._store_batch()
        │  INSERT ... ON CONFLICT (source, external_id) DO NOTHING
        │  Batch size: 50 per transaction
        ▼
[ PostgreSQL: jobs ]
  Fresh · normalized · domain-diverse · deduplicated
        │
        │  Phase 4: OpenAI text-embedding-3-small
        ▼
[ PostgreSQL: job_embeddings — vector(1536) · HNSW ]
        │
        │  Phase 5: KMeans(K=10) · LLM labels
        ▼
[ PostgreSQL: role_clusters + job_cluster_memberships ]
        │
        │  Phase 6: resume embed · cosine similarity · LLM gap analysis
        ▼
[ PostgreSQL: rankings ]
        │
        │  Phase 7: path selection · job targeting · plan generation
        ▼
[ PostgreSQL: execution_plans + execution_actions ]
        │
        ├── CLI export  → Excel + JSON
        ├── Web         → dashboard + downloads
        └── MCP         → tool responses
```

---

## 9. Folder Structure

### Current State (what exists and is tested)

```
CareerOS/
├── core/
│   ├── collectors/
│   │   ├── base.py              ✓ BaseScraper + RawJob
│   │   ├── greenhouse.py        ✓ Built + tested (485 Stripe jobs)
│   │   ├── lever.py             ✓ Built
│   │   └── ashby.py             ✗ Empty placeholder
│   ├── normalization/
│   │   └── job_normalizer.py    ✓ Built — rule-based only, needs rewrite
│   ├── embeddings/
│   │   ├── job_embedder.py      ✗ Phase 4
│   │   └── resume_embedder.py   ✗ Phase 4
│   ├── clustering/
│   │   └── kmeans.py            ✗ Phase 5
│   ├── ranking/
│   │   └── career_mapper.py     ✗ Phase 6
│   ├── strategy/
│   │   └── execution_engine.py  ✗ Phase 7
│   ├── workflows/
│   │   └── pipeline.py          ✓ Built — needs async update
│   └── utils/
│       ├── logging.py           ✗ Empty
│       ├── retry.py             ✗ Empty
│       └── config.py            ✗ Empty
├── database/
│   ├── models/                  ✓ All 6 models built + tested
│   ├── session.py               ✓ Built + tested
│   ├── base.py                  ✓ Built
│   └── migrations/
│       └── schema.sql           ✓ Applied to local Postgres
├── cli/
│   ├── main.py                  ✓ Built (version + ingest-jobs commands)
│   └── commands/
│       ├── ingest.py            ✓ Built + tested
│       ├── analyze.py           ✗ Phase 8
│       ├── export.py            ✗ Phase 8
│       └── pipeline.py          ✗ Empty
├── api/                         ✗ Phase 9
├── mcp_server/                  ✗ Phase 10
├── exports/                     ✓ Folder exists, empty
├── config/
│   ├── settings.py              ✗ Not built
│   └── .env.example             ✗ Not created
├── scripts/
│   └── seed_db.py               ✓ Built + tested
├── tests/                       ✗ Empty
├── docker-compose.yml           ✓ pgvector/pg17
├── pyproject.toml               ✓
├── README.md                    ✓
└── .env                         ✓ Local only
```

### Target State (end of Phase 3)

```
CareerOS/
├── core/
│   ├── collectors/
│   │   ├── base.py              BaseScraper · RawJob · ScraperRegistry
│   │   ├── ats_scrapers.py      Greenhouse · Lever · Ashby · ATS_REGISTRY
│   │   ├── feed_scrapers.py     Simplify · YC · Jobright · HiringCafe
│   │   └── discovery.py         SitemapDiscovery
│   │   (delete: greenhouse.py · lever.py · ashby.py)
│   │
│   ├── normalization/
│   │   └── job_normalizer.py    Hybrid async (rules + Groq LLM)
│   ├── embeddings/              Phase 4
│   ├── clustering/              Phase 5
│   ├── ranking/                 Phase 6
│   ├── strategy/                Phase 7
│   ├── conversation/            Phase 8 (new)
│   │   ├── session.py
│   │   ├── prompts.py
│   │   └── handler.py
│   ├── scheduler/               Phase 3 finish (new)
│   │   └── daily_ingest.py
│   └── workflows/
│       └── pipeline.py          Updated for async + 24h filter
│
├── database/                    Unchanged
│
├── cli/
│   ├── main.py                  4 final commands
│   └── commands/
│       ├── ingest.py            Uses discovery + all sources
│       ├── analyze.py           Phase 8
│       ├── status.py            Phase 8
│       └── export.py            Phase 8
│
├── api/                         Phase 9
├── web/                         Phase 9 (Next.js monorepo)
├── mcp_server/                  Phase 10
├── exports/
├── config/
│   ├── settings.py              All config here, no sources.json
│   └── .env.example
├── docs/
├── scripts/
└── tests/
    ├── test_collectors.py
    ├── test_discovery.py
    ├── test_normalization.py
    ├── test_pipeline.py
    └── test_ranking.py
```

---

## 10. CLI — 4 Commands Only

```
careeros ingest      Discover → scrape all sources → normalize → store
careeros analyze     Upload resume → guided career session
careeros status      Current plan + this week's actions
careeros export      Export plan to Excel + PDF
```

### careeros ingest (target output)

```
$ careeros ingest

  Discovering companies from ATS sitemaps...
  ✓ Greenhouse  4,847 companies → sampling 500 (domain-balanced)
  ✓ Lever       2,103 companies → sampling 500
  ✓ Ashby         891 companies → sampling 400

  Scraping jobs posted in the last 24 hours...
  ✓ Greenhouse  1,243 fresh jobs
  ✓ Lever         891 fresh jobs
  ✓ Ashby         334 fresh jobs
  ✓ Simplify      127 fresh jobs
  ✓ YC             89 fresh jobs
  ✓ Jobright      203 fresh jobs

  Normalizing 2,887 jobs (domain · seniority · skills)...
  ✓ 2,887 normalized · 143 skipped · 0 failed

  Domain breakdown:
    software engineering     23%
    finance & fintech        11%
    healthcare & biotech      9%
    mechanical engineering    7%
    management consulting     6%
    other domains            44%

  DB: 18,432 total · 2,887 fresh (last 24h)
```

---

## 11. Web App

### Stack
```
Frontend:  Next.js 14 (App Router) — web/ folder in monorepo
Backend:   FastAPI — API + proxies Next.js in production
Auth:      Clerk
Hosting:   Railway
```

### UI Principles
```
Font:        Inter
Background:  #f9f9f7
Text:        #1a1a1a
Accent:      #d97706 (amber, CTAs only)
Border:      1px solid #e5e5e3
No gradients. No decorative animations.
Information density over decoration.
```

### Pages
```
/              Landing — "Upload your resume. See where you stand today."
/analyze       Resume upload → progress → /session
/session       Split screen: conversation (60%) + context panel (40%)
/jobs          Today's jobs (24h), filters, one-click resume tailoring
/roadmap       Learning path, milestones, progress
/profile       Resume versions, analysis history, applications
```

### Conversation Design

Every LLM response has full user context. Zero generic advice.

```
Context injected into every message:
  resume_summary · top_cluster_name · top_cluster_score
  top_3_skill_gaps · fresh_job_count · user_goal · timeline

Conversation phases:
  discovery → path_selection → plan_generation → execution_tracking
```

---

## 12. Tech Stack

| Component | Technology | Notes |
|---|---|---|
| Database | PostgreSQL 17 + pgvector | Transactions + vector search |
| ORM | SQLAlchemy 2.0 async | Type-safe, Alembic-compatible |
| Migrations | Alembic | Schema versioning |
| Async HTTP | httpx.AsyncClient | Semaphore-gated, retried |
| Retry | tenacity | Exponential backoff |
| HTML parsing | selectolax | Fast, C-backed |
| Embeddings | OpenAI text-embedding-3-small | 1536-dim, Phase 4 |
| LLM (dev) | Groq llama-3.3-70b-versatile | Free, fast, openai-compatible |
| LLM (prod) | Claude Haiku / Sonnet | Phase 9+ |
| Clustering | scikit-learn KMeans | Deterministic |
| PDF parsing | pypdf | Pure Python |
| Excel export | openpyxl | Full control |
| CLI | Typer + Rich | 4 commands |
| Config | pydantic-settings | Validated env vars |
| Scheduler | APScheduler | Daily ingest, no external infra |
| API | FastAPI + uvicorn | Async, SSE streaming |
| Frontend | Next.js 14 | App Router, RSC |
| Auth | Clerk | Zero custom code |
| Hosting | Railway | Simple, Postgres included |

---

## 13. Build Phases

```
Phase 3  ACTIVE    Data Pipeline

  Done:
  ✓ GreenhouseScraper + LeverScraper
  ✓ JobNormalizer (rule-based, sync)
  ✓ IngestionPipeline with deduplication
  ✓ careeros ingest-jobs CLI (verified: 485 Stripe jobs, idempotency confirmed)

  Remaining (in order):
  1. config/settings.py          pydantic-settings · sitemap URLs · LLM config
  2. .env.example                document all required env vars
  3. core/collectors/base.py     add ScraperRegistry class
  4. core/collectors/ats_scrapers.py
                                 consolidate Greenhouse + Lever + Ashby
                                 add 24h freshness filter
                                 add ATS_REGISTRY dict
  5. core/collectors/discovery.py
                                 SitemapDiscovery class
                                 domain-balanced sampling
  6. core/collectors/feed_scrapers.py
                                 SimplifyScraper · YCScraper · JobrightScraper
                                 24h age filter on all feeds
                                 FEED_REGISTRY dict
  7. core/normalization/job_normalizer.py
                                 rewrite as async
                                 add LLM extraction (Groq)
                                 domain · seniority · skills
                                 normalize_batch() with Semaphore(20)
  8. core/workflows/pipeline.py  update for async normalizer
                                 add 24h safety-net filter
                                 add domain breakdown logging
                                 add MultiSourcePipeline
  9. cli/commands/ingest.py      update to use discovery
                                 run all sources automatically
                                 show domain breakdown in output
  10. core/scheduler/daily_ingest.py
                                 APScheduler · 2am daily trigger
  11. Delete: greenhouse.py · lever.py · ashby.py


Phase 4            Embeddings
  1. job_embedder.py             batch async · 8191 token limit
                                 skip already-embedded jobs
                                 OpenAI text-embedding-3-small
  2. resume_embedder.py          same model · same dimensions
  3. Populate job_embeddings     run on all jobs in DB
  4. CLI command: careeros embed


Phase 5            Market Clustering (Agent 1 complete)
  1. kmeans.py                   KMeans(K=10) · L2-normalized
                                 deterministic (random_state=42)
  2. LLM cluster labeling        Groq generates label per cluster
                                 top_skills extraction per cluster
  3. Populate role_clusters      + job_cluster_memberships
  4. CLI command: careeros cluster
  5. Validate: expect non-tech clusters in output


Phase 6            Profile Matching (Agent 2)
  1. Resume parser               pypdf → plain text
                                 Groq extracts: skills · titles · years_exp
  2. career_mapper.py            embed resume
                                 cosine similarity vs all cluster centroids
                                 Groq: skill gap analysis per cluster
                                 fit_category assignment
  3. Populate rankings table
  4. CLI: careeros analyze (partial — analysis only, no conversation yet)


Phase 7            Strategy Engine (Agent 3)
  1. execution_engine.py         Path A/B/C selection logic
                                 Job targeting (fresh jobs only, 24h)
                                 Groq: resume variant generation
                                 Groq: weekly action plan generation
                                 Groq: skill roadmap generation
  2. Populate execution_plans + execution_actions
  3. Export: Excel workbook · JSON report · resume variant files


Phase 8            CLI Polish
  1. careeros analyze            full guided conversation in terminal
                                 context-injected LLM responses
                                 streaming output to terminal
  2. careeros status             current plan + this week's actions
  3. careeros export             Excel + PDF + resume variants
  4. Finalize 4-command interface
  5. core/conversation/          session.py · prompts.py · handler.py


Phase 9            Web App
  1. FastAPI routes              jobs · resume · pipeline · conversation
  2. Streaming endpoint          SSE for conversation responses
  3. Next.js scaffold            web/ folder · App Router
  4. Landing page                resume upload CTA
  5. /analyze page               upload + progress bar
  6. /session page               split screen conversation UI
  7. /jobs page                  fresh jobs dashboard
  8. /roadmap page               learning path visualization
  9. Clerk auth                  sign up · sign in · session
  10. Railway deployment          Postgres + API + Next.js


Phase 10           MCP Layer
  1. mcp_server/server.py        MCP protocol setup
  2. search_jobs tool            query → fresh job results
  3. rank_resume tool            resume text → rankings
  4. generate_plan tool          resume_id → execution plan
  5. get_status tool             current plan progress
```

---

## 14. Scaling Path

```
Daily ingest:
  Now:    APScheduler · 500 companies per ATS · ~3,000 fresh jobs/day
  Later:  Celery + Redis · full sitemap crawl weekly · delta daily

Vector search:
  Now:    HNSW indexes in schema.sql · handles 100k+ vectors
  Later:  No changes needed · O(log N) approximate search

Multi-user:
  Now:    Single user · local
  Later:  Add user_id FK to resumes · rankings · execution_plans
          PostgreSQL row-level security
          Clerk JWT on FastAPI middleware
          Zero schema redesign required

New sources:
  Add one class to ats_scrapers.py or feed_scrapers.py
  Add one entry to REGISTRY dict
  Zero other changes

LLM upgrade:
  Change LLM_PROVIDER and LLM_MODEL in .env
  Zero code changes
  Re-normalize existing jobs if extraction quality matters
```

---

## 15. What CareerOS Does Not Build

| What | Why |
|---|---|
| LinkedIn / Indeed scraping | ToS violation. Legal risk. |
| Hardcoded company lists | Biased, stale. Sitemaps solve this. |
| Keyword domain detection | Breaks across domains. LLM is robust. |
| Job archives for recommendations | CareerOS is live signal. Fresh only. |
| ATS form submission | Brittle, ToS risk. |
| Interview prep | Separate product. |
| Generic chatbot | Every response grounded in user data. |
| sources.json | Replaced entirely by SitemapDiscovery. |