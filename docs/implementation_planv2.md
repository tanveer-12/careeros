# Lumia: Career‑clarity OS – Implementation Plan v2

**Goal:** Build a local‑first career‑intelligence system that maps user resumes against job‑market archetypes, then **generates prioritized learning paths** and micro‑action plans to unlock those roles, without relying on paid OpenAI API keys.  

**Data focus:**  
- Remote‑focused sources only (Remotive, plus optional future APIs). [web:3][web:6]  
- Embeddings via Hugging Face / local models (e.g., `Supabase/bge‑small‑en`). [web:53][web:59]  


---

## 1. Product vision

- **What Lumia is:**  
  - A personal career‑clarity OS that helps users answer:  
    - “Which kinds of roles fit me best?”  
    - “What should I learn to get there?”  
    - “What should I write on my resume and LinkedIn each week?”  

- **Scope boundaries:**  
  - Focus on **learning‑path‑driven growth**, not just job‑ranking.  
  - Use **Remotive** as the primary job‑data source; Greenhouse / Lever / Ashby are removed entirely. [web:3][web:6]  
  - Replace paid‑API embeddings with **Hugging Face / local models** (e.g., `Supabase/bge‑small‑en` via TEI). [web:53][web:59]  


---

## 2. High‑level architecture

Organize the system into four logical layers:

### Layer 1: Job‑data ingestion (Remotive‑only in MVP)

- Ingest job postings from:
  - **Himalayas** (remote‑focused, structured fields) — the **only** source in MVP. [web:3][web:6]  
- Normalize each job into:
  - Title, company, location(s), remote/hybrid/onsite, experience level, skills/tags.  
- Store in PostgreSQL for later use.  

### Layer 2: Embedding & clustering

- Use a **local Hugging Face embedding model** (e.g., `Supabase/bge‑small‑en`) to generate embeddings for each job text. [web:53][web:59]  
- Store embeddings in PostgreSQL using `pgvector`. [web:54]  
- Run clustering (K‑means or HDBSCAN) on job embeddings to discover natural role archetypes. [web:5][web:29]  
- For each cluster:
  - Assign a human‑readable archetype label (e.g., “ML Platform Engineering”, “Analytics Engineer”).  
  - Extract a list of key skills and responsibilities from the cluster’s jobs.  

### Layer 3: Resume‑to‑market mapping

- Support user resumes in:
  - Plain‑text or PDF.  
  - Store parsed sections: skills, experience, projects, education. [web:12]  
- Embed the resume using the **same HF model** as the jobs, then:
  - Compute a weighted embedding (prioritizing skills and experience).  
- Compute cosine similarity between the resume embedding and each archetype centroid. [web:7][web:29]  
- Rank archetypes by relevance and compute:
  - Skill‑match score (skills in resume vs archetype).  
  - **Skill‑gap list (skills in archetype but not in resume)** — this is the **core learning‑input**.  

### Layer 4: Learning‑path‑driven execution plan

- For a given user:
  - Inputs:
    - Resume.  
    - Selected archetype(s) and target constraints.  
  - Outputs:
    - **A 3–12‑week learning path** per key skill gap, e.g.:
      - “Learn dbt basics → 4 weeks”  
      - “Build 1 end‑to‑end ML pipeline project → 6 weeks”  
      - “Add 2 CI/CD examples to your resume → 1 week”  
    - For each week:
      - **Concrete micro‑actions**:
        - “Rewrite project X to emphasize MLOps / CI‑CD / data‑governance.”  
        - “Add Y to your resume bullets.”  
        - “Draft a LinkedIn post about X trend to signal your alignment.”  
      - **Resources** (optional, but valuable):
        - Links to free courses, docs, tutorials aligned with the skill gap (e.g., “Free SQL course on Khan Academy”, “dbt docs” etc.). [web:24]  
    - **One‑click reminders**:
      - “After you finish this week, you can update your LinkedIn to reflect X.”  
      - “Update this resume section once you complete Y.”  

