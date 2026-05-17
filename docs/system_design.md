# CareerOS — System Design

**Version:** 0.1.0  
**Status:** MVP  
**Last updated:** 2025

---

## 1. High-Level Architecture

CareerOS is a 4-layer system. Each layer has a single responsibility. No layer reaches into another layer's concerns. The boundary between layers is always a well-defined data structure — never a direct function call across layers.

```
┌──────────────────────────────────────────────────────────────────────┐
│  LAYER 1 — DATA                                                      │
│                                                                      │
│  Scrapers         Greenhouse · Lever · Ashby (JSON APIs)             │
│  Normalizer   →   Unified Job schema (deduplicated)                  │
│  Storage      →   PostgreSQL: jobs table                             │
│                                                                      │
│  Output: Job[] rows, normalized, deduplicated, persisted             │
└──────────────────────────────┬───────────────────────────────────────┘
                               │ Job[]
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│  LAYER 2 — INTELLIGENCE                                              │
│                                                                      │
│  Agent 1: Market Intelligence                                        │
│    jobs → embeddings (pgvector) → role clusters (KMeans)            │
│                                                                      │
│  Agent 2: Career Mapping                                             │
│    resume → embedding → cosine similarity → ranked clusters          │
│                                                                      │
│  Output: RoleCluster[], Ranking[] with skill gaps and reasoning      │
└──────────────────────────────┬───────────────────────────────────────┘
                               │ Ranking[]
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│  LAYER 3 — DECISION                                                  │
│                                                                      │
│  Agent 3: Strategy & Execution                                       │
│    rankings → job selection → resume variants → weekly plan          │
│                                                                      │
│  Output: ExecutionPlan (structured JSON, persisted)                  │
└──────────────────────────────┬───────────────────────────────────────┘
                               │ ExecutionPlan
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│  LAYER 4 — EXECUTION                                                 │
│                                                                      │
│  CLI (primary)              FastAPI (secondary)                      │
│  careeros ingest-jobs       POST /ingest-jobs                        │
│  careeros run-analysis      POST /upload-resume                      │
│  careeros export            POST /run-analysis                       │
│  careeros full-pipeline     GET  /export                             │
│                                                                      │
│  Exports: JSON report · Excel workbook · resume variant files        │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 2. Core Data Flow

```
[ Job Board APIs ]
        │
        │  httpx.AsyncClient — rate-limited, retried, semaphore-gated
        ▼
[ Scrapers ]
        │  RawJob[] — ATS-native payload, source-tagged
        │
        │  Normalizer: field mapping + HTML cleaning + skill extraction
        ▼
[ PostgreSQL: jobs ]
  id · source · source_id · title · company · location
  description_clean · skills[] · domain · seniority · remote
        │
        │  OpenAI text-embedding-3-small (batched, token-truncated)
        ▼
[ PostgreSQL: job_embeddings ]
  job_id · embedding vector(1536) · model
        │
        │  KMeans(K=10) on L2-normalized embedding matrix
        ▼
[ PostgreSQL: role_clusters ]          [ PostgreSQL: job_cluster_memberships ]
  cluster_index · label · centroid      job_id · cluster_id · distance_to_centroid
  job_count · top_skills[] · run_id
        │
        │  ◀──── resume.pdf → pypdf → plain text → LLM extraction
        │  ◀──── ResumeEmbedding: same model, same dimensions
        │
        │  cosine_similarity = dot( L2(resume_vec), L2(centroid) )
        ▼
[ PostgreSQL: rankings ]
  resume_id · cluster_id · cosine_similarity · rank
  fit_category · skill_gaps[] · skill_matches[] · reasoning
        │
        │  Strategy Agent: select jobs, generate variants, build plan
        ▼
[ PostgreSQL: execution_plans ]
  resume_id · plan (JSON)
        │
        │  Export system reads plan + jobs + variants
        ▼
[ Output files ]
  career_report.json          — full structured output
  career_report.xlsx          — 4 tabs: overview · jobs · variants · weekly plan
  resume_<cluster_label>.txt  — one file per strong/adjacent cluster
