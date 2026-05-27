"""
core/clustering/hdbscan_engine.py

Semantic archetype discovery pipeline:
  1. Fetch all job embeddings from DB
  2. UMAP (5-dim) on full 384-dim vectors → compact space for HDBSCAN
  3. UMAP (2-dim) independently → (x, y) coordinates for visualization
  4. HDBSCAN on 5-dim vectors → cluster labels + per-job membership probabilities
  5. Merge all job texts per cluster → c-TF-IDF → top distinctive keywords
  6. Label each archetype: embed c-TF-IDF keywords, pick closest to cluster centroid
  7. Compute per-cluster statistics: centroid, density, top skills, representatives
  8. Persist: ClusteringRun, RoleCluster, JobClusterMembership (with umap_x/y + prob)

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
from sentence_transformers import SentenceTransformer
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

logger = logging.getLogger("lumia.clustering.hdbscan")

# ── HDBSCAN parameters ─────────────────────────────────────────────────────────
# min_cluster_size: smallest group that qualifies as a real archetype.
#   Reduce to 5 if you have fewer than ~500 jobs total.
# min_samples:      controls conservativeness of cluster boundaries.
#   Higher = more noise points but tighter clusters.
# cluster_selection_method = "eom": excess-of-mass — handles variable-density
#   clusters well; better than "leaf" for job markets with mixed densities.
_HDBSCAN_PARAMS = dict(
    min_cluster_size         = 10,
    min_samples              = 5,
    metric                   = "euclidean",  # correct after UMAP projection
    cluster_selection_method = "eom",
    prediction_data          = True,          # enables soft membership probabilities
)

# Clusters with fewer jobs than this after discovery are flagged is_long_tail=True
_LONG_TAIL_THRESHOLD = 10


class HDBSCANClusteringEngine:

    def __init__(self) -> None:
        self.model_name = MODEL_NAME
        self.model      = SentenceTransformer(MODEL_NAME)

    # ── Public entry point ─────────────────────────────────────────────────────

    async def run(self, force: bool = False) -> str | None:
        """
        Execute the full archetype discovery pipeline.
        Returns the run_id on success, None if no embeddings found.
        """

        # ── 1. Fetch embeddings from DB ────────────────────────────────────────
        async with async_session() as session:
            rows = (await session.execute(
                select(
                    JobEmbedding.job_id,
                    JobEmbedding.embedding,
                    JobEmbedding.input_text,
                    Job.skills_final,
                    Job.title,
                    Job.domain,
                    Job.company,
                )
                .join(Job, Job.id == JobEmbedding.job_id)
                .where(JobEmbedding.model == self.model_name)
            )).all()

        if not rows:
            logger.error("No embeddings found — run embed_jobs first.")
            return None

        job_ids      = [r.job_id       for r in rows]
        input_texts  = [r.input_text or "" for r in rows]
        skills_list  = [r.skills_final or [] for r in rows]
        titles       = [r.title or ""   for r in rows]
        companies    = [r.company or ""  for r in rows]

        # Build a stop-word set from company names so c-TF-IDF never labels a
        # cluster by its employer (e.g. "speechify", "grafana labs").
        # We tokenize each company name and add every resulting token.
        company_stop_words: set[str] = set()
        for co in companies:
            tokens = re.sub(r"[^a-z ]", " ", co.lower()).split()
            company_stop_words.update(t for t in tokens if len(t) > 1)
            if len(tokens) >= 2:
                company_stop_words.add(" ".join(tokens))

        raw_vecs = [np.array(r.embedding, dtype=np.float32) for r in rows]
        matrix   = normalize(np.vstack(raw_vecs), norm="l2").astype(np.float32)
        logger.info("Fetched %d job embeddings", len(rows))

        # ── 2 & 3. UMAP — run both reductions in the thread pool ───────────────
        loop = asyncio.get_event_loop()
        logger.info("Running UMAP 5-dim (for HDBSCAN) and 2-dim (for visualization)...")
        reduced_5d, reduced_2d = await asyncio.gather(
            loop.run_in_executor(None, lambda: reduce(matrix, n_components=5)),
            loop.run_in_executor(None, lambda: reduce(matrix, n_components=2)),
        )

        # ── 4. HDBSCAN on 5-dim UMAP vectors ──────────────────────────────────
        logger.info("Running HDBSCAN...")
        clusterer = hdbscan.HDBSCAN(**_HDBSCAN_PARAMS)
        clusterer.fit(reduced_5d)

        labels        = clusterer.labels_        # -1 = noise / unassigned
        probs         = clusterer.probabilities_  # per-job membership confidence
        unique_labels = sorted(set(labels) - {-1})
        n_clusters    = len(unique_labels)
        n_unassigned  = int((labels == -1).sum())
        logger.info(
            "HDBSCAN complete — %d archetypes discovered, %d jobs unassigned (noise)",
            n_clusters, n_unassigned,
        )

        # Group job indices by cluster label
        jobs_by_cluster: dict[int, list[int]] = collections.defaultdict(list)
        for idx, label in enumerate(labels):
            if label != -1:
                jobs_by_cluster[label].append(idx)

        # ── 5. c-TF-IDF keyword extraction ────────────────────────────────────
        # Merge all input_text for each cluster into one corpus document
        cluster_corpus: dict[int, str] = {
            ci: " ".join(input_texts[idx] for idx in idxs)
            for ci, idxs in jobs_by_cluster.items()
        }
        ctfidf_by_cluster = extract_keywords(
            cluster_corpus, top_n=15, extra_stop_words=company_stop_words
        )
        logger.info("c-TF-IDF extraction complete for %d clusters", len(ctfidf_by_cluster))

        # ── 6–8. Per-cluster: label, statistics, persist ───────────────────────
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
                    f"min_samples={_HDBSCAN_PARAMS['min_samples']} "
                    f"method={_HDBSCAN_PARAMS['cluster_selection_method']}"
                ),
            )
            session.add(run)
            await session.flush()
            run_id = run.id
            logger.info("ClusteringRun created: %s", run_id)

            for ci in unique_labels:
                idxs = jobs_by_cluster[ci]

                # Centroid: mean of full 384-dim unit vectors, re-normalized
                cluster_vecs = matrix[idxs]            # (n_members, 384)
                centroid     = cluster_vecs.mean(axis=0)
                centroid    /= (np.linalg.norm(centroid) + 1e-9)

                # Density: mean L2 distance from members to centroid (lower = tighter)
                distances = np.linalg.norm(cluster_vecs - centroid, axis=1)
                density   = float(distances.mean())

                # Representative jobs: 5 closest to centroid in 384-dim space
                closest      = np.argsort(distances)[:5]
                rep_job_ids  = [job_ids[idxs[r]] for r in closest]

                # Top skills by frequency across all cluster members
                top_skills = [
                    skill for skill, _ in collections.Counter(
                        s for idx in idxs for s in skills_list[idx]
                    ).most_common(10)
                ]

                # c-TF-IDF keywords for this cluster
                keywords = ctfidf_by_cluster.get(ci, [])

                # Label: embed keywords → pick keyword closest to cluster centroid
                label, summary = await self._label_from_ctfidf(
                    keywords,
                    centroid,
                    [titles[idx] for idx in idxs[:30]],
                )

                role_cluster = RoleCluster(
                    id                     = str(uuid.uuid4()),
                    run_id                 = run_id,
                    cluster_index          = ci,
                    label                  = label,
                    summary                = summary,
                    centroid               = centroid.tolist(),
                    top_skills             = top_skills,
                    ctfidf_keywords        = keywords,
                    representative_job_ids = rep_job_ids,
                    job_count              = len(idxs),
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

                logger.info(
                    "Cluster %d → label=%r | jobs=%d | long_tail=%s | density=%.4f",
                    ci, label, len(idxs), len(idxs) < _LONG_TAIL_THRESHOLD, density,
                )

            await session.commit()

        logger.info(
            "Done — run_id=%s | %d archetypes | %d unassigned",
            run_id, n_clusters, n_unassigned,
        )
        return run_id

    # ── Archetype labeling ─────────────────────────────────────────────────────

    async def _label_from_ctfidf(
        self,
        keywords: list[str],
        centroid: np.ndarray,
        sample_titles: list[str],
    ) -> tuple[str, str]:
        """
        Choose the best archetype label from c-TF-IDF keyword candidates.

        Steps:
          1. Embed each c-TF-IDF keyword with the same model used for jobs.
          2. Score each keyword embedding against the cluster centroid (dot product
             of unit vectors = cosine similarity).
          3. The keyword with the highest cosine similarity wins — it is both
             semantically central to the cluster AND distinctive vs. other clusters
             (guaranteed by c-TF-IDF).
          4. Summary = top 8 keywords joined for display and debugging.

        Falls back to "other" when no keywords are available (empty cluster text).
        """
        if not keywords:
            return "other", ""

        loop = asyncio.get_event_loop()
        keyword_vecs = await loop.run_in_executor(
            None,
            lambda kw=keywords: self.model.encode(kw, normalize_embeddings=True),
        )

        scores  = keyword_vecs @ centroid           # cosine similarity to centroid
        label   = keywords[int(np.argmax(scores))]
        summary = ", ".join(keywords[:8])
        return label, summary


# ── CLI entry point ────────────────────────────────────────────────────────────
# python -m core.clustering.hdbscan_engine

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    asyncio.run(HDBSCANClusteringEngine().run())