---

## 3. MVP‑phase roadmap (learning‑path‑first)

### Phase 1: Data layer & ingestion (no ATS) — COMPLETE ✓

(Keep same as your current Phase 1, but explicitly state:)

- **No Greenhouse / Lever / Ashby scrapers.** ✓  
- **Only Remotive‑based ingestion.** ✓ (Himalayas scraper also added as a second source)  
- Schema migrated: all 10 tables + 5 enum types + pgvector indexes live in lumia_dev. ✓  
- Job normalizer (HTML stripping, salary parsing, domain/seniority inference) implemented. ✓  
- Skill enricher (180+ aliases, 3-stage enrichment, confidence scoring) implemented. ✓  
- CLI `lumia ingest` command functional. ✓  

---

### Layer 2: Embedding + Clustering Pipeline — Implementation Instructions
Files map
Action	File
Delete	core/clustering/kmeans.py
Modify	core/embeddings/__init__.py
Modify	core/embeddings/job_embedder.py
Modify	database/models/job_embeddings.py
Modify	database/models/clustering.py
Modify	database/models/job_cluster_memberships.py
Modify	database/migration/schema.sql
Create	core/clustering/reducer.py
Create	core/clustering/ctfidf.py
Create	core/clustering/hdbscan_engine.py
Step 0 — Delete K-means
Delete core/clustering/kmeans.py. It is fully replaced by hdbscan_engine.py.

Step 1 — core/embeddings/__init__.py
Add one constant and update __all__:


TEXT_VERSION         = "v2"   # bump this whenever _build_embedding_text() changes
Add "TEXT_VERSION" to __all__. Everything else in the file stays the same.

Why: TEXT_VERSION is stored alongside every embedding so you can detect stale embeddings after a text-assembly change and know exactly which jobs need re-embedding.

Step 2 — core/embeddings/job_embedder.py
2a. Imports — add at the top:


import re
from core.embeddings import MODEL_NAME, EMBEDDING_DIMENSIONS, MAX_CHARS, TEXT_VERSION
2b. Replace _build_embedding_text() with a richer version. Priority order: title block (never truncated) → seniority + domain (taxonomy anchor) → skills (highest signal for matching) → description (truncated last):


def _build_embedding_text(job: Job) -> str:
    title     = (job.title     or "").strip()
    company   = (job.company   or "").strip()
    location  = (job.location  or "").strip()
    seniority = (job.seniority or "").strip()
    domain    = (job.domain    or "").strip()
    skills    = ", ".join(job.skills_final or job.skills or [])

    # Strip residual HTML tags and collapse whitespace before truncating
    raw_desc = job.description or ""
    desc = re.sub(r"<[^>]+>", " ", raw_desc)
    desc = re.sub(r"\s+", " ", desc).strip()[:600]

    parts = [f"{title} at {company}"]
    if location:
        parts[0] += f" ({location})"
    if seniority:
        parts.append(seniority)
    if domain:
        parts.append(domain)
    if skills:
        parts.append(f"Skills: {skills}")
    if desc:
        parts.append(desc)

    return " | ".join(parts)[:MAX_CHARS]
2c. Add two text variant functions below _build_embedding_text:


def _build_title_only_text(job: Job) -> str:
    """Compact signal for title-only ablation tests."""
    parts = [job.title or "", job.seniority or "", job.domain or "", job.company or ""]
    return " ".join(p.strip() for p in parts if p.strip())[:MAX_CHARS]


def _build_description_only_text(job: Job) -> str:
    """Raw description text stripped of HTML, for description-only experiments."""
    raw = job.description or ""
    cleaned = re.sub(r"<[^>]+>", " ", raw)
    return re.sub(r"\s+", " ", cleaned).strip()[:MAX_CHARS]
2d. Update _store_embeddings() — add input_text_version and populate token_count in the JobEmbedding(...) constructor:


