# CareerOS — Database Reference

**Version:** 0.1.0  
**Status:** MVP  
**Engine:** PostgreSQL 18 + pgvector  
**Source of truth:** `table-creation.sql`

---

## Extensions

| Extension | Purpose |
|---|---|
| `vector` | Native `vector(n)` column type + HNSW/IVFFlat indexes |
| `uuid-ossp` | `uuid_generate_v4()` for all primary keys |
| `pg_trgm` | Trigram GIN indexes for fuzzy title/company search |

---

## ENUM Types

| Enum | Values |
|---|---|
| `job_source` | `greenhouse`, `lever`, `ashby`, `manual` |
| `job_status` | `raw` → `normalized` → `embedded` → `clustered` |
| `employment_type` | `full_time`, `part_time`, `contract`, `internship`, `other` |
| `work_location` | `remote`, `hybrid`, `onsite` |
| `fit_category` | `strong` (≥0.75), `adjacent` (0.50–0.74), `weak` (<0.50) |
| `execution_status` | `pending`, `in_progress`, `complete`, `skipped`, `failed` |
| `resume_variant_type` | `base`, `tailored` |

---

## Table Map

```
Layer 1 — Data (Agent 1)
  jobs                     raw + normalized job postings
  job_embeddings           vector(1536) per job · HNSW
  clustering_runs          KMeans run metadata
  role_clusters            K centroids + LLM labels · HNSW
  job_cluster_memberships  job → nearest cluster + L2 distance

Layer 2 — Intelligence (Agent 2)
  resumes                  base + tailored resume variants
  resume_embeddings        vector(1536) per resume · HNSW
  rankings                 cosine similarity · fit_category · skill gaps

Layer 3 — Decision (Agent 3)
  execution_plans          full JSONB plan per resume/run
  execution_actions        weekly tasks decomposed from plan
```

---

## Layer 1 — Data

### `jobs`

Primary store for all job postings. Agent 1 writes twice: on scrape (`status = 'raw'`) and after normalization (`status = 'normalized'`).

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID PK` | `uuid_generate_v4()` |
| `source` | `job_source` | ATS origin |
| `external_id` | `TEXT` | ATS-native job ID |
| `source_url` | `TEXT` | Direct link to posting |
| `raw_payload` | `JSONB` | Immutable ATS response |
| `scraped_at` | `TIMESTAMPTZ` | When scraper ran |
| `title` | `TEXT` | Normalized |
| `company` | `TEXT` | Normalized |
| `location` | `TEXT` | Human-readable string |
| `work_location` | `work_location` | remote / hybrid / onsite |
| `employment_type` | `employment_type` | |
| `description` | `TEXT` | HTML-stripped prose |
| `skills` | `TEXT[]` | Extracted skill tokens |
| `domain` | `TEXT` | e.g. "data engineering" |
| `seniority` | `TEXT` | e.g. "senior", "staff", "ic" |
| `salary_min` | `INTEGER` | Annual, in `salary_currency` |
| `salary_max` | `INTEGER` | |
| `salary_currency` | `CHAR(3)` | ISO 4217 |
| `posted_at` | `TIMESTAMPTZ` | |
| `closes_at` | `TIMESTAMPTZ` | |
| `status` | `job_status` | Pipeline state |
| `normalized_at` | `TIMESTAMPTZ` | Set by normalizer |
| `created_at` / `updated_at` | `TIMESTAMPTZ` | Auto-managed |

**Constraints:** `UNIQUE(source, external_id)` — deduplication key.

**Indexes:**
```
idx_jobs_status        (status)                    — pipeline queries
idx_jobs_posted_at     (posted_at DESC NULLS LAST) — recency sort
idx_jobs_domain        (domain)                    — facet filter
idx_jobs_company       (company)                   — facet filter
idx_jobs_title_trgm    GIN trgm                    — fuzzy search
idx_jobs_raw_payload   GIN jsonb                   — payload querying
idx_jobs_skills        GIN array                   — skill overlap queries
```

---

### `job_embeddings`

One row per `(job_id, model)`. The `model` column is the re-embed migration handle — swapping models creates new rows, old rows remain for comparison.

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID PK` | |
| `job_id` | `UUID FK → jobs` | CASCADE delete |
| `model` | `TEXT` | e.g. `text-embedding-3-small` |
| `embedding` | `vector(1536)` | L2-normalized before insert |
| `input_text` | `TEXT` | The chunk fed to the model |
| `token_count` | `INTEGER` | Cost tracking |
| `created_at` | `TIMESTAMPTZ` | |

