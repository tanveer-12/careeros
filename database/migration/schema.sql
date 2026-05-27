-- =============================================================================
-- CareerOS · PostgreSQL 18 + pgvector
-- Version: 0.1.0  |  Status: MVP
-- =============================================================================
-- Execution order matters — run top to bottom.
-- Assumes a fresh database. Idempotent via IF NOT EXISTS guards.
-- =============================================================================


-- ---------------------------------------------------------------------------
-- EXTENSIONS
-- ---------------------------------------------------------------------------

CREATE EXTENSION IF NOT EXISTS vector;          -- pgvector: vector type + indexes

-- ---------------------------------------------------------------------------
-- ENUM TYPES
-- ---------------------------------------------------------------------------

CREATE TYPE job_source AS ENUM (
    'remotive',
    'himalayas',
    'manual'
);

CREATE TYPE employment_type AS ENUM (
    'full_time',
    'part_time',
    'contract',
    'internship',
    'freelance',
    'other'
);

CREATE TYPE work_location AS ENUM (
    'remote',
    'hybrid',
    'onsite'
);

CREATE TYPE fit_category AS ENUM (
    'strong',       -- cosine similarity >= 0.75
    'adjacent',     -- 0.50 – 0.74
    'weak'          -- < 0.50
);

CREATE TYPE weel_plan_status AS ENUM (
    'active',
    'completed',
    'archived',
    'failed'
);

CREATE TYPE plan_step_type AS ENUM (
    'learning_task',
    'writing_task',
    'apply_task'
);


-- =============================================================================
-- LAYER 1 — DATA
-- jobs · job_embeddings · clustering_runs · role_clusters · job_cluster_memberships
-- =============================================================================


-- ---------------------------------------------------------------------------
-- jobs
-- Agent 1 writes here twice: once on scrape (raw), once after normalization.
-- Remotive-only job source; no ATS
-- ---------------------------------------------------------------------------

CREATE TABLE jobs (
    id               UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Source identity
    source           job_source      NOT NULL,
    external_id      TEXT            NOT NULL,   -- Remotive job ID
    source_url       TEXT            NOT NULL,

    -- Raw capture — immutable after insert
    raw_payload      JSONB           NOT NULL,
    scraped_at       TIMESTAMPTZ     NOT NULL DEFAULT now(),

    -- Normalized fields — populated by job_normalizer.py
    title            TEXT,
    company          TEXT,
    location         TEXT,
    work_location    work_location,
    employment_type  employment_type,
    description      TEXT,           -- HTML-stripped clean prose
    skills           TEXT[],         -- extracted skill tokens
    domain           TEXT,           -- e.g. "data engineering"
    seniority        TEXT,           -- e.g. "senior", "staff", "ic"
    salary_currency  CHAR(3),                 -- ISO 4217, e.g., "USD"
    salary_min       INTEGER,                  -- annual, in salary_currency
    salary_max       INTEGER,
    posted_at        TIMESTAMPTZ,
    closes_at        TIMESTAMPTZ,

    -- Bookkeeping
    created_at       TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ     NOT NULL DEFAULT now(),

    CONSTRAINT jobs_source_external_uniq UNIQUE (source, external_id)
);

CREATE INDEX idx_jobs_posted_at    ON jobs (posted_at DESC NULLS LAST);
CREATE INDEX idx_jobs_domain       ON jobs (domain);
CREATE INDEX idx_jobs_company      ON jobs (company);
CREATE INDEX idx_jobs_title_trgm   ON jobs USING gin (title gin_trgm_ops);
CREATE INDEX idx_jobs_raw_payload  ON jobs USING gin (raw_payload);
CREATE INDEX idx_jobs_skills       ON jobs USING gin (skills);


-- ---------------------------------------------------------------------------
-- job_embeddings
-- One row per (job, model). model column supports future re-embed migrations.
-- Uses vector(384) for BAAI/bge‑small‑en.
-- ---------------------------------------------------------------------------