session.add(JobEmbedding(
    id                 = str(uuid.uuid4()),
    job_id             = job.id,
    embedding          = vector,
    model              = self.model_name,
    input_text         = text,
    input_text_version = TEXT_VERSION,
    token_count        = len(text.split()),  # word-count proxy; sufficient for tracking
    created_at         = now,
))
Step 3 — database/models/job_embeddings.py
Add one column after input_text:


input_text_version: Mapped[Optional[str]] = mapped_column(String)
Step 4 — database/models/clustering.py
ClusteringRun — add two columns:


algorithm:        Mapped[str]           = mapped_column(String, nullable=False, default="hdbscan")
unassigned_count: Mapped[Optional[int]] = mapped_column(Integer)
RoleCluster — add these columns. Add Boolean, Float, Text to sqlalchemy imports first:


summary:                Mapped[Optional[str]]        = mapped_column(String)
representative_job_ids: Mapped[Optional[List[str]]]  = mapped_column(JSON, default=list)
ctfidf_keywords:        Mapped[Optional[List[str]]]  = mapped_column(JSON, default=list)
density:                Mapped[Optional[float]]       = mapped_column(Float)
is_long_tail:           Mapped[bool]                 = mapped_column(Boolean, nullable=False, default=False)
ctfidf_keywords stores the raw top-15 c-TF-IDF terms before the label is chosen. It is the audit trail for the labeling step.

Step 5 — database/models/job_cluster_memberships.py
Add two columns for 2D UMAP coordinates (used for visualization only; the 5D coords used for HDBSCAN are ephemeral and not stored):


umap_x: Mapped[Optional[float]] = mapped_column(Float)
umap_y: Mapped[Optional[float]] = mapped_column(Float)
membership_prob: Mapped[Optional[float]] = mapped_column(Float)
membership_prob is HDBSCAN's soft-clustering probability (0.0–1.0). Jobs with membership_prob < 0.05 are weakly assigned and should be treated as borderline.

Add Optional to the typing import.

Step 6 — database/migration/schema.sql
Append a migration block before the schema summary comment:


-- =============================================================================
-- MIGRATION: Layer 2 semantic pipeline (UMAP + HDBSCAN + c-TF-IDF)
-- Run once against lumia_dev before executing hdbscan_engine.py
-- =============================================================================

ALTER TABLE job_embeddings
    ADD COLUMN IF NOT EXISTS input_text_version TEXT;

ALTER TABLE clustering_runs
    ADD COLUMN IF NOT EXISTS algorithm        TEXT    NOT NULL DEFAULT 'hdbscan',
    ADD COLUMN IF NOT EXISTS unassigned_count INTEGER;

ALTER TABLE role_clusters
    ADD COLUMN IF NOT EXISTS summary                TEXT,
    ADD COLUMN IF NOT EXISTS representative_job_ids JSONB NOT NULL DEFAULT '[]',
    ADD COLUMN IF NOT EXISTS ctfidf_keywords        JSONB NOT NULL DEFAULT '[]',
    ADD COLUMN IF NOT EXISTS density                REAL,
    ADD COLUMN IF NOT EXISTS is_long_tail           BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE job_cluster_memberships
    ADD COLUMN IF NOT EXISTS umap_x          REAL,
    ADD COLUMN IF NOT EXISTS umap_y          REAL,
    ADD COLUMN IF NOT EXISTS membership_prob REAL;
Step 7 — core/clustering/reducer.py (new file)
Single responsibility: accept a numpy matrix, return UMAP-reduced coordinates. No DB access.


"""
core/clustering/reducer.py

UMAP dimensionality reduction for job embeddings.

Rules:
- 5-dim output for HDBSCAN input (denser packing, more stable clusters).
- 2-dim output for visualization (call reduce(matrix, n_components=2)).
- UMAP is NOT used for retrieval — the 384-dim vectors in job_embeddings are
  the canonical representation. UMAP coords are ephemeral and tied to a run.
- min_dist=0.0 packs clusters tightly, which improves HDBSCAN recall.
"""
import logging
import numpy as np
from umap import UMAP

