# Lumia — System Design  
**Local‑first career‑intelligence system**

**Version:** 1.0.0 (refactored from CareerOS → Lumia)  
**Status:** Active Development — Phase 3 (Data Pipeline)  
**Last updated:** May 2026  
**Focus:** Career clarity + execution planning, not job‑application automation


---

## 0. Mission

Lumia is **not**:

- A job board.  
- A resume‑optimizer SaaS.  
- A generic chatbot.  

Lumia is a **local‑first, web‑first career‑intelligence system** that answers three questions:
Where do I actually stand in today's job market?

What is the most efficient path to the job I want?

What should I do this week to get there?


Existing platforms rank jobs by keyword match and leave you to reverse‑engineer your path.  
Lumia starts where they stop: by mapping your resume to **live market archetypes** and generating **weekly execution plans** (job targets + resume‑variants + micro‑actions).  

It works equally well for:

- Software engineers  
- Investment bankers  
- Mechanical engineers  
- Nurses  
- Consultants  
- Robotics researchers  

**Zero domain bias by design.**

---

## 1. Who This Is For

### Fresher / New Grad
Problem:
  Has skills but doesn’t know which roles to target.
  Applies randomly, gets no callbacks.
  Doesn’t know what to learn next.

Lumia gives them:
  “The market has 3 clusters you can realistically enter today.”
  “Data Engineering: you’re 65% there. Missing: dbt, Airflow, cloud platform.”
  “8 companies posted new‑grad roles in this cluster today.”
  “Learn X in 3 weeks → apply to these 5 → here’s the tailored resume.”
  Week‑by‑week: what to learn, what to build, what to apply to.


### Mid‑Level Professional (any domain)
Problem:
  Stuck at current level, unclear what moves the needle.
  Resume is generic, not positioned for specific targets.
  Doesn’t know which companies are worth targeting.

Lumia gives them:
  “Your profile maps to Senior Financial Analyst and Corporate Strategy.”
  “For Corporate Strategy: you need M&A exposure + one more vertical.”
  “These 12 companies posted relevant roles in the last 24 hours.”
  “Your resume positions you as a generalist — here’s a variant per cluster.”



---

## 2. Core Design Principles

### No Hardcoding
- Company lists, job slugs, and domain mappings are never hardcoded.  
- Companies are discovered automatically from ATS public sitemaps.  
- Domains are extracted via LLM, not keyword dictionaries.  
- The system adapts to any industry without code changes.  

### 24‑Hour Freshness Window
- Lumia only ingests jobs posted within the last 24 hours.  
- This is **not a job archive**. It is a live market signal.  
- Every run reflects what employers want **right now, today**.  
- Older jobs are filtered at the scraper level before touching the DB.  

### Domain Agnosticism
- The intelligence layer makes **zero assumptions** about what field a user works in.  
- Clustering, ranking, and strategy work identically for:
  - Software engineer  
  - Financial analyst  
  - Mechanical engineer  
  - Clinical researcher  
  - Marketing director  
- Domain diversity in the DB is enforced by the discovery layer.  

### Zero Manual Maintenance
- No CSV files. No slug lists. No keyword dictionaries to update.  
- The system self‑maintains through sitemap discovery and LLM extraction.  

### Free / Local‑first LLMs During Development
- During development, **all LLM calls use free / open‑source / local models** (e.g., Groq or Hugging Face via local inference). [web:23][web:53][web:59]  
- The LLM client is **provider‑agnostic**: swap to production models by changing two environment variables, zero code changes. [web:23][web:54]  

### Local‑first, web‑first priorities
- The **web‑app is the primary user interface**; Lumia is **not** a terminal‑only tool.  
- The **CLI is reserved for:**  
  - Running background workflows (ingest, analyze, status, export).  
  - Running tests and verifying that integration / unit tests pass.  
- You will **not** build an “apply‑for‑you” automation layer in MVP; focus is insight + planning. [web:3][web:6][web:15]  


---

## 3. System Architecture
┌──────────────────────────────────────────────────────────────────────┐
│  LAYER 1 — DATA COLLECTION  (runs daily, fully automatic)            │
│                                                                      │
│  Discovery:  ATS sitemaps → company slugs (auto‑discovered)          │
│  ATS:        Greenhouse · Lever · Ashby                              │
│  Feeds:      Remotive · [optional: YC / other clean APIs]            │
│  Filter:     posted_at within last 24 hours only                     │
│  Normalize:  RawJob → NormalizedJob (rules + LLM)                    │
│  Store:      PostgreSQL with deduplication                           │
│                                                                      │
│  Output: fresh, normalized, domain‑diverse jobs from today           │
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
                               │ RoleCluster]
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
                               │ Ranking]
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│  LAYER 4 — STRATEGY ENGINE  (Agent 3)                                │
│                                                                      │
│  Path A: Apply now   → strong fit → today's jobs → tailored resume   │
│  Path B: Build then → adjacent fit → skill roadmap → unlock roles   │
│  Path C: Pivot       → weak fit + high interest → 3‑month plan        │
│                                                                      │
│  Output: ExecutionPlan with weekly actions, job targets, roadmap     │
└──────────────────────────────┬───────────────────────────────────────┘
                               │ ExecutionPlan
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│  LAYER 5 — INTERFACES                                                │
│                                                                      │
│  CLI (terminal)              Web App (hosted)                        │
│    lumia ingest              Next.js 14 + FastAPI                    │
│    lumia analyze             light‑themed, soothing UI               │
│    lumia status              Conversational + dashboard views        │
│    lumia export              No “apply‑for‑you” layer in MVP         │
│                              CLI only for tests & background jobs    │
└──────────────────────────────────────────────────────────────────────┘