CREATE TABLE job_embeddings (
    id           UUID           PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id       UUID           NOT NULL REFERENCES jobs (id) ON DELETE CASCADE,
    model        TEXT           NOT NULL,          -- e.g., "Supabase/bge-small-en"
    embedding    vector(384)    NOT NULL,          -- 384‑dim for bge‑small‑en [web:107][web:109]
    input_text   TEXT           NOT NULL,          -- the text chunk fed to the model
    token_count  INTEGER,                           -- for cost tracking
    created_at   TIMESTAMPTZ    NOT NULL DEFAULT now(),

    CONSTRAINT job_embeddings_job_model_uniq UNIQUE (job_id, model)
);


-- HNSW: O(log N) approximate cosine search (system_design.md §7)
CREATE INDEX idx_job_embeddings_hnsw
    ON job_embeddings
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);


-- ---------------------------------------------------------------------------
-- clustering_runs
-- Tracks each KMeans execution so centroids + memberships stay consistent.
-- A new run is created whenever K changes or jobs are re-embedded.
-- ---------------------------------------------------------------------------

CREATE TABLE clustering_runs (
    id         UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    model      TEXT        NOT NULL,   -- embedding model used in this run
    k          INTEGER     NOT NULL,   -- number of clusters (MVP default: 10)
    job_count  INTEGER     NOT NULL,   -- number of jobs included
    run_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    notes      TEXT,

    CONSTRAINT clustering_runs_k_positive         CHECK (k > 0),
    CONSTRAINT clustering_runs_job_count_positive CHECK (job_count > 0)
);


-- ---------------------------------------------------------------------------
-- role_clusters
-- Agent 1 output: K centroids + LLM-generated labels and top skills.
-- Uses vector(384) centroid.
-- ---------------------------------------------------------------------------

CREATE TABLE role_clusters (
    id             UUID           PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_id         UUID           NOT NULL REFERENCES clustering_runs (id) ON DELETE CASCADE,
    cluster_index  INTEGER        NOT NULL,   -- 0‑based index within the run
    label          TEXT           NOT NULL,   -- LLM label, e.g. "ML Platform Engineering"
    centroid       vector(384)    NOT NULL,   -- mean of member job embeddings (384‑dim) [web:107][web:109]
    top_skills     TEXT[]         NOT NULL DEFAULT '{}',
    job_count      INTEGER        NOT NULL DEFAULT 0,
    created_at     TIMESTAMPTZ    NOT NULL DEFAULT now(),

    CONSTRAINT role_clusters_run_index_uniq    UNIQUE (run_id, cluster_index),
    CONSTRAINT role_clusters_job_count_nonneg  CHECK (job_count >= 0)
);