logger = logging.getLogger("lumia.clustering.reducer")


def reduce(matrix: np.ndarray, n_components: int = 5) -> np.ndarray:
    """
    Args:
        matrix:       float32 (n_jobs, 384), L2-normalized
        n_components: 5 for HDBSCAN input, 2 for 2D visualization

    Returns:
        float32 (n_jobs, n_components)
    """
    logger.info("UMAP: %d jobs → %d dims", matrix.shape[0], n_components)
    reducer = UMAP(
        n_components  = n_components,
        n_neighbors   = 15,
        min_dist      = 0.0,   # tight packing improves HDBSCAN
        metric        = "cosine",
        random_state  = 42,
        low_memory    = False,
    )
    out = reducer.fit_transform(matrix).astype(np.float32)
    logger.info("UMAP complete — output: %s", out.shape)
    return out
Step 8 — core/clustering/ctfidf.py (new file)
BERTopic-style c-TF-IDF. No BERTopic dependency — implemented directly with sklearn.CountVectorizer. The key insight: treat the entire job corpus of each cluster as one document, then compute IDF across clusters rather than individual jobs:


"""
core/clustering/ctfidf.py

Class-based TF-IDF (c-TF-IDF) for archetype keyword extraction.

Standard TF-IDF finds terms frequent in one document vs. others.
c-TF-IDF finds terms frequent in one CLUSTER vs. other clusters.

Algorithm:
1. Merge all job texts in a cluster into one cluster document.
2. Compute TF within each cluster document (normalized by cluster word count).
3. Compute IDF across cluster documents:
       idf(t) = log(1 + n_clusters / df(t))
   where df(t) = number of clusters containing term t.
4. c-TF-IDF score = TF_normalized * IDF.
5. Top-k terms per cluster are the most distinctive terms for that archetype.
"""
import logging
import numpy as np
from sklearn.feature_extraction.text import CountVectorizer

logger = logging.getLogger("lumia.clustering.ctfidf")


def extract_keywords(
    cluster_texts: dict[int, str],
    top_n: int = 15,
) -> dict[int, list[str]]:
    """
    Args:
        cluster_texts: {cluster_label: concatenated text of all jobs in cluster}
        top_n:         number of top keywords to return per cluster

    Returns:
        {cluster_label: [keyword, ...]}  — ordered by c-TF-IDF score descending
    """
    cluster_ids = sorted(cluster_texts.keys())
    docs        = [cluster_texts[ci] for ci in cluster_ids]

    vectorizer = CountVectorizer(
        stop_words  = "english",
        ngram_range = (1, 2),   # unigrams + bigrams to surface "data engineer", "machine learning"
        min_df      = 1,
        max_features= 15_000,
        token_pattern = r"(?u)\b[a-zA-Z][a-zA-Z0-9+#\-\.]{1,}\b",  # keep "c++", ".net", "devops"
    )

    # TF matrix: shape (n_clusters, vocab_size)
    tf_matrix = vectorizer.fit_transform(docs).toarray().astype(np.float64)

    # Normalize TF by cluster word count so large clusters don't dominate
    words_per_cluster = tf_matrix.sum(axis=1, keepdims=True)
    tf_norm           = tf_matrix / (words_per_cluster + 1e-9)

    # IDF across cluster documents (not individual documents)
    n_clusters        = len(docs)
    df                = (tf_matrix > 0).sum(axis=0)  # shape (vocab_size,)
    idf               = np.log(1 + n_clusters / (df + 1))

    ctfidf_matrix     = tf_norm * idf  # shape (n_clusters, vocab_size)

    vocab   = vectorizer.get_feature_names_out()
    result  = {}

    for i, ci in enumerate(cluster_ids):
        top_idx      = np.argsort(ctfidf_matrix[i])[::-1][:top_n]
        result[ci]   = [vocab[j] for j in top_idx]
        logger.debug("Cluster %d top terms: %s", ci, result[ci][:5])

    return result
