-- =============================================================================
-- Lumia · PostgreSQL + pgvector
-- Version: 0.2.0  |  Status: MVP
-- =============================================================================
-- Execution order matters — run top to bottom on a fresh database.
-- Idempotent via IF NOT EXISTS guards.
-- For upgrading an existing lumia_dev from v0.1.0, run the migration block
-- at the bottom of this file instead of re-creating from scratch.
-- =============================================================================


-- ---------------------------------------------------------------------------
-- EXTENSIONS
-- ---------------------------------------------------------------------------

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;   -- trigram index on job titles


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

CREATE TYPE week_plan_status AS ENUM (
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
-- jobs · job_embeddings
-- =============================================================================


-- ---------------------------------------------------------------------------
-- jobs
-- ---------------------------------------------------------------------------

CREATE TABLE jobs (
    id               UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),

    source           job_source      NOT NULL,
    external_id      TEXT            NOT NULL,
    source_url       TEXT            NOT NULL,

    raw_payload      JSONB           NOT NULL,
    scraped_at       TIMESTAMPTZ     NOT NULL DEFAULT now(),

    title            TEXT,
    company          TEXT,
    location         TEXT,
    work_location    work_location,
    employment_type  employment_type,
    description      TEXT,
    skills           TEXT[],
    domain           TEXT,
    seniority        TEXT,
    salary_currency  CHAR(3),
    salary_min       INTEGER,
    salary_max       INTEGER,
    posted_at        TIMESTAMPTZ,
    closes_at        TIMESTAMPTZ,

    skills_extracted      TEXT[],
    skills_normalized     TEXT[],
    skills_inferred       TEXT[],
    skills_final          TEXT[]  NOT NULL DEFAULT '{}',
    skills_confidence     REAL,
    skills_source_version TEXT,

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
CREATE INDEX idx_jobs_skills_final ON jobs USING gin (skills_final);


-- ---------------------------------------------------------------------------
-- job_embeddings
-- ---------------------------------------------------------------------------

CREATE TABLE job_embeddings (
    id                   UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id               UUID         NOT NULL REFERENCES jobs (id) ON DELETE CASCADE,
    model                TEXT         NOT NULL,
    embedding            vector(384)  NOT NULL,
    input_text           TEXT         NOT NULL,
    input_text_version   TEXT,
    token_count          INTEGER,
    created_at           TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT job_embeddings_job_model_uniq UNIQUE (job_id, model)
);

CREATE INDEX idx_job_embeddings_hnsw
    ON job_embeddings
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);


-- =============================================================================
-- LAYER 2 — ARCHETYPE TAXONOMY
-- role_archetypes: predefined job-role taxonomy with corpus-bootstrapped centroids
-- =============================================================================