**Constraints:** `UNIQUE(job_id, model)`

**Indexes:**
```
idx_job_embeddings_hnsw   HNSW cosine   m=16, ef_construction=64
```

---

### `clustering_runs`

Each KMeans execution gets a row. Centroids and memberships are scoped to a `run_id`. A new run is required when: K changes, the embedding model changes, or a significant batch of new jobs is added.

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID PK` | |
| `model` | `TEXT` | Embedding model used |
| `k` | `INTEGER` | Cluster count (MVP default: 10) |
| `job_count` | `INTEGER` | Jobs included in this run |
| `run_at` | `TIMESTAMPTZ` | |
| `notes` | `TEXT` | Optional human label |

**Constraints:** `k > 0`, `job_count > 0`

---

### `role_clusters`

K rows per clustering run. Centroid is the mean of all member job embeddings. Label and `top_skills` are LLM-generated after clustering.

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID PK` | |
| `run_id` | `UUID FK → clustering_runs` | CASCADE delete |
| `cluster_index` | `INTEGER` | 0-based within run |
| `label` | `TEXT` | e.g. "ML Platform Engineering" |
| `centroid` | `vector(1536)` | Mean embedding of members |
| `top_skills` | `TEXT[]` | Top N extracted skills |
| `job_count` | `INTEGER` | Member count |
| `created_at` | `TIMESTAMPTZ` | |

**Constraints:** `UNIQUE(run_id, cluster_index)`, `job_count >= 0`

**Indexes:**
```
idx_role_clusters_centroid_hnsw   HNSW cosine   Agent 2's primary query
idx_role_clusters_run_id          (run_id)
```

---

### `job_cluster_memberships`

Assignment table. Each job belongs to exactly one cluster per run.

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID PK` | |
| `job_id` | `UUID FK → jobs` | CASCADE delete |
| `cluster_id` | `UUID FK → role_clusters` | CASCADE delete |
| `run_id` | `UUID FK → clustering_runs` | CASCADE delete |
| `distance_to_centroid` | `FLOAT` | L2 distance; lower = tighter fit |

**Constraints:** `UNIQUE(job_id, run_id)` — one cluster per job per run.

---

## Layer 2 — Intelligence

### `resumes`

Base resumes and LLM-tailored variants share this table. A tailored variant must reference both a `parent_resume_id` (the base) and a `target_cluster_id` (which cluster it was written for). CHECK constraints enforce this.

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID PK` | |
| `variant` | `resume_variant_type` | `base` or `tailored` |
| `parent_resume_id` | `UUID FK → resumes` | NULL for base; set for tailored |
| `file_name` | `TEXT` | Original filename |
| `file_path` | `TEXT` | Relative path under `exports/resumes/` |
| `target_cluster_id` | `UUID FK → role_clusters` | NULL for base; set for tailored |
| `raw_text` | `TEXT` | pypdf plain text output |
| `parsed_skills` | `TEXT[]` | Extracted from resume |
| `parsed_titles` | `TEXT[]` | Job titles found in resume |
| `parsed_years_exp` | `INTEGER` | Estimated years of experience |
| `is_embedded` | `BOOLEAN` | Pipeline state flag |
| `created_at` / `updated_at` | `TIMESTAMPTZ` | |

**Constraints:**
- Tailored variants must have `parent_resume_id` (not null)
- Tailored variants must have `target_cluster_id` (not null)

---

### `resume_embeddings`

Mirrors `job_embeddings` exactly. Using the same model on both tables puts resumes and jobs in the same vector space, making cosine similarity meaningful.

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID PK` | |
| `resume_id` | `UUID FK → resumes` | CASCADE delete |
| `model` | `TEXT` | Must match `job_embeddings.model` for valid comparison |
| `embedding` | `vector(1536)` | |
| `input_text` | `TEXT` | |
| `token_count` | `INTEGER` | |
| `created_at` | `TIMESTAMPTZ` | |

**Constraints:** `UNIQUE(resume_id, model)`

---

### `rankings`

Agent 2's output table. One row per `(resume, cluster, run)`. This is what Agent 3 reads to build execution plans.

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID PK` | |
| `resume_id` | `UUID FK → resumes` | |
| `cluster_id` | `UUID FK → role_clusters` | |
| `run_id` | `UUID FK → clustering_runs` | |
| `cosine_similarity` | `FLOAT` | Range: -1.0 to 1.0 |
| `rank` | `INTEGER` | 1 = best match for this resume |
| `fit_category` | `fit_category` | strong / adjacent / weak |
| `skill_gaps` | `TEXT[]` | Skills in cluster missing from resume |
| `skill_matches` | `TEXT[]` | Skills present in both |
| `reasoning` | `TEXT` | LLM-generated explanation |
| `ranked_at` | `TIMESTAMPTZ` | |