-- Resume‑to‑cluster cosine similarity (Agent 2's primary query)
-- HNSW for fast centroid search
CREATE INDEX idx_role_clusters_centroid_hnsw
    ON role_clusters
    USING hnsw (centroid vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE INDEX idx_role_clusters_run_id ON role_clusters (run_id);


-- ---------------------------------------------------------------------------
-- job_cluster_memberships
-- Each job assigned to its nearest cluster within a run.
-- ---------------------------------------------------------------------------

CREATE TABLE job_cluster_memberships (
    id                   UUID      PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id               UUID      NOT NULL REFERENCES jobs (id) ON DELETE CASCADE,
    cluster_id           UUID      NOT NULL REFERENCES role_clusters (id) ON DELETE CASCADE,
    run_id               UUID      NOT NULL REFERENCES clustering_runs (id) ON DELETE CASCADE,
    distance_to_centroid FLOAT     NOT NULL,   -- L2 distance; lower = tighter fit

    CONSTRAINT job_cluster_memberships_job_run_uniq UNIQUE (job_id, run_id)
);

CREATE INDEX idx_jcm_cluster_id ON job_cluster_memberships (cluster_id);
CREATE INDEX idx_jcm_run_id     ON job_cluster_memberships (run_id);


-- =============================================================================
-- LAYER 2 — INTELLIGENCE
-- resumes · resume_embeddings · rankings
-- =============================================================================


-- ---------------------------------------------------------------------------
-- iser_resumes
-- Lumia MVP: one uploaded resume per user, no variants yet.
-- If you later add tailored variants, you can extend this table.
-- ---------------------------------------------------------------------------

CREATE TABLE user_resumes (
    id              UUID           PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         TEXT           NOT NULL,   -- external auth ID (e.g., Clerk)

    -- File reference
    file_name       TEXT           NOT NULL,
    file_path       TEXT,                      -- relative path under exports/resumes/

    -- Parsed content (from pypdf)
    raw_text        TEXT           NOT NULL,
    parsed_skills   TEXT[]         NOT NULL DEFAULT '{}',
    parsed_titles   TEXT[]         NOT NULL DEFAULT '{}',
    parsed_years_exp INTEGER,

    -- Pipeline state
    is_embedded     BOOLEAN        NOT NULL DEFAULT FALSE,

    created_at      TIMESTAMPTZ    NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ    NOT NULL DEFAULT now()
);


CREATE INDEX idx_user_resumes_user_id  ON user_resumes (user_id);
CREATE INDEX idx_user_resumes_embedded ON user_resumes (is_embedded);


-- ---------------------------------------------------------------------------
-- resume_embeddings
-- Mirrors job_embeddings. Same model = same vector space = comparable cosine.
-- ---------------------------------------------------------------------------

CREATE TABLE resume_embeddings (
    id           UUID           PRIMARY KEY DEFAULT uuid_generate_v4(),
    resume_id    UUID           NOT NULL REFERENCES user_resumes (id) ON DELETE CASCADE,
    model        TEXT           NOT NULL,
    embedding    vector(384)    NOT NULL,          -- 384‑dim for bge‑small‑en [web:107][web:109]
    input_text   TEXT           NOT NULL,
    token_count  INTEGER,
    created_at   TIMESTAMPTZ    NOT NULL DEFAULT now(),

    CONSTRAINT resume_embeddings_resume_model_uniq UNIQUE (resume_id, model)
);


CREATE INDEX idx_resume_embeddings_hnsw
    ON resume_embeddings
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);


-- ---------------------------------------------------------------------------
-- rankings
-- Agent 2 output: one row per (resume, cluster, run).
-- cosine_similarity drives rank; fit_category drives Agent 3 filtering.
-- ---------------------------------------------------------------------------

CREATE TABLE rankings (
    id              UUID          PRIMARY KEY DEFAULT uuid_generate_v4(),
    resume_id       UUID          NOT NULL REFERENCES user_resumes (id) ON DELETE CASCADE,
    cluster_id      UUID          NOT NULL REFERENCES role_clusters (id) ON DELETE CASCADE,
    run_id          UUID          NOT NULL REFERENCES clustering_runs (id) ON DELETE CASCADE,

    -- Similarity signal (Agent 2 core output)
    cosine_similarity FLOAT       NOT NULL,
    rank            INTEGER       NOT NULL,   -- 1 = best match for this resume

    -- LLM‑generated reasoning (optional, on‑demand)
    fit_category    fit_category  NOT NULL,
    skill_gaps      TEXT[]        NOT NULL DEFAULT '{}',
    skill_matches   TEXT[]        NOT NULL DEFAULT '{}',
    reasoning       TEXT,

    ranked_at       TIMESTAMPTZ   NOT NULL DEFAULT now(),

    CONSTRAINT rankings_resume_cluster_run_uniq UNIQUE (resume_id, cluster_id, run_id),
    CONSTRAINT rankings_similarity_range       CHECK (cosine_similarity BETWEEN -1.0 AND 1.0),
    CONSTRAINT rankings_rank_positive          CHECK (rank > 0)
);


CREATE INDEX idx_rankings_resume_id  ON rankings (resume_id);
CREATE INDEX idx_rankings_cluster_id ON rankings (cluster_id);
-- Primary sort for `lumia analyze` output
CREATE INDEX idx_rankings_resume_sim ON rankings (resume_id, cosine_similarity DESC);
CREATE INDEX idx_rankings_fit        ON rankings (fit_category);


-- =============================================================================
-- LAYER 3 — DECISION
-- two_week_plans · two_week_plan_steps
-- =============================================================================


-- ---------------------------------------------------------------------------
-- two_week_plans
-- Lumia MVP: 2‑week execution plan only.
-- A user can have one active plan per resume + cluster combination.
-- Longer plans will come in later stages.
-- ---------------------------------------------------------------------------

CREATE TABLE two_week_plans (
    id                  UUID           PRIMARY KEY DEFAULT uuid_generate_v4(),
    resume_id           UUID           NOT NULL REFERENCES user_resumes (id) ON DELETE CASCADE,
    cluster_id          UUID           NOT NULL REFERENCES role_clusters (id) ON DELETE CASCADE,

    -- Filters chosen by user
    target_location     TEXT,
    target_work_style   TEXT,          -- e.g., "remote", "hybrid", "onsite"
    target_employment_type TEXT,       -- e.g., "full_time", "contract"

    status              week_plan_status NOT NOT NULL DEFAULT 'active',

    created_at          TIMESTAMPTZ    NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ    NOT NULL DEFAULT now(),

    CONSTRAINT two_week_plans_resume_cluster_uniq UNIQUE (resume_id, cluster_id, status)
);


CREATE INDEX idx_two_week_plans_resume_id ON two_week_plans (resume_id);
CREATE INDEX idx_two_week_plans_cluster_id ON two_week_plans (cluster_id);
CREATE INDEX idx_two_week_plans_status     ON two_week_plans (status);



-- ---------------------------------------------------------------------------
-- two_week_plan_steps
-- Weekly tasks decomposed from the 2‑week plan.
-- Steps are either:
--   learning_task, writing_task, apply_task.
-- Optional AI‑explanation text per step is stored here (or in a separate column later).
-- ---------------------------------------------------------------------------


CREATE TABLE two_week_plan_steps (
    id                  UUID           PRIMARY KEY DEFAULT uuid_generate_v4(),
    plan_id             UUID           NOT NULL REFERENCES two_week_plans (id) ON DELETE CASCADE,
    week_number         INTEGER        NOT NULL,   -- 1 or 2
    step_type           plan_step_type NOT NOT NULL,

    title               TEXT           NOT NULL,
    description         TEXT           NOT NULL,
    resource_links      TEXT[],                   -- optional learning resources
    estimated_hours     FLOAT,                    -- rough estimate
    ai_explanation      TEXT,                     -- optional LLM‑generated explanation
    is_completed        BOOLEAN        NOT NULL DEFAULT FALSE,

    created_at          TIMESTAMPTZ    NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ    NOT NULL DEFAULT now(),

    CONSTRAINT two_week_plan_steps_week_range CHECK (week_number IN (1, 2)),
    CONSTRAINT two_week_plan_steps_estimated_hours_positive CHECK (estimated_hours IS NULL OR estimated_hours > 0)
);


CREATE INDEX idx_two_week_plan_steps_plan_id ON two_week_plan_steps (plan_id);
CREATE INDEX idx_two_week_plan_steps_week    ON two_week_plan_steps (plan_id, week_number);


-- =============================================================================
-- UTILITY — updated_at auto-maintenance
-- =============================================================================

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;


CREATE TRIGGER trg_jobs_updated_at
    BEFORE UPDATE ON jobs
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();


CREATE TRIGGER trg_user_resumes_updated_at
    BEFORE UPDATE ON user_resumes
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();


CREATE TRIGGER trg_two_week_plans_updated_at
    BEFORE UPDATE ON two_week_plans
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- =============================================================================
-- SCHEMA SUMMARY
-- =============================================================================

/*
  Layer 1 — Data (Agent 1)
  ┌──────────────────────────────┐
  │ jobs                         │  raw + normalized job postings
  │ job_embeddings               │  vector(384) per job · HNSW
  │ clustering_runs              │  KMeans run metadata
  │ role_clusters                │  K centroids + labels · HNSW
  │ job_cluster_memberships      │  job → nearest cluster + L2 distance
  └──────────────────────────────┘

  Layer 2 — Intelligence (Agent 2)
  ┌──────────────────────────────┐
  │ user_resumes                 │  per‑user uploaded resume
  │ resume_embeddings            │  vector(384) per resume · HNSW
  │ rankings                     │  cosine similarity · fit_category · gaps
  └──────────────────────────────┘

  Layer 3 — Decision (Agent 3)
  ┌──────────────────────────────┐
  │ two_week_plans               │  2‑week execution plan per resume/cluster
  │ two_week_plan_steps          │  weekly tasks, AI‑explanation optional
  └──────────────────────────────┘

  10 tables · 5 ENUMs · 3 HNSW indexes · 3 updated_at triggers
  All embeddings use vector(384) for compatibility with BAAI/bge‑small‑en.
*/