CREATE TABLE role_archetypes (
    id               UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    title            TEXT         NOT NULL UNIQUE,
    category         TEXT         NOT NULL,
    canonical_skills TEXT[]       NOT NULL DEFAULT '{}',
    -- NULL until bootstrapper runs; title-embed fallback keeps job_count = 0
    centroid         vector(384),
    job_count        INTEGER      NOT NULL DEFAULT 0,
    built_at         TIMESTAMPTZ,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- HNSW index for fast resume → archetype cosine similarity lookup
CREATE INDEX idx_role_archetypes_centroid_hnsw
    ON role_archetypes
    USING hnsw (centroid vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE INDEX idx_role_archetypes_category ON role_archetypes (category);


-- =============================================================================
-- LAYER 3 — INTELLIGENCE
-- user_resumes · resume_embeddings · rankings
-- =============================================================================


-- ---------------------------------------------------------------------------
-- user_resumes
-- ---------------------------------------------------------------------------

CREATE TABLE user_resumes (
    id               UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id          TEXT         NOT NULL,

    file_name        TEXT         NOT NULL,
    file_path        TEXT,

    raw_text         TEXT         NOT NULL,
    parsed_skills    TEXT[]       NOT NULL DEFAULT '{}',
    parsed_titles    TEXT[]       NOT NULL DEFAULT '{}',
    parsed_years_exp INTEGER,

    is_embedded      BOOLEAN      NOT NULL DEFAULT FALSE,

    created_at       TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX idx_user_resumes_user_id  ON user_resumes (user_id);
CREATE INDEX idx_user_resumes_embedded ON user_resumes (is_embedded);


-- ---------------------------------------------------------------------------
-- resume_embeddings
-- ---------------------------------------------------------------------------

CREATE TABLE resume_embeddings (
    id           UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    resume_id    UUID         NOT NULL REFERENCES user_resumes (id) ON DELETE CASCADE,
    model        TEXT         NOT NULL,
    embedding    vector(384)  NOT NULL,
    input_text   TEXT         NOT NULL,
    token_count  INTEGER,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT resume_embeddings_resume_model_uniq UNIQUE (resume_id, model)
);

CREATE INDEX idx_resume_embeddings_hnsw
    ON resume_embeddings
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);


-- ---------------------------------------------------------------------------
-- rankings
-- One row per (resume, archetype). cosine_similarity drives rank.
-- ---------------------------------------------------------------------------

CREATE TABLE rankings (
    id                UUID          PRIMARY KEY DEFAULT uuid_generate_v4(),
    resume_id         UUID          NOT NULL REFERENCES user_resumes (id) ON DELETE CASCADE,
    archetype_id      UUID          NOT NULL REFERENCES role_archetypes (id) ON DELETE CASCADE,

    cosine_similarity FLOAT         NOT NULL,
    rank              INTEGER       NOT NULL,
    fit_category      fit_category  NOT NULL,
    skill_gaps        TEXT[]        NOT NULL DEFAULT '{}',
    skill_matches     TEXT[]        NOT NULL DEFAULT '{}',
    reasoning         TEXT,

    ranked_at         TIMESTAMPTZ   NOT NULL DEFAULT now(),

    CONSTRAINT rankings_resume_archetype_uniq  UNIQUE (resume_id, archetype_id),
    CONSTRAINT rankings_similarity_range       CHECK (cosine_similarity BETWEEN -1.0 AND 1.0),
    CONSTRAINT rankings_rank_positive          CHECK (rank > 0)
);

CREATE INDEX idx_rankings_resume_id  ON rankings (resume_id);
CREATE INDEX idx_rankings_archetype_id ON rankings (archetype_id);
CREATE INDEX idx_rankings_resume_sim ON rankings (resume_id, cosine_similarity DESC);
CREATE INDEX idx_rankings_fit        ON rankings (fit_category);


-- =============================================================================
-- LAYER 4 — DECISION
-- two_week_plans · two_week_plan_steps
-- =============================================================================

CREATE TABLE two_week_plans (
    id                      UUID             PRIMARY KEY DEFAULT uuid_generate_v4(),
    resume_id               UUID             NOT NULL REFERENCES user_resumes (id) ON DELETE CASCADE,
    archetype_id            UUID             NOT NULL REFERENCES role_archetypes (id) ON DELETE CASCADE,

    target_location         TEXT,
    target_work_style       TEXT,
    target_employment_type  TEXT,

    status                  week_plan_status NOT NULL DEFAULT 'active',

    created_at              TIMESTAMPTZ      NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ      NOT NULL DEFAULT now(),

    CONSTRAINT two_week_plans_resume_archetype_uniq UNIQUE (resume_id, archetype_id, status)
);

CREATE INDEX idx_two_week_plans_resume_id    ON two_week_plans (resume_id);
CREATE INDEX idx_two_week_plans_archetype_id ON two_week_plans (archetype_id);
CREATE INDEX idx_two_week_plans_status       ON two_week_plans (status);


CREATE TABLE two_week_plan_steps (
    id               UUID           PRIMARY KEY DEFAULT uuid_generate_v4(),
    plan_id          UUID           NOT NULL REFERENCES two_week_plans (id) ON DELETE CASCADE,
    week_number      INTEGER        NOT NULL,
    step_type        plan_step_type NOT NULL,

    title            TEXT           NOT NULL,
    description      TEXT           NOT NULL,
    resource_links   TEXT[],
    estimated_hours  FLOAT,
    ai_explanation   TEXT,
    is_completed     BOOLEAN        NOT NULL DEFAULT FALSE,

    created_at       TIMESTAMPTZ    NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ    NOT NULL DEFAULT now(),

    CONSTRAINT two_week_plan_steps_week_range CHECK (week_number IN (1, 2)),
    CONSTRAINT two_week_plan_steps_hours_positive CHECK (estimated_hours IS NULL OR estimated_hours > 0)
);

CREATE INDEX idx_two_week_plan_steps_plan_id ON two_week_plan_steps (plan_id);
CREATE INDEX idx_two_week_plan_steps_week    ON two_week_plan_steps (plan_id, week_number);


-- =============================================================================
-- UTILITY — updated_at triggers
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

CREATE TRIGGER trg_two_week_plan_steps_updated_at
    BEFORE UPDATE ON two_week_plan_steps
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- =============================================================================
-- MIGRATION: v0.1.0 → v0.2.0  (run against existing lumia_dev)
-- Replaces clustering tables with predefined role_archetypes taxonomy.
-- Safe to run multiple times (idempotent).
-- =============================================================================

/*
-- Step 1: drop clustering tables (cascades to old rankings + two_week_plans FKs)
DROP TABLE IF EXISTS job_cluster_memberships CASCADE;
DROP TABLE IF EXISTS role_clusters           CASCADE;
DROP TABLE IF EXISTS clustering_runs         CASCADE;

-- Step 2: create role_archetypes
CREATE TABLE IF NOT EXISTS role_archetypes (
    id               UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    title            TEXT         NOT NULL UNIQUE,
    category         TEXT         NOT NULL,
    canonical_skills TEXT[]       NOT NULL DEFAULT '{}',
    centroid         vector(384),
    job_count        INTEGER      NOT NULL DEFAULT 0,
    built_at         TIMESTAMPTZ,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_role_archetypes_centroid_hnsw
    ON role_archetypes
    USING hnsw (centroid vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS idx_role_archetypes_category ON role_archetypes (category);

-- Step 3: recreate rankings pointing to role_archetypes
DROP TABLE IF EXISTS rankings CASCADE;
CREATE TABLE rankings (
    id                UUID          PRIMARY KEY DEFAULT uuid_generate_v4(),
    resume_id         UUID          NOT NULL REFERENCES user_resumes (id) ON DELETE CASCADE,
    archetype_id      UUID          NOT NULL REFERENCES role_archetypes (id) ON DELETE CASCADE,
    cosine_similarity FLOAT         NOT NULL,
    rank              INTEGER       NOT NULL,
    fit_category      fit_category  NOT NULL,
    skill_gaps        TEXT[]        NOT NULL DEFAULT '{}',
    skill_matches     TEXT[]        NOT NULL DEFAULT '{}',
    reasoning         TEXT,
    ranked_at         TIMESTAMPTZ   NOT NULL DEFAULT now(),
    CONSTRAINT rankings_resume_archetype_uniq  UNIQUE (resume_id, archetype_id),
    CONSTRAINT rankings_similarity_range       CHECK (cosine_similarity BETWEEN -1.0 AND 1.0),
    CONSTRAINT rankings_rank_positive          CHECK (rank > 0)
);

-- Step 4: recreate two_week_plans pointing to role_archetypes
DROP TABLE IF EXISTS two_week_plan_steps CASCADE;
DROP TABLE IF EXISTS two_week_plans      CASCADE;

CREATE TABLE two_week_plans (
    id                      UUID             PRIMARY KEY DEFAULT uuid_generate_v4(),
    resume_id               UUID             NOT NULL REFERENCES user_resumes (id) ON DELETE CASCADE,
    archetype_id            UUID             NOT NULL REFERENCES role_archetypes (id) ON DELETE CASCADE,
    target_location         TEXT,
    target_work_style       TEXT,
    target_employment_type  TEXT,
    status                  week_plan_status NOT NULL DEFAULT 'active',
    created_at              TIMESTAMPTZ      NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ      NOT NULL DEFAULT now(),
    CONSTRAINT two_week_plans_resume_archetype_uniq UNIQUE (resume_id, archetype_id, status)
);

CREATE TABLE two_week_plan_steps (
    id               UUID           PRIMARY KEY DEFAULT uuid_generate_v4(),
    plan_id          UUID           NOT NULL REFERENCES two_week_plans (id) ON DELETE CASCADE,
    week_number      INTEGER        NOT NULL,
    step_type        plan_step_type NOT NULL,
    title            TEXT           NOT NULL,
    description      TEXT           NOT NULL,
    resource_links   TEXT[],
    estimated_hours  FLOAT,
    ai_explanation   TEXT,
    is_completed     BOOLEAN        NOT NULL DEFAULT FALSE,
    created_at       TIMESTAMPTZ    NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ    NOT NULL DEFAULT now(),
    CONSTRAINT two_week_plan_steps_week_range CHECK (week_number IN (1, 2)),
    CONSTRAINT two_week_plan_steps_hours_positive CHECK (estimated_hours IS NULL OR estimated_hours > 0)
);

-- Step 5: add input_text_version to job_embeddings if missing
ALTER TABLE job_embeddings ADD COLUMN IF NOT EXISTS input_text_version TEXT;
*/


-- =============================================================================
-- SCHEMA SUMMARY (v0.2.0)
-- =============================================================================

/*
  Layer 1 — Data
  ┌──────────────────────────────┐
  │ jobs                         │  raw + normalized job postings
  │ job_embeddings               │  vector(384) · HNSW
  └──────────────────────────────┘

  Layer 2 — Archetype Taxonomy
  ┌──────────────────────────────┐
  │ role_archetypes              │  ~280 predefined role archetypes
  │                              │  centroid = corpus mean or title embed
  │                              │  canonical_skills = top-10 from corpus
  └──────────────────────────────┘

  Layer 3 — Intelligence
  ┌──────────────────────────────┐
  │ user_resumes                 │  per-user uploaded resume
  │ resume_embeddings            │  vector(384) · HNSW
  │ rankings                     │  resume → top archetypes + skill gaps
  └──────────────────────────────┘

  Layer 4 — Decision
  ┌──────────────────────────────┐
  │ two_week_plans               │  2-week execution plan per resume/archetype
  │ two_week_plan_steps          │  weekly tasks with AI explanation
  └──────────────────────────────┘

  9 tables · 6 ENUMs · 3 HNSW indexes · 4 updated_at triggers
*/