---

## 4. Collector Architecture

### Structure
core/collectors/
base.py BaseScraper ABC · RawJob dataclass · ScraperRegistry
api_scrapers/ (formerly "feed_scrapers")
remotive.py RemotiveScraper
yc.py YCScraper (optional)
[other] ...
discovery.py [N/A for now, retired]



### Why Registry Pattern (simplified)

Now that you don’t rely on ATS sitemaps:

- You still use **ScraperRegistry**, but only for API‑style sources:
  ```python
  API_REGISTRY = {
      "remotive": RemotiveScraper,
      "yc": YCScraper,
      # ...
  }
  ```
- Pipeline asks the registry:
  - `get_scraper("remotive")` → correct class.
- Adding a new source = one new class + one dict entry. Nothing else changes. [web:6][web:69]



### SitemapDiscovery

ATS platforms publish public XML sitemaps of every company on their platform.  
Lumia reads these to discover slugs automatically — no hardcoding ever.  

Each sitemap has thousands of companies across every industry:  
Goldman Sachs, Mayo Clinic, Boeing, Bain, Johnson Controls —  
all discovered automatically. No human decides which companies to include.  

### Domain Diversity Sampling

A naive alphabetical cut of 500 from the sitemap returns only A‑C companies.  
Discovery enforces proportional domain sampling using heuristic name signals:
40%  tech / software
15%  finance / fintech
15%  healthcare / biotech
10%  engineering / robotics / aerospace
10%  consulting / business
10%  media / consumer / other


No LLM needed for sampling — company name signals are sufficient.  
("bank", "capital" → finance · "health", "bio" → healthcare · etc.).  

### Layer 4: Learning‑Path‑Driven Strategy Engine (Agent 3)

The strategy engine generates short‑term **2‑week learning‑and‑writing plans** by default. Long‑term plans (4–8–12 weeks) will be added in later stages.

For each user, it outputs:

- A **2‑week plan** aligned with the top skill gaps:
  - **Learning tasks** (e.g., “Start course X”, “Read docs for Y”, “Build Z”).  
  - **Writing / LinkedIn tasks**:
    - “Rewrite resume bullet for project A to emphasize B.”  
    - “Draft a LinkedIn post about starting X.”  
  - Optional **apply‑type tasks**:
    - “Apply to 2–3 roles that match your archetype.”  

The **core value is the 2‑week learning‑and‑writing plan**; job‑applications are optional and secondary. In future stages, the product will allow:
- Extending to 4‑week, 8‑week, or 12‑week learning paths.
- Custom‑length plans based on user preferences.

---

## 5. The 24‑Hour Freshness Rule

... (unchanged from your earlier draft, just keep the text under this section as‑is)

---

## 6. Normalization — Hybrid Approach

... (unchanged — keep your detailed rule‑based + LLM‑based normalization)

---

## 7. LLM & Embedding Strategy

### LLM Configuration (development vs future production)

... (update your `OpenAI → HF` notes to match HF‑only / local‑inference)

Key changes:

- Explicitly say:
  - “Embeddings use **Hugging Face** models (e.g., `Supabase/bge‑small‑en` or equivalent) via local inference (Text Embeddings Inference / TEI).” [web:53][web:59]  
  - “No paid‑API embedding in MVP; keep everything local‑first / on‑your own infra.” [web:53][web:56]  

---

## 8. Data Flow

... (keep your existing ASCII‑art data‑flow diagram, but update embeddings to HF‑model / TEI).

---

## 9. UI & Visual Design (Lumia‑style, light‑themed)

### Overall UI principles

- **Light‑themed only** (no dark mode).  
- **Soothing, not overwhelming**:  
  - Minimal parallax / motion;  
  - No black‑hero sections, no neon;  
  - Soft, warm, or muted pastel accents. [web:42][web:48]  
- **Clear, sectioned layout**:  
  - Hero → “How it works” → “Dashboard preview” → CTA.  
  - Each section clearly separated, with breathing‑space.  