Step 9 — core/clustering/hdbscan_engine.py (new file)
This module owns the entire archetype discovery pipeline: fetch → UMAP → HDBSCAN → c-TF-IDF → label → save:


"""
core/clustering/hdbscan_engine.py

Semantic archetype discovery pipeline:
  1. Fetch all job embeddings from DB
  2. UMAP (5-dim) for clustering; UMAP (2-dim) for visualization coordinates
  3. HDBSCAN on 5-dim vectors → cluster labels + membership probabilities
  4. c-TF-IDF on merged cluster corpora → top distinctive keywords per cluster
  5. Archetype labeling: best c-TF-IDF keyword scored against cluster centroid
  6. Save ClusteringRun, RoleCluster, JobClusterMembership (with umap_x/y + prob)

Run:  python -m core.clustering.hdbscan_engine
"""
import asyncio
import collections
import logging
import re
import uuid
from datetime import datetime, timezone

import hdbscan
import numpy as np
from sklearn.preprocessing import normalize
from sqlalchemy import select

from core.clustering.ctfidf import extract_keywords
from core.clustering.reducer import reduce
from core.embeddings import MODEL_NAME
from database.models.clustering import ClusteringRun, RoleCluster
from database.models.job_cluster_memberships import JobClusterMembership
from database.models.job_embeddings import JobEmbedding
from database.models.jobs import Job
from database.session import async_session
from sentence_transformers import SentenceTransformer

logger = logging.getLogger("lumia.clustering.hdbscan")

# ── HDBSCAN parameters ────────────────────────────────────────────────────────
# min_cluster_size: smallest group that counts as a real archetype.
#   Too small → noisy micro-clusters. Too large → you miss real niches.
#   Start at 10; reduce to 5 if you have fewer than 500 jobs.
_HDBSCAN_PARAMS = dict(
    min_cluster_size         = 10,
    min_samples              = 5,
    metric                   = "euclidean",   # UMAP output → Euclidean is correct
    cluster_selection_method = "eom",          # "excess of mass" handles variable densities
    prediction_data          = True,           # required for soft cluster probabilities
)

# Clusters below this size after discovery are marked is_long_tail=True
_LONG_TAIL_THRESHOLD = 10