**Constraints:** `UNIQUE(resume_id, cluster_id, run_id)`, similarity range check, rank > 0

**Indexes:**
```
idx_rankings_resume_sim   (resume_id, cosine_similarity DESC)   — primary sort
idx_rankings_fit          (fit_category)                        — Agent 3 filter
```

---

## Layer 3 — Decision

### `execution_plans`

One plan per `(resume, run)`. The full structured JSON payload is stored in `plan` for flexible export. Individual actions are normalized into `execution_actions` for CLI status tracking.

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID PK` | |
| `resume_id` | `UUID FK → resumes` | |
| `run_id` | `UUID FK → clustering_runs` | |
| `plan` | `JSONB` | Shape: `{ weekly_actions[], top_jobs[], resume_variants{}, skill_development[] }` |
| `json_export_path` | `TEXT` | Written by `careeros export` |
| `xlsx_export_path` | `TEXT` | Written by `careeros export` |
| `status` | `execution_status` | |
| `created_at` / `updated_at` | `TIMESTAMPTZ` | |

**Constraints:** `UNIQUE(resume_id, run_id)`

---

### `execution_actions`

Granular weekly tasks from the plan. Decoupled from the JSONB blob so the CLI can query status without parsing JSON.

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID PK` | |
| `plan_id` | `UUID FK → execution_plans` | CASCADE delete |
| `week` | `INTEGER` | 1-indexed |
| `day` | `INTEGER` | 1=Mon … 7=Sun; NULL = any day that week |
| `action_type` | `TEXT` | `apply`, `skill_build`, `network`, etc. |
| `description` | `TEXT` | Human-readable task |
| `job_id` | `UUID FK → jobs` | SET NULL on job delete |
| `status` | `execution_status` | |
| `due_at` | `TIMESTAMPTZ` | |
| `completed_at` | `TIMESTAMPTZ` | |
| `created_at` | `TIMESTAMPTZ` | |

---

## Triggers

`set_updated_at()` fires `BEFORE UPDATE` on `jobs`, `resumes`, and `execution_plans`. No manual timestamp management required in application code.

---

## Key Query Patterns

**Fetch all jobs ready to embed:**
```sql
SELECT id, title, description, skills
FROM jobs
WHERE status = 'normalized'
ORDER BY created_at;
```

**Find K nearest clusters to a resume embedding:**
```sql
SELECT rc.id, rc.label, 1 - (re.embedding <=> rc.centroid) AS cosine_similarity
FROM role_clusters rc, resume_embeddings re
WHERE re.resume_id = $1
  AND rc.run_id = $2
ORDER BY re.embedding <=> rc.centroid
LIMIT 10;
```

**Fetch ranked clusters for a resume (Agent 3 input):**
```sql
SELECT r.rank, r.cosine_similarity, r.fit_category,
       r.skill_gaps, r.skill_matches, r.reasoning,
       rc.label
FROM rankings r
JOIN role_clusters rc ON rc.id = r.cluster_id
WHERE r.resume_id = $1
  AND r.run_id = $2
  AND r.fit_category IN ('strong', 'adjacent')
ORDER BY r.rank;
```

**Fetch jobs in a cluster for export:**
```sql
SELECT j.id, j.title, j.company, j.source_url, j.salary_min, j.salary_max
FROM jobs j
JOIN job_cluster_memberships jcm ON jcm.job_id = j.id
WHERE jcm.cluster_id = $1
  AND jcm.run_id = $2
ORDER BY jcm.distance_to_centroid;
```

---

## Scaling Notes

- HNSW indexes are already in place on all three `vector(1536)` columns. No migration needed at scale.
- Adding multi-user support requires only: `user_id UUID` FK on `resumes`, `rankings`, `execution_plans` + PostgreSQL row-level security policies.
- Re-embedding with a new model creates new rows in `job_embeddings` / `resume_embeddings` (scoped by `model`). A new `clustering_run` is required after re-embedding. Old data is preserved.