### Color palette (example)

- Background: light off‑white (`#f9f9f7`).  
- Text: dark neutral (`#1a1a1a` for headings, `#6f6f6f` for body).  
- Accent: warm amber‑orange (`#d97706`) or soft teal (`#0f766e`) for CTAs.  
- Border / separator: light gray (`#e5e5e3`). [web:31][web:34][web:37]  

### Typography

- Display / logo / section titles: `Instrument Serif` (or another elegant serif).  
- Body text: `Inter` (or another clean, low‑contrast sans‑serif). [web:36][web:39]  
- No italics in body text; keep it very readable.  

### Motion effects (minimal, soothing)

- Use **fade‑rise** effects only (opacity + small translateY).  
- Duration: `0.6–0.8s`, easing: `ease‑out`.  
- Stagger entry of elements by `0.1–0.2s`.  
- No fast‑looping, no bounces, no intense zooms. [web:42][web:45]  

### Core pages (prototype‑first)

- `/`  
  - Laguna‑style landing page:  
    - Light, minimal hero.  
    - “Upload your resume. See where you stand in today’s job market.”  
    - “Begin your journey” CTA.  
- `/analyze`  
  - Resume‑upload + progress indicators.  
- `/dashboard`  
  - Three‑panel layout:  
    - “Career archetypes”.  
    - “Skill‑gap report”.  
    - “This week’s plan”.  
- `/jobs`  
  - Filtered list of fresh jobs (24h).  
  - One‑click view of “How well this job matches you”.  
- `/roadmap`  
  - Simple timeline / milestone‑view for 3–6–12‑week plans.  

You can reference MotionSites‑style “hero” concepts but **strip out the cinematic video and black‑dominant styling**; keep it **light, calm, and career‑focused**. [web:44][web:48]  

---

## 10. Tech Stack (Lumia, Refactored)

| Component            | Technology                       | Notes |
|----------------------|----------------------------------|-------|
| Database             | PostgreSQL 17 + pgvector         | Transactions + vector search [web:54] |
| ORM                  | SQLAlchemy 2.0 async             | Type‑safe, Alembic‑compatible |
| Migrations           | Alembic                          | Schema versioning |
| Async HTTP           | httpx.AsyncClient               | Semaphore‑gated, retried |
| Retry                | tenacity                         | Exponential backoff |
| HTML parsing         | selectolax                       | Fast, C‑backed |
| Embeddings (MVP)     | Hugging Face (e.g., bge‑small‑en) via local‑inference | No paid‑API, strong semantic‑search. [web:53][web:59] |
| LLM (dev)            | Groq / HF‑based model            | Free, fast, openai‑compatible. [web:23] |
| LLM (prod‑later)     | Claude‑equivalent or HF‑pro‑class | Phase‑later swap. |
| Clustering           | scikit‑learn KMeans              | Deterministic, lightweight. |
| PDF parsing          | pypdf                            | Pure Python. |
| Excel export         | openpyxl                         | Full control. |
| CLI                  | Typer + Rich                     | 4 commands. |
| Config               | pydantic‑settings                | Validated env vars. |
| Scheduler            | APScheduler                      | Daily ingest, no external infra. |
| API / Backend        | FastAPI + uvicorn                | Async, SSE‑ready. |
| Frontend (web‑app)   | Next.js 14 (App Router)          | Light‑themed, motion‑leaning UI. [web:36] |
| Auth (optional)      | Clerk                            | Zero‑custom code. |
| Hosting (prototype)  | Railway                          | Quick Postgres + app. |


---

## 11. Build Phases (v2 — with refactored DB & UI)

Use your existing Phases 3–10 structure, but:

- Rename `careeros` → `lumia` in every CLI / doc.  
- Explicitly say **“Phase 3” = DB‑refactor + normalizer‑rewrite + scheduler + feeds (Remotive)”**.  
- Explicitly say **“Phase 9” = Web‑app prototype (light‑themed, soothing, minimal‑motion)”**.  

... (rest of your “Build Phases” section can stay as‑is, just with `Lumia` instead of `CareerOS` where it appears).  

---

## 12. What Lumia Does Not Build (MVP)

| What                     | Why |
|--------------------------|-----|
| LinkedIn / Indeed scraping | ToS violation. Legal risk. |
| Hardcoded company lists  | Biased, stale. Sitemaps solve this. |
| Keyword‑based domain detection | Breaks across domains. LLM is robust. |
| Job archives for recommendations | Lumia is live signal. Fresh only. |
| ATS form‑submission automation | Brittle, ToS‑risk; not MVP‑aligned. |
| Interview‑prep product   | Separate product later. |
| Generic chatbot          | Every response grounded in user data. |
| `sources.json`           | Replaced by SitemapDiscovery. |
| “Apply‑for‑you” layer    | Not MVP; keep Lumia focused on clarity and planning. |