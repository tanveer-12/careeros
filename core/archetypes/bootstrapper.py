"""
core/archetypes/bootstrapper.py

Builds centroid embeddings for every RoleArchetype using corpus-bootstrapped method:

  For each archetype:
    1. Search jobs WHERE title ILIKE '%{core_title}%' and join with job_embeddings.
    2. If ≥ 3 matching jobs found:
         centroid       = L2-normalised mean of their 384-dim embeddings
         canonical_skills = top-10 skills by frequency across matching jobs
         job_count      = number of contributing jobs
    3. If < 3 matching jobs (rare/niche title):
         centroid = embed(archetype title) directly — clean fallback, no noise
         canonical_skills = []
         job_count = 0

Run:  python -m core.archetypes.bootstrapper
      python -m core.archetypes.bootstrapper --force   (rebuild all centroids)
"""
import asyncio
import collections
import logging
import re
import uuid
from datetime import datetime, timezone

import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.preprocessing import normalize
from sqlalchemy import select

from core.archetypes.taxonomy import ARCHETYPES
from core.embeddings import MODEL_NAME
from database.models.job_embeddings import JobEmbedding
from database.models.jobs import Job
from database.models.role_archetypes import RoleArchetype
from database.session import async_session

logger = logging.getLogger("lumia.archetypes.bootstrapper")

# Minimum corpus matches required to trust the averaged centroid over a title embed
_MIN_CORPUS_JOBS = 3

# Leading seniority words to strip when building a fallback search term
_SENIORITY_PREFIXES = (
    "junior ", "senior ", "staff ", "principal ", "lead ", "associate ",
    "founding ", "sr. ", "sr ", "group ", "distinguished ", "chief ",
    "deputy ", "interim ",
)


def _core_title(title: str) -> str:
    """Strip leading seniority token to get the base role name for DB search."""
    t = title.lower().strip()
    for prefix in _SENIORITY_PREFIXES:
        if t.startswith(prefix):
            return t[len(prefix):].strip()
    return t


async def _fetch_matching_embeddings(
    session,
    search_term: str,
) -> list:
    """Return (embedding, job_id, skills_final) rows for jobs matching search_term."""
    stmt = (
        select(
            JobEmbedding.embedding,
            JobEmbedding.job_id,
            Job.skills_final,
        )
        .join(Job, Job.id == JobEmbedding.job_id)
        .where(Job.title.ilike(f"%{search_term}%"))
        .where(JobEmbedding.model == MODEL_NAME)
    )
    result = await session.execute(stmt)
    return result.all()


async def _build_centroid(
    session,
    archetype: RoleArchetype,
    model: SentenceTransformer,
) -> tuple[list[float], list[str], int]:
    """
    Returns (centroid_vector, canonical_skills, contributing_job_count).
    """
    # Stage 1: exact title search
    rows = await _fetch_matching_embeddings(session, archetype.title)

    # Stage 2: seniority-stripped fallback search
    if len(rows) < _MIN_CORPUS_JOBS:
        core = _core_title(archetype.title)
        if core and core != archetype.title.lower():
            rows = await _fetch_matching_embeddings(session, core)

    if len(rows) >= _MIN_CORPUS_JOBS:
        vecs = [np.array(r.embedding, dtype=np.float32) for r in rows]
        matrix = normalize(np.vstack(vecs), norm="l2").astype(np.float32)
        centroid = matrix.mean(axis=0)
        centroid = centroid / (np.linalg.norm(centroid) + 1e-9)

        skill_counts: collections.Counter = collections.Counter(
            s for r in rows for s in (r.skills_final or [])
        )
        canonical_skills = [s for s, _ in skill_counts.most_common(10)]
        return centroid.tolist(), canonical_skills, len(rows)

    # Stage 3: title-embed fallback
    loop = asyncio.get_event_loop()
    vec = await loop.run_in_executor(
        None,
        lambda t=archetype.title: model.encode(t, normalize_embeddings=True),
    )
    logger.debug(
        "Archetype %r: no corpus match (<%d jobs) — using title embedding",
        archetype.title, _MIN_CORPUS_JOBS,
    )
    return vec.tolist(), [], 0


async def build(force: bool = False) -> None:
    """
    Upsert all archetypes from taxonomy into role_archetypes, then build centroids.

    force=True: rebuild centroids even for archetypes that already have one.
    """
    logger.info("Loading embedding model: %s", MODEL_NAME)
    model = SentenceTransformer(MODEL_NAME)

    # ── 1. Upsert taxonomy rows ───────────────────────────────────────────────
    async with async_session() as session:
        existing_titles: set[str] = set(
            (await session.execute(select(RoleArchetype.title))).scalars().all()
        )

        new_count = 0
        for arch in ARCHETYPES:
            if arch["title"] not in existing_titles:
                session.add(RoleArchetype(
                    id       = str(uuid.uuid4()),
                    title    = arch["title"],
                    category = arch["category"],
                ))
                new_count += 1

        await session.commit()
        logger.info("Taxonomy upsert: %d new archetypes inserted", new_count)

    # ── 2. Build centroids ────────────────────────────────────────────────────
    async with async_session() as session:
        stmt = select(RoleArchetype)
        if not force:
            stmt = stmt.where(RoleArchetype.centroid == None)  # noqa: E711
        archetypes = (await session.execute(stmt)).scalars().all()

        logger.info(
            "Building centroids for %d archetypes (force=%s)...", len(archetypes), force
        )

        corpus_count  = 0
        fallback_count = 0

        for archetype in archetypes:
            centroid, skills, job_count = await _build_centroid(session, archetype, model)
            archetype.centroid         = centroid
            archetype.canonical_skills = skills
            archetype.job_count        = job_count
            archetype.built_at         = datetime.now(timezone.utc)

            if job_count >= _MIN_CORPUS_JOBS:
                corpus_count += 1
                logger.debug(
                    "  %-50s  corpus  jobs=%d  skills=%d",
                    archetype.title, job_count, len(skills),
                )
            else:
                fallback_count += 1
                logger.debug("  %-50s  fallback (title embed)", archetype.title)

        await session.commit()

    logger.info(
        "Done — corpus: %d  title-fallback: %d  total: %d",
        corpus_count, fallback_count, corpus_count + fallback_count,
    )


# ── CLI entry point ────────────────────────────────────────────────────────────
# python -m core.archetypes.bootstrapper
# python -m core.archetypes.bootstrapper --force

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    force_flag = "--force" in sys.argv
    asyncio.run(build(force=force_flag))
