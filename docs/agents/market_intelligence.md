# Agent 1 — Market Intelligence Agent

**Layer:** Intelligence (Layer 2)  
**File:** `docs/agents/market_intelligence_agent.py`

---

## Responsibility

Owns all job market data. Converts raw ATS payloads into a normalized, embedded, and clustered representation of the current job market.

This agent is the only component that touches scraper output and the only component that writes to `job_embeddings` and `role_clusters`. Nothing downstream calls a scraper directly.

---

## Input

```python
companies: dict[str, list[str]]
# Example:
{
  "greenhouse": ["stripe", "figma", "coinbase"],
  "lever":      ["notion", "duolingo"],
  "ashby":      ["linear", "retool"]
}
```

Passed by the CLI (`careeros ingest-jobs`) or FastAPI (`POST /ingest-jobs`). The caller does not need to know which ATS each company uses — that is this agent's concern.

---

## Output

Four sets of rows written to PostgreSQL:

**`jobs`**
```
id · source · source_id · title · company · location · remote
description_clean · skills[] · domain · seniority
salary_min · salary_max · scraped_at · is_active
```

**`job_embeddings`**
```
job_id · embedding vector(1536) · model · created_at
```

**`role_clusters`**
```
cluster_index · label · centroid vector(1536)
job_count · top_skills[] · run_id · created_at
```

**`job_cluster_memberships`**
```
job_id · cluster_id · distance_to_centroid
```

Also returns a summary dict to the caller:
```python
{
  "scraped": int,
  "normalized": int,
  "inserted": int,
  "updated": int,
  "embedded": int,
  "clusters": [{"cluster_index": int, "label": str, "job_count": int}]
}
```

---

## Logic

### Step 1 — Scrape

One scraper class per ATS (`GreenhouseScraper`, `LeverScraper`, `AshbyScraper`). Each implements:

```python
async def scrape_company(slug: str) -> list[RawJob]
```

All scrapers share a single `asyncio.Semaphore` capped at `settings.scrape_concurrency` (default: 5). This prevents concurrent request overflow across all ATS sources combined, not per-source.

HTTP client is `httpx.AsyncClient` with a shared connection pool per scraper instance. Retries are handled by `tenacity` with exponential backoff: wait 1s → 2s → 4s, max 3 attempts, triggers on `httpx.HTTPError` and HTTP 429.

### Step 2 — Normalize

Each `RawJob` passes through the normalizer:

1. HTML description → plain text via `selectolax` (fast C-backed parser)
2. Whitespace normalization (collapse runs, strip boilerplate EEO text)
3. Keyword-based skill extraction against a curated vocabulary (~60 skills)
4. Rule-based seniority classification from job title
5. Keyword-based domain classification from title + first 500 chars of description
6. Regex salary range extraction

Output is a `Job` ORM object ready for DB insertion.

### Step 3 — Deduplicate and store

Deduplication key: `(source, source_id)`. On conflict:
- **Existing row:** update `title`, `description_clean`, `skills`, `domain`
- **New row:** insert

Uses `INSERT ... ON CONFLICT DO UPDATE` via SQLAlchemy upsert pattern. Idempotent — safe to re-run against the same companies.

### Step 4 — Embed

Queries for all `Job` rows with no corresponding `JobEmbedding`. Skips already-embedded jobs — re-runs are incremental and cheap.

Embedding text: `f"{job.title}\n\n{job.description_clean}"`. Title is prepended because it carries high-signal role type information that anchors the embedding before reading the description.

Text is truncated to 6,000 tokens before embedding (model limit: 8,191 tokens; 6,000 is a safe conservative bound that retains >99% of job content).

Requests are batched at 100 texts per API call. A 100ms sleep separates batches to avoid rate limiting. Model: `text-embedding-3-small` (1536 dimensions, $0.02/1M tokens).

### Step 5 — Cluster

1. Load all `JobEmbedding` rows into a numpy matrix of shape `(N, 1536)`
2. L2-normalize each row — converts cosine similarity to equivalent euclidean distance, required for KMeans to minimize the correct objective
3. Run `KMeans(n_clusters=K, random_state=42, n_init=10)` — fixed seed for reproducibility, 10 random initializations to avoid local minima
4. Assign each job to its nearest centroid; compute `distance_to_centroid` as L2 distance in normalized space
5. Generate a human-readable label for each cluster by prompting GPT-4o-mini with the 5 job titles nearest each centroid
6. Persist clusters and memberships; tag with a `run_id` UUID prefix for traceability across runs

Minimum jobs required before clustering: `settings.min_jobs_for_clustering` (default: 30). Below this threshold, clustering is skipped and a warning is logged.

---

## Failure Cases

| Failure | Behavior |
|---|---|
| ATS returns 404 for a company slug | Log warning, skip company, continue with others |
| HTTP 429 rate limit | tenacity catches it, sleeps `Retry-After` header value, retries |
| All retries exhausted for one job | Log warning, skip that job, continue batch |
| Normalizer throws on a RawJob | Log warning with source/source_id, skip that job |
| OpenAI embedding API error | Entire batch fails; jobs remain un-embedded; safe to retry the embed step independently |
| Fewer than `min_jobs_for_clustering` embeddings | Log warning, return early, no cluster rows written |
| LLM cluster labeling fails for one cluster | Use fallback label `"Cluster {index}"`, continue |
| DB write fails mid-batch | SQLAlchemy rolls back the transaction; no partial state written |