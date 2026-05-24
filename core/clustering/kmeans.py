import asyncio
import collections
import itertools
import logging
from datetime import datetime, timezone
import re
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import normalize
from sentence_transformers import SentenceTransformer
from sqlalchemy import cast, select
from sqlalchemy.types import Date

from core.embeddings import MODEL_NAME
from database.models import ClusteringRun, Job, JobClusterMembership, JobEmbedding, RoleCluster
from database.session import async_session

_STOPWORDS = {
     "at", "in", "the", "and", "of", "for", "with", "a", "an", "to",
    "senior", "junior", "lead", "staff", "principal", "engineer",
    "manager", "director", "associate", "specialist", "ii", "iii", "i",
    "vp", "svp", "evp", "head", "chief", "remote", "hybrid", "onsite",
    "full", "time", "part", "contract", "intern", "internship",
    "its", "new", "grad", "entry", "level", "mid", "experienced",
}


class ClusteringEngine:
    def __init__(self) -> None:
        self.model_name = MODEL_NAME
        self.log = logging.getLogger("careeros.clustering.kmeans")
        self.log.info("Loading local embedding model: %s", MODEL_NAME)
        self.model = SentenceTransformer(MODEL_NAME)

    async def run_clustering(self, k: int = 10, force: bool = False):
        # Step 1 — Idempotency check
        async with async_session() as session:
            today = datetime.now(timezone.utc).date()
            existing = await session.scalar(
                select(ClusteringRun).where(
                    cast(ClusteringRun.run_at, Date) == today
                ).limit(1)
            )
            if existing and not force:
                self.log.info("Clustering run already exists for today (run_id=%s). Pass force=True to re-run.", existing.id)
                return existing.id

        # Step 2 — Fetch all job embeddings
        async with async_session() as session:
            rows = (await session.execute(
                select(JobEmbedding.job_id, JobEmbedding.embedding, Job.skills, Job.title, Job.domain)
                .join(Job, Job.id == JobEmbedding.job_id)
                .where(JobEmbedding.model == self.model_name)
            )).all()

        self.log.info("Fetched %d job embeddings", len(rows))
        if not rows:
            self.log.error("No job embeddings found. Run embed_jobs first.")
            return None

        job_ids   = [r.job_id   for r in rows]
        skills    = [r.skills or [] for r in rows]
        titles    = [r.title or "" for r in rows]
        domains  = [r.domain or "" for r in rows]
        raw_vecs  = [np.array(r.embedding, dtype=np.float32) for r in rows]

        # Step 3 — Build normalised numpy matrix
        matrix = normalize(
            np.vstack(raw_vecs).astype(np.float32), norm="l2"
        )

        # Step 4 — Run KMeans
        self.log.info("Running KMeans(k=%d, random_state=42, n_init=10)...", k)
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        km.fit(matrix)
        self.log.info("KMeans converged in %d iterations", km.n_iter_)

        labels   = km.labels_          # shape (n_jobs,)
        centers  = km.cluster_centers_ # shape (k, 384)

        # Step 5 — Insert ClusteringRun
        async with async_session() as session:
            run = ClusteringRun(
                model=self.model_name,
                k=k,
                job_count=len(rows),
                run_at=datetime.now(timezone.utc),
                notes=f"KMeans k={k} random_state=42 n_init=10",
            )
            session.add(run)
            await session.flush()
            run_id = run.id
            self.log.info("Inserted ClusteringRun: %s", run_id)

            # Step 6 — Group jobs by cluster, then insert RoleCluster + memberships
            jobs_by_cluster: dict[int, list[tuple]] = collections.defaultdict(list)
            for idx, (jid, jskills, jtitle,jdomain, vec) in enumerate(
                zip(job_ids, skills, titles, domains,matrix)
            ):
                jobs_by_cluster[labels[idx]].append((jid, jskills, jtitle, jdomain, vec))

            sample_titles_by_cluster: dict[int, list[str]] = {}
            sample_domains_by_cluster: dict[int, list[str]] = {}

            for ci in range(k):
                cluster_jobs = jobs_by_cluster[ci]

                top_skills = [
                    skill
                    for skill, _ in collections.Counter(
                        s for _, jskills, _, _, _ in cluster_jobs for s in jskills
                    ).most_common(10)
                ]

                sample_titles = [jtitle for _, _, jtitle, _, _ in cluster_jobs[:20]]
                sample_domains = [jdomain for _, _, _, jdomain, _ in cluster_jobs]
                sample_titles_by_cluster[ci] = sample_titles
                sample_domains_by_cluster[ci] = sample_domains

                centroid = centers[ci].tolist()

                role_cluster = RoleCluster(
                    run_id=run_id,
                    cluster_index=ci,
                    label="",
                    centroid=centroid,
                    top_skills=top_skills,
                    job_count=len(cluster_jobs),
                )
                session.add(role_cluster)
                await session.flush()

                centroid_vec = np.array(centroid, dtype=np.float32)
                memberships = [
                    JobClusterMembership(
                        job_id=jid,
                        cluster_id=role_cluster.id,
                        run_id=run_id,
                        distance_to_centroid=float(np.linalg.norm(vec - centroid_vec)),
                    )
                    for jid, _, _, _, vec in cluster_jobs
                ]
                session.add_all(memberships)

            await session.commit()

            # Step 7 — Label clusters
        await self.label_clusters(run_id, sample_titles_by_cluster, sample_domains_by_cluster)

        self.log.info("Done — %d clusters labeled, run_id=%s", k, run_id)
        return run_id

    async def label_clusters(
        self,
        run_id,
        sample_titles_by_cluster: dict[int, list[str]],
        sample_domains_by_cluster: dict[int, list[str]],
    ) -> None:
        async with async_session() as session:
            clusters = (await session.execute(
                select(RoleCluster)
                .where(RoleCluster.run_id == run_id)
                .order_by(RoleCluster.cluster_index)
            )).scalars().all()

            self.log.info("Labeling %d clusters via semantic centroid matching...", len(clusters))

            for cluster in clusters:
                ci = cluster.cluster_index
                centroid_vec = np.array(cluster.centroid, dtype=np.float32)

                # Step 1 — build candidates from domain (primary) + skills + single title words
                # Domain values are clean strings that embed well
                domain_counts = collections.Counter(
                    d for d in sample_domains_by_cluster.get(ci, []) if d and d != "other"
                )
                # top 3 domains by frequency
                top_domains = [d for d, _ in domain_counts.most_common(3)]

                # single meaningful words from titles (no bigrams)
                title_words: list[str] = []
                for title in sample_titles_by_cluster.get(ci, []):
                    cleaned = re.sub(r"[^\w\s]", " ", title.lower())
                    title_words.extend(
                        t for t in cleaned.split()
                        if t not in _STOPWORDS and len(t) > 3
                    )
                top_title_words = [w for w, _ in collections.Counter(title_words).most_common(10)]

                # candidates: domains first (highest signal), then skills, then title words
                candidates = top_domains + list(cluster.top_skills or []) + top_title_words

                # deduplicate preserving order, cap at 40
                seen: set[str] = set()
                deduped: list[str] = []
                for c in candidates:
                    if c not in seen:
                        seen.add(c)
                        deduped.append(c)
                    if len(deduped) == 40:
                        break

                if not deduped:
                    cluster.label = "other"
                    await session.commit()
                    continue

                # Step 2 — embed and pick closest to centroid
                loop = asyncio.get_event_loop()
                candidate_vecs = await loop.run_in_executor(
                    None,
                    lambda cands=deduped: self.model.encode(cands, normalize_embeddings=True),
                )

                scores = candidate_vecs @ centroid_vec
                best_label = deduped[int(np.argmax(scores))]

                cluster.label = best_label
                await session.commit()
                self.log.info("Cluster %d: %s (%d jobs)", ci, best_label, cluster.job_count)