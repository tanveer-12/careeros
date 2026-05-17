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
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";     -- uuid_generate_v4()
CREATE EXTENSION IF NOT EXISTS pg_trgm;         -- trigram fuzzy search on text fields


-- ---------------------------------------------------------------------------
-- ENUM TYPES
-- ---------------------------------------------------------------------------

CREATE TYPE job_source AS ENUM (
    'greenhouse',
    'lever',
    'ashby',
    'manual'
);

CREATE TYPE job_status AS ENUM (
    'raw',          -- scraped, not yet normalized
    'normalized',   -- field mapping + HTML clean complete
    'embedded',     -- embedding generated
    'clustered'     -- assigned to a role cluster
);

CREATE TYPE employment_type AS ENUM (
    'full_time',
    'part_time',
    'contract',
    'internship',
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

CREATE TYPE execution_status AS ENUM (
    'pending',
    'in_progress',
    'complete',
    'skipped',
    'failed'
);

CREATE TYPE resume_variant_type AS ENUM (
    'base',         -- original uploaded resume
    'tailored'      -- LLM-generated variant targeting a specific cluster
);


-- =============================================================================
-- LAYER 1 — DATA
-- jobs · job_embeddings · clustering_runs · role_clusters · job_cluster_memberships
-- =============================================================================


-- ---------------------------------------------------------------------------
-- jobs
-- Agent 1 writes here twice: once on scrape (raw), once after normalization.
-- ---------------------------------------------------------------------------

CREATE TABLE jobs (
    id               UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Source identity
    source           job_source      NOT NULL,
    external_id      TEXT            NOT NULL,   -- ATS-native job ID
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
    salary_min       INTEGER,        -- annual, in salary_currency
    salary_max       INTEGER,
    salary_currency  CHAR(3),        -- ISO 4217, e.g. "USD"
    posted_at        TIMESTAMPTZ,
    closes_at        TIMESTAMPTZ,

    -- Pipeline state
    status           job_status      NOT NULL DEFAULT 'raw',
    normalized_at    TIMESTAMPTZ,

    -- Bookkeeping
    created_at       TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ     NOT NULL DEFAULT now(),

    CONSTRAINT jobs_source_external_uniq UNIQUE (source, external_id)
);

CREATE INDEX idx_jobs_status       ON jobs (status);
CREATE INDEX idx_jobs_posted_at    ON jobs (posted_at DESC NULLS LAST);
CREATE INDEX idx_jobs_domain       ON jobs (domain);
CREATE INDEX idx_jobs_company      ON jobs (company);
CREATE INDEX idx_jobs_title_trgm   ON jobs USING gin (title gin_trgm_ops);
CREATE INDEX idx_jobs_raw_payload  ON jobs USING gin (raw_payload);
CREATE INDEX idx_jobs_skills       ON jobs USING gin (skills);


-- ---------------------------------------------------------------------------
-- job_embeddings
-- One row per (job, model). model column supports future re-embed migrations.
-- ---------------------------------------------------------------------------

CREATE TABLE job_embeddings (
    id           UUID          PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id       UUID          NOT NULL REFERENCES jobs (id) ON DELETE CASCADE,
    model        TEXT          NOT NULL,          -- "text-embedding-3-small"
    embedding    vector(1536)  NOT NULL,
    input_text   TEXT          NOT NULL,          -- the text chunk fed to the model
    token_count  INTEGER,                         -- for cost tracking
    created_at   TIMESTAMPTZ   NOT NULL DEFAULT now(),

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
-- ---------------------------------------------------------------------------

CREATE TABLE role_clusters (
    id             UUID          PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_id         UUID          NOT NULL REFERENCES clustering_runs (id) ON DELETE CASCADE,
    cluster_index  INTEGER       NOT NULL,   -- 0-based index within the run
    label          TEXT          NOT NULL,   -- LLM label, e.g. "ML Platform Engineering"
    centroid       vector(1536)  NOT NULL,   -- mean of member job embeddings
    top_skills     TEXT[]        NOT NULL DEFAULT '{}',
    job_count      INTEGER       NOT NULL DEFAULT 0,
    created_at     TIMESTAMPTZ   NOT NULL DEFAULT now(),

    CONSTRAINT role_clusters_run_index_uniq    UNIQUE (run_id, cluster_index),
    CONSTRAINT role_clusters_job_count_nonneg  CHECK (job_count >= 0)
);

-- Resume-to-cluster cosine similarity (Agent 2's primary query)
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
    id                   UUID    PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id               UUID    NOT NULL REFERENCES jobs (id) ON DELETE CASCADE,
    cluster_id           UUID    NOT NULL REFERENCES role_clusters (id) ON DELETE CASCADE,
    run_id               UUID    NOT NULL REFERENCES clustering_runs (id) ON DELETE CASCADE,
    distance_to_centroid FLOAT   NOT NULL,   -- L2 distance; lower = tighter fit

    CONSTRAINT job_cluster_memberships_job_run_uniq UNIQUE (job_id, run_id)
);

CREATE INDEX idx_jcm_cluster_id ON job_cluster_memberships (cluster_id);
CREATE INDEX idx_jcm_run_id     ON job_cluster_memberships (run_id);


-- =============================================================================
-- LAYER 2 — INTELLIGENCE
-- resumes · resume_embeddings · rankings
-- =============================================================================


-- ---------------------------------------------------------------------------
-- resumes
-- Base resumes and LLM-tailored variants share this table.
-- Variants link back to their parent via parent_resume_id.
-- ---------------------------------------------------------------------------

CREATE TABLE resumes (
    id                UUID                PRIMARY KEY DEFAULT uuid_generate_v4(),
    variant           resume_variant_type NOT NULL DEFAULT 'base',
    parent_resume_id  UUID                REFERENCES resumes (id) ON DELETE SET NULL,
    -- ^ NULL for base; points to base resume for tailored variants

    -- File reference
    file_name         TEXT                NOT NULL,
    file_path         TEXT,               -- relative path under exports/resumes/

    -- For tailored variants: which cluster was this written for?
    target_cluster_id UUID                REFERENCES role_clusters (id) ON DELETE SET NULL,

    -- Parsed content (from pypdf)
    raw_text          TEXT                NOT NULL,
    parsed_skills     TEXT[]              NOT NULL DEFAULT '{}',
    parsed_titles     TEXT[]              NOT NULL DEFAULT '{}',
    parsed_years_exp  INTEGER,

    -- Pipeline state
    is_embedded       BOOLEAN             NOT NULL DEFAULT FALSE,

    created_at        TIMESTAMPTZ         NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ         NOT NULL DEFAULT now(),

    CONSTRAINT resumes_tailored_needs_parent
        CHECK (variant = 'base' OR parent_resume_id IS NOT NULL),
    CONSTRAINT resumes_tailored_needs_cluster
        CHECK (variant = 'base' OR target_cluster_id IS NOT NULL)
);

CREATE INDEX idx_resumes_variant           ON resumes (variant);
CREATE INDEX idx_resumes_parent_resume_id  ON resumes (parent_resume_id);


-- ---------------------------------------------------------------------------
-- resume_embeddings
-- Mirrors job_embeddings. Same model = same vector space = comparable cosine.
-- ---------------------------------------------------------------------------

CREATE TABLE resume_embeddings (
    id          UUID          PRIMARY KEY DEFAULT uuid_generate_v4(),
    resume_id   UUID          NOT NULL REFERENCES resumes (id) ON DELETE CASCADE,
    model       TEXT          NOT NULL,
    embedding   vector(1536)  NOT NULL,
    input_text  TEXT          NOT NULL,
    token_count INTEGER,
    created_at  TIMESTAMPTZ   NOT NULL DEFAULT now(),

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
    id                UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    resume_id         UUID         NOT NULL REFERENCES resumes (id) ON DELETE CASCADE,
    cluster_id        UUID         NOT NULL REFERENCES role_clusters (id) ON DELETE CASCADE,
    run_id            UUID         NOT NULL REFERENCES clustering_runs (id) ON DELETE CASCADE,

    -- Similarity signal (Agent 2 core output)
    cosine_similarity FLOAT        NOT NULL,
    rank              INTEGER      NOT NULL,   -- 1 = best match for this resume

    -- LLM-generated reasoning
    fit_category      fit_category NOT NULL,
    skill_gaps        TEXT[]       NOT NULL DEFAULT '{}',
    skill_matches     TEXT[]       NOT NULL DEFAULT '{}',
    reasoning         TEXT,

    ranked_at         TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT rankings_resume_cluster_run_uniq UNIQUE (resume_id, cluster_id, run_id),
    CONSTRAINT rankings_similarity_range        CHECK (cosine_similarity BETWEEN -1.0 AND 1.0),
    CONSTRAINT rankings_rank_positive           CHECK (rank > 0)
);

CREATE INDEX idx_rankings_resume_id   ON rankings (resume_id);
CREATE INDEX idx_rankings_cluster_id  ON rankings (cluster_id);
-- Primary sort for `careeros analyze` output
CREATE INDEX idx_rankings_resume_sim  ON rankings (resume_id, cosine_similarity DESC);
CREATE INDEX idx_rankings_fit         ON rankings (fit_category);


-- =============================================================================
-- LAYER 3 — DECISION
-- execution_plans · execution_actions
-- =============================================================================


-- ---------------------------------------------------------------------------
-- execution_plans
-- Agent 3 output: one plan per (resume, clustering_run).
-- Full structured plan stored as JSONB; individual actions normalized below.
-- ---------------------------------------------------------------------------

CREATE TABLE execution_plans (
    id          UUID             PRIMARY KEY DEFAULT uuid_generate_v4(),
    resume_id   UUID             NOT NULL REFERENCES resumes (id) ON DELETE CASCADE,
    run_id      UUID             NOT NULL REFERENCES clustering_runs (id) ON DELETE CASCADE,

    -- Full plan payload written by execution_engine.py
    -- Shape: { weekly_actions[], top_jobs[], resume_variants{}, skill_development[] }
    plan        JSONB            NOT NULL,

    -- Export file paths (written by CLI export command)
    json_export_path TEXT,
    xlsx_export_path TEXT,

    status      execution_status NOT NULL DEFAULT 'pending',

    created_at  TIMESTAMPTZ      NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ      NOT NULL DEFAULT now(),

    CONSTRAINT execution_plans_resume_run_uniq UNIQUE (resume_id, run_id)
);

CREATE INDEX idx_execution_plans_resume_id ON execution_plans (resume_id);
CREATE INDEX idx_execution_plans_status    ON execution_plans (status);


-- ---------------------------------------------------------------------------
-- execution_actions
-- Weekly tasks decomposed from the plan. Enables `careeros status` tracking.
-- ---------------------------------------------------------------------------

CREATE TABLE execution_actions (
    id            UUID             PRIMARY KEY DEFAULT uuid_generate_v4(),
    plan_id       UUID             NOT NULL REFERENCES execution_plans (id) ON DELETE CASCADE,
    week          INTEGER          NOT NULL,   -- 1-indexed
    day           INTEGER,                    -- 1=Mon … 5=Fri; NULL = any day that week
    action_type   TEXT             NOT NULL,  -- "apply" | "skill_build" | "network" | etc.
    description   TEXT             NOT NULL,
    job_id        UUID             REFERENCES jobs (id) ON DELETE SET NULL,
    status        execution_status NOT NULL DEFAULT 'pending',
    due_at        TIMESTAMPTZ,
    completed_at  TIMESTAMPTZ,
    created_at    TIMESTAMPTZ      NOT NULL DEFAULT now(),

    CONSTRAINT execution_actions_week_positive CHECK (week > 0),
    CONSTRAINT execution_actions_day_range     CHECK (day IS NULL OR day BETWEEN 1 AND 7)
);

CREATE INDEX idx_execution_actions_plan_id ON execution_actions (plan_id);
CREATE INDEX idx_execution_actions_status  ON execution_actions (status);
CREATE INDEX idx_execution_actions_week    ON execution_actions (plan_id, week);


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

CREATE TRIGGER trg_resumes_updated_at
    BEFORE UPDATE ON resumes
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_execution_plans_updated_at
    BEFORE UPDATE ON execution_plans
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- =============================================================================
-- SCHEMA SUMMARY
-- =============================================================================
--
--  Layer 1 — Data (Agent 1)
--  ┌──────────────────────────────┐
--  │ jobs                         │  raw + normalized job postings
--  │ job_embeddings               │  vector(1536) per job · HNSW
--  │ clustering_runs              │  KMeans run metadata
--  │ role_clusters                │  K centroids + LLM labels · HNSW
--  │ job_cluster_memberships      │  job → nearest cluster + L2 distance
--  └──────────────────────────────┘
--
--  Layer 2 — Intelligence (Agent 2)
--  ┌──────────────────────────────┐
--  │ resumes                      │  base + tailored variants
--  │ resume_embeddings            │  vector(1536) per resume · HNSW
--  │ rankings                     │  cosine similarity · fit_category · gaps
--  └──────────────────────────────┘
--
--  Layer 3 — Decision (Agent 3)
--  ┌──────────────────────────────┐
--  │ execution_plans              │  full JSONB plan per resume/run
--  │ execution_actions            │  weekly tasks decomposed from plan
--  └──────────────────────────────┘
--
--  10 tables · 7 ENUMs · 3 HNSW indexes · 3 updated_at triggers
-- =============================================================================