```

---

## 3. Agent Overview

### Agent 1 — Market Intelligence Agent

**System role:** Owns all job market data. Converts raw ATS payloads into a normalized, embedded, clustered representation of the current job market.

**Input:** `dict[source → list[company_slug]]`

**Output:**
- `Job[]` — normalized, deduplicated, stored in PostgreSQL
- `JobEmbedding[]` — one `vector(1536)` per job
- `RoleCluster[]` — K clusters, each with a centroid, LLM-generated label, and top skills
- `JobClusterMembership[]` — each job assigned to its nearest cluster with distance score

**Responsibility boundary:** This agent knows nothing about resumes or users. It only knows about the market.

---

### Agent 2 — Career Mapping Agent

**System role:** Owns the comparison between one resume and the job market. Produces evidence-backed, ranked career directions.

**Input:** `Resume` — parsed, embedded, stored in PostgreSQL

**Output:**
- `Ranking[]` — one per cluster, sorted by `cosine_similarity` descending
- Each ranking carries: `fit_category` (strong / adjacent / weak), `skill_gaps[]`, `skill_matches[]`, `reasoning` (LLM-generated)

**Responsibility boundary:** This agent reads clusters produced by Agent 1 and reads the resume. It does not select jobs or generate plans — that is Agent 3's job.

---

### Agent 3 — Strategy & Execution Agent

**System role:** Owns the decision layer. Converts ranked clusters into specific, actionable outputs: job targets, resume variants, and a prioritized weekly plan.

**Input:** `Ranking[]` for a given resume, read from PostgreSQL

**Output:**
- `ExecutionPlan` — persisted to PostgreSQL, also written to `output_dir` as files
- Plan contains: `weekly_actions[]`, `top_jobs[]`, `resume_variants{}`, `skill_development[]`

**Responsibility boundary:** This agent does not re-rank or re-embed. It reads final rankings and makes decisions based on them. All LLM calls in this agent are generative (resume writing, plan generation), not analytical.

---

## 4. Tech Stack

| Component | Technology | Reason |
|---|---|---|
| API layer | FastAPI + uvicorn | Async-native, typed, fast to build on |
| Database | PostgreSQL 16 | Reliable, transactional, pgvector-compatible |
| Vector search | pgvector + HNSW index | Cosine similarity at scale without a separate service |
| ORM | SQLAlchemy 2.0 (async) | Type-safe, async-first, Alembic-compatible |
| Migrations | Alembic | Schema versioning; safe production deploys |
| Async HTTP | httpx.AsyncClient | Connection pooling, async, retries-compatible |
| Retry logic | tenacity | Exponential backoff with per-exception control |
| HTML parsing | selectolax | C-backed, 10–100x faster than BeautifulSoup |
| Embeddings | OpenAI text-embedding-3-small | 1536-dim, $0.02/1M tokens, strong quality |
| LLM calls | OpenAI GPT-4o-mini | Cluster labeling, reasoning, resume generation |
| Clustering | scikit-learn KMeans | Deterministic, no labeled data required |
| PDF parsing | pypdf | No system dependencies, pure Python |
| Excel export | openpyxl | Full workbook control, no LibreOffice required |
| CLI | Typer + Rich | Composable commands, styled terminal output |
| Config | pydantic-settings | Validated env vars, `.env` support, type-safe |

---

## 5. Design Decisions

### Why pgvector?

Standard PostgreSQL cannot efficiently compute cosine similarity over thousands of 1536-dimensional float vectors. A full table scan is O(N) — acceptable at 500 jobs, unacceptable at 50,000.

pgvector adds a native `vector` column type and an HNSW index that turns similarity search into approximate O(log N) lookups at >99% recall. Keeping vectors in Postgres — rather than a dedicated vector database — eliminates an external service dependency. The resume, rankings, embeddings, and jobs are all in one transactional system with no sync overhead.

### Why clustering?

Matching a resume against individual job postings produces 500 ranked results. This is noisy and unactionable: two "Senior Data Engineer" postings may score very differently based on description length or word choice alone, not on actual role similarity.

Cluster centroids are the average of many embeddings. They absorb noise from any individual posting. Matching against 10 centroids instead of 500 postings:

- Reduces noise from outlier descriptions
- Produces 10 actionable career directions instead of 500 scores
- Reveals sub-types within a domain ("ML Platform Engineering" vs. "Analytics Engineering")
- Runs in O(K) instead of O(N)

### Why CLI-first?

**Reproducibility.** A CLI command is an artifact. `careeros full-pipeline --resume resume.pdf` produces identical output given identical data. You can version-control it, put it in a Makefile, share it, or run it in CI. A UI session cannot be reproduced.

**Speed of iteration.** During development and tuning, invoking a pipeline step from the terminal takes one second. The equivalent through a UI requires a build, a deploy, and several clicks per run.

**Composability.** CLI commands are Unix primitives. You can pipe output, script sequences, and call them from other tools. The FastAPI layer is built on the same service layer as the CLI — it adds HTTP without replacing or duplicating anything.

---

## 6. Tradeoffs — What CareerOS Does Not Build

These are explicit decisions, not gaps. Each item was considered and deferred for a specific reason.

| What | Why not built |
|---|---|
| LinkedIn / Indeed scraping | JavaScript-rendered pages require headless browsers. Anti-bot systems make these scrapers fragile at scale. Greenhouse, Lever, and Ashby expose stable, documented JSON APIs. |
| Real-time job alerts | Requires a persistent scheduler and background worker process. Out of scope for a local-first, single-run MVP. |
| User accounts and authentication | Multi-tenancy requires row-level security, session management, and a login system. The MVP is single-user and runs locally. |
| Cover letter generation | Adds LLM cost per application. Cover letters are lower-ROI than resume tailoring and job selection. Addable later as an optional export step. |
| ATS form submission | Automating application submission is brittle, carries ToS risk, and removes the human judgment step before committing to an application. |
| Interview preparation | CareerOS ends at "apply to this job with this resume." Post-application preparation is a separate product surface. |
| React / web UI | A full UI adds a build pipeline, component library, state management, and a deployment target. The CLI achieves the same outcome for the MVP user with no additional infrastructure. |
| Multi-user collaboration | Coach dashboards, shared plans, and team accounts require multi-tenancy. The data model supports adding `user_id` — it is deferred, not impossible. |
| Historical market trend analysis | Trend data requires long-running scrapes and time-series storage. The MVP operates on a current snapshot only. |

---

## 7. Scaling Path

Listed in order of impact. Each item is independent.

### Async ingestion with job queues

**Current state:** Scraping runs synchronously inside a CLI command. A large scrape blocks the terminal for several minutes.

**Future state:** Move scraping and embedding tasks to an async job queue (ARQ or Celery + Redis). The CLI submits a task and returns immediately. Workers process in the background. Enables scheduled daily scrapes, parallel multi-worker processing, and isolated retry logic per task.

### HNSW indexing at scale

**Current state:** pgvector runs exact cosine search with no index. Fast enough up to ~10,000 vectors.

**Future state:** At 10,000+ job embeddings, add an HNSW index:

```sql
CREATE INDEX ON job_embeddings
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```

Turns similarity search from O(N) exact scan to O(log N) approximate search at >99% recall. No application code changes required.

### MCP tool hooks

**Current state:** CareerOS is a standalone local system. Agents are called directly by the CLI or API.

**Future state:** Expose agent capabilities as MCP (Model Context Protocol) tools so external AI agents can call CareerOS functions as part of a larger workflow:

```
search_jobs(query, filters)    →  Job[]
rank_resume(resume_text)       →  Ranking[]
generate_resume(cluster_label) →  ResumeVariant
create_plan(resume_id)         →  ExecutionPlan
```

The tool interface maps cleanly to the existing service layer. No agent logic changes required — only a thin MCP adapter layer.

### Multi-user support

**Current state:** Single-user. All resumes and plans belong to one person.

**Future state:** Add `user_id` UUID foreign key to `resumes`, `rankings`, and `execution_plans`. Add row-level security policies in PostgreSQL. Add FastAPI authentication (JWT or OAuth2). The data model already accommodates this — `user_id` is the only missing column in each affected table.

### Expanded scraping sources

**Current state:** Greenhouse, Lever, Ashby — stable JSON APIs, easy to parse.

**Future state:** Add sources in order of API stability:

1. Workday — semi-structured XML API, widely used in enterprise
2. Rippling — newer ATS, public job board API
3. Wellfound / AngelList — startup-focused
4. LinkedIn — unofficial API or browser automation; high maintenance cost, deferred last

Each new source requires only a new scraper class implementing `scrape_company(slug) → RawJob[]`. The normalizer, embedding pipeline, and clustering are unchanged.

### Embedding model upgrades

**Current state:** `text-embedding-3-small` — 1536 dimensions, $0.02 per 1M tokens.

**Future state:** The `model` column on `job_embeddings` and `resume_embeddings` tracks which model generated each vector. Upgrading to a larger or newer model requires re-embedding all jobs, re-clustering (centroids are model-specific), and re-ranking all resumes. This is a planned migration operation, not a schema change. A CLI command (`careeros reembed --model <model>`) can orchestrate it.