class HDBSCANClusteringEngine:

    def __init__(self) -> None:
        self.model_name = MODEL_NAME
        self.model      = SentenceTransformer(MODEL_NAME)

    # ─────────────────────────────────────────────────────────────────────────
    # Public entry point
    # ─────────────────────────────────────────────────────────────────────────

    async def run(self, force: bool = False) -> str | None:
        """Full pipeline. Returns run_id on success, None on failure."""

        # ── 1. Fetch embeddings ───────────────────────────────────────────────
        async with async_session() as session:
            rows = (await session.execute(
                select(
                    JobEmbedding.job_id,
                    JobEmbedding.embedding,
                    JobEmbedding.input_text,
                    Job.skills_final,
                    Job.title,
                    Job.domain,
                )
                .join(Job, Job.id == JobEmbedding.job_id)
                .where(JobEmbedding.model == self.model_name)
            )).all()

        if not rows:
            logger.error("No embeddings found — run embed_jobs first.")
            return None

        job_ids     = [r.job_id       for r in rows]
        input_texts = [r.input_text or "" for r in rows]
        skills_list = [r.skills_final or [] for r in rows]
        titles      = [r.title or ""   for r in rows]
        domains     = [r.domain or ""  for r in rows]

        raw_vecs    = [np.array(r.embedding, dtype=np.float32) for r in rows]
        matrix      = normalize(np.vstack(raw_vecs), norm="l2").astype(np.float32)
        logger.info("Fetched %d job embeddings", len(rows))

        # ── 2. UMAP ───────────────────────────────────────────────────────────
        loop = asyncio.get_event_loop()
        # 5-dim for HDBSCAN input
        reduced_5d = await loop.run_in_executor(None, lambda: reduce(matrix, n_components=5))
        # 2-dim for visualization (stored in memberships)
        reduced_2d = await loop.run_in_executor(None, lambda: reduce(matrix, n_components=2))

        # ── 3. HDBSCAN ────────────────────────────────────────────────────────
        logger.info("Running HDBSCAN on %d jobs (5-dim UMAP space)...", len(rows))
        clusterer = hdbscan.HDBSCAN(**_HDBSCAN_PARAMS)
        clusterer.fit(reduced_5d)

        labels        = clusterer.labels_       # -1 = noise/unassigned
        probs         = clusterer.probabilities_ # per-job cluster membership confidence
        unique_labels = [l for l in sorted(set(labels)) if l != -1]
        n_clusters    = len(unique_labels)
        n_unassigned  = int((labels == -1).sum())
        logger.info("HDBSCAN: %d archetypes, %d unassigned noise jobs", n_clusters, n_unassigned)

        # ── 4. Build cluster corpora and run c-TF-IDF ─────────────────────────
        # Group job indices by cluster label
        jobs_by_cluster: dict[int, list[int]] = collections.defaultdict(list)
        for idx, label in enumerate(labels):
            if label != -1:
                jobs_by_cluster[label].append(idx)

        # Merge all input_text for each cluster into one corpus document
        cluster_corpus: dict[int, str] = {
            ci: " ".join(input_texts[idx] for idx in idxs)
            for ci, idxs in jobs_by_cluster.items()
        }
        ctfidf_keywords = extract_keywords(cluster_corpus, top_n=15)

        # ── 5–6. Label + save ─────────────────────────────────────────────────
        async with async_session() as session:
            run = ClusteringRun(
                id               = str(uuid.uuid4()),
                model            = self.model_name,
                algorithm        = "hdbscan",
                k                = n_clusters,
                job_count        = len(rows),
                unassigned_count = n_unassigned,
                run_at           = datetime.now(timezone.utc),
                notes            = (
                    f"HDBSCAN min_cluster_size={_HDBSCAN_PARAMS['min_cluster_size']} "
                    f"min_samples={_HDBSCAN_PARAMS['min_samples']}"
                ),
            )
            session.add(run)
            await session.flush()
            run_id = run.id

            for ci in unique_labels:
                idxs = jobs_by_cluster[ci]

                # Centroid: mean of full 384-dim vectors, re-normalized
                cluster_vecs = matrix[idxs]
                centroid     = cluster_vecs.mean(axis=0)
                centroid    /= (np.linalg.norm(centroid) + 1e-9)

                # Density: mean L2 distance of members to centroid
                distances = np.linalg.norm(cluster_vecs - centroid, axis=1)
                density   = float(distances.mean())

                # Representative jobs: 5 closest to centroid in full 384-dim space
                closest_rank  = np.argsort(distances)[:5]
                rep_job_ids   = [job_ids[idxs[r]] for r in closest_rank]

                # Top skills across cluster
                top_skills = [
                    skill for skill, _ in collections.Counter(
                        s for idx in idxs for s in skills_list[idx]
                    ).most_common(10)
                ]

                # Label: pick c-TF-IDF keyword whose embedding is closest to centroid
                keywords  = ctfidf_keywords.get(ci, [])
                label, summary = await self._label_from_ctfidf(
                    keywords, centroid, [titles[idx] for idx in idxs[:30]]
                )

                role_cluster = RoleCluster(
                    id                     = str(uuid.uuid4()),
                    run_id                 = run_id,
                    cluster_index          = ci,
                    label                  = label,
                    summary                = summary,
                    centroid               = centroid.tolist(),
                    top_skills             = top_skills,
                    job_count              = len(idxs),
                    representative_job_ids = rep_job_ids,
                    ctfidf_keywords        = keywords,
                    density                = density,
                    is_long_tail           = len(idxs) < _LONG_TAIL_THRESHOLD,
                )
                session.add(role_cluster)
                await session.flush()

                memberships = [
                    JobClusterMembership(
                        id                   = str(uuid.uuid4()),
                        job_id               = job_ids[idxs[rank]],
                        cluster_id           = role_cluster.id,
                        run_id               = run_id,
                        distance_to_centroid = float(distances[rank]),
                        membership_prob      = float(probs[idxs[rank]]),
                        umap_x               = float(reduced_2d[idxs[rank], 0]),
                        umap_y               = float(reduced_2d[idxs[rank], 1]),
                    )
                    for rank in range(len(idxs))
                ]
                session.add_all(memberships)

            await session.commit()

        logger.info("Done — run_id=%s | %d archetypes | %d unassigned", run_id, n_clusters, n_unassigned)
        return run_id

    # ─────────────────────────────────────────────────────────────────────────
    # Labeling
    # ─────────────────────────────────────────────────────────────────────────

    async def _label_from_ctfidf(
        self,
        keywords: list[str],
        centroid: np.ndarray,
        sample_titles: list[str],
    ) -> tuple[str, str]:
        """
        Choose the best archetype label from c-TF-IDF keyword candidates.

        Strategy:
          1. Use c-TF-IDF keywords as candidates (these are already distinctive
             within the cluster vs. other clusters).
          2. Embed each candidate and score against the cluster centroid.
          3. The candidate with the highest cosine similarity to the centroid
             wins — it is both distinctive (c-TF-IDF) and semantically central.
          4. Summary = top 8 keywords joined, for display and debugging.

        Returns:
            (label, summary)
        """
        if not keywords:
            return "other", ""

        loop = asyncio.get_event_loop()
        keyword_vecs = await loop.run_in_executor(
            None,
            lambda kw=keywords: self.model.encode(kw, normalize_embeddings=True),
        )

        scores = keyword_vecs @ centroid
        label  = keywords[int(np.argmax(scores))]
        summary = ", ".join(keywords[:8])
        return label, summary
Step 10 — New dependencies
Install before running:


pip install umap-learn hdbscan scikit-learn
On Windows, if hdbscan fails to build: pip install hdbscan --no-build-isolation. umap-learn requires numba; it installs automatically but the first UMAP call will trigger a JIT compile (~30 seconds, cached after).

Execution order

# 1. Run the schema migration once
psql -d lumia_dev -f database/migration/schema.sql

# 2. Embed all un-embedded jobs (text assembly v2 + token count)
python -m core.embeddings.job_embedder

# 3. Run the full archetype discovery pipeline
python -m core.clustering.hdbscan_engine
Data flow summary

job_embeddings (384-dim, canonical)
    │
    ├─ UMAP(5-dim) ──► HDBSCAN ──► labels + probs
    │
    ├─ UMAP(2-dim) ──► umap_x, umap_y per job (stored in job_cluster_memberships)
    │
    └─ cluster corpus ──► c-TF-IDF ──► keywords ──► embed ──► score vs centroid ──► label

Stored per run:
  clustering_runs        — algorithm, k, unassigned_count
  role_clusters          — label, summary, ctfidf_keywords, centroid (384-dim),
                           top_skills, representative_job_ids, density, is_long_tail
  job_cluster_memberships — distance_to_centroid, 
---

### Phase 3: Resume‑to‑market mapping + skill‑gaps

- **Emphasize:**
  - The **skill‑gap list** is the **primary input** into the learning‑path generator.  
  - For each archetype, the system outputs:
    - “You need to learn: A, B, C.”  
    - “You already have: X, Y.”  

---

### Phase 4: Learning‑path‑engine design

- **Define a “learning‑path” schema:**
  - Fields:
    - `skill_gap`  
    - `recommended_resource_links` (URLs, optional)  
    - `estimated_weeks`  
    - `weekly_actions` (array of micro‑tasks)  
- **Implement a path‑generator function:**
  - For each skill gap:
    - Decide level: “intro”, “intermediate”, “project‑level”.  
    - Generate:
      - Recommended resources (free‑tier where possible).  
      - Micro‑actions (e.g., “Build Z”, “Rewrite Q”).  
- **Store learning‑paths** in the DB (e.g., `learning_paths`, `learning_path_steps`).  

### Phase 5: Weekly execution plan (2‑week learning‑focused)

- Implement a “2‑week plan” generator that:
  - Takes:
    - User’s resume.  
    - Skill‑gap list.  
    - Current archetype(s).  
  - Outputs:
    - A **2‑week plan**:
      - **Week 1:**
        - 1–2 learning tasks (e.g., “Start course X”, “Read docs for Y”, “Build Z”).  
        - 1–2 writing / LinkedIn tasks:
          - “Rewrite resume bullet for project A to emphasize B.”  
          - “Draft a LinkedIn post about starting X.”  
      - **Week 2:**
        - 1–2 learning tasks (e.g., “Finish module 1 of X”, “Build 1 mini‑project”).  
        - 1–2 writing / LinkedIn tasks:
          - “Add completed X to your resume bullets.”  
          - “Draft a follow‑up LinkedIn post about what you learned.”  
        - Optional:
          - 0–1 “apply”‑type tasks:
            - “Apply to 2–3 roles that match archetype X.”  
  - The **2‑week plan is the default and only option in MVP**.  
  - Long‑term plans (4–8–12 weeks) will be added in future stages.

- Expose:
  - A simple API / UI view that shows:
    - “2‑week learning‑and‑writing plan: learning + writing + optional apply.”  
  - Clear labels:
    - “This is a 2‑week starter plan. Extended plans will come later.”

### Phase 6: Light‑themed web‑app prototype (learning‑journey UI) — SCAFFOLD COMPLETE ✓ (mock data only; backend integration pending)

Built with **Next.js 14 App Router** (not Vite), Tailwind CSS, and Framer Motion:

- Landing page (`/`) with hero, 3-step explainer, animated market ticker, and CTAs. ✓  
- Upload page (`/upload`) with dropzone, progress simulation, PDF/DOCX support. ✓  
- Clusters page (`/clusters`) with animated 3D orbit visualization (Three.js). ✓  
- 2-week plan page (`/plan`) with week-by-week tasks, checkboxes, and expandable details. ✓  
- `BottomNav`, `OwlCompanion`, and `OwlLogo` components implemented. ✓  
- All pages currently use mock data (`lib/mockData.ts`); real API calls not yet wired. ⬜  

- Implement a minimal UI where the user:
  - Uploads a resume.  
  - Views:
    - Top archetypes.  
    - Skill‑gap list.  
    - Full learning path (timeline).  
    - Weekly plan.  
- Use:
  - **Light‑themed, soothing design** with **clear sections** for:
    - “Your archetypes”  
    - “Skill gaps → Learning path”  
    - “This week’s plan (learn + write + LinkedIn)”  
- Add:
  - Simple “mark as done” for weekly tasks.  
  - Optional “Add LinkedIn‑post‑draft” suggestions.  

---

## 4. Non‑functional considerations

- **Focus on “learning as the core metric”:**
  - User progress is tracked by:
    - Weeks completed.  
    - Skill‑gap resolution (e.g., “You’ve closed 4 of 7 gaps”).  
- **Keep job‑data secondary;**
  - The “apply”‑side of the plan is **optional**, not the core value.  

---

## 5. Git / branch strategy

- Keep `main` as the “source of truth”.  
- Use `refactor/v2-dev` to:
  - Remove ATS scrapers.  
  - Add `learning_paths` / `learning_path_steps` tables.  
  - Build the **learning‑path‑engine** and **LinkedIn‑suggestion logic**.  
- When stable, merge back to `main`.  