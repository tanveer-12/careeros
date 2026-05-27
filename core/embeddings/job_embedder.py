"""
core/embeddings/job_embedder.py
Generates and stores vector embeddings for all normalized jobs that don't have one yet.
Uses sentence-transformers — runs 100% locally, no API key needed.
Model: "BAAI/bge-small-en"
  - 384 dimensions
  - Downloads once (~130 MB) on first run, then cached on disk forever
  - Fast: ~4000 sentences/sec on CPU

Run directly:  python -m core.embeddings.job_embedder
"""
import asyncio
import logging
import re
import uuid
from datetime import datetime, timezone

from sentence_transformers import SentenceTransformer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import settings
from database.models import Job, JobEmbedding
from database.session import async_session
from core.embeddings import MODEL_NAME, EMBEDDING_DIMENSIONS, MAX_CHARS, TEXT_VERSION

logger = logging.getLogger("lumia.embeddings.job_embedder")

BATCH_SIZE = 128


# ── Text assembly ─────────────────────────────────────────────────────────────

def _build_embedding_text(job: Job) -> str:
    """
    Build the canonical embedding text for a job.

    Priority order (highest signal first — never truncated):
      1. title + company + location
      2. seniority + domain  (taxonomy anchors)
      3. skills (comma-separated)
      4. description[:600]  (truncated first when space is tight)

    Consistent format across every job keeps cosine similarity scores comparable.
    """
    title     = (job.title     or "").strip()
    company   = (job.company   or "").strip()
    location  = (job.location  or "").strip()
    seniority = (job.seniority or "").strip()
    domain    = (job.domain    or "").strip()
    skills    = ", ".join(job.skills_final or job.skills or [])

    # Strip any residual HTML tags the normalizer may have missed, collapse whitespace
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


def _build_title_only_text(job: Job) -> str:
    """Compact title-only variant for ablation testing."""
    parts = [job.title or "", job.seniority or "", job.domain or "", job.company or ""]
    return " ".join(p.strip() for p in parts if p.strip())[:MAX_CHARS]


def _build_description_only_text(job: Job) -> str:
    """HTML-stripped description only, for description-only experiments."""
    raw = job.description or ""
    cleaned = re.sub(r"<[^>]+>", " ", raw)
    return re.sub(r"\s+", " ", cleaned).strip()[:MAX_CHARS]


# ── Embedder ──────────────────────────────────────────────────────────────────

class JobEmbedder:
    """
    Fetches unembedded jobs, encodes them in batches with a local
    SentenceTransformer model, and writes vectors to job_embeddings.

    Usage:
        embedder = JobEmbedder()
        await embedder.embed_jobs()
    """

    def __init__(self) -> None:
        logger.info("Loading local embedding model: %s", MODEL_NAME)
        self.model_name = MODEL_NAME
        self.model      = SentenceTransformer(MODEL_NAME)
        logger.info("Model ready — %d dimensions", EMBEDDING_DIMENSIONS)

    # ── Step 1: fetch jobs that still need embeddings ──────────────────────────

    async def _fetch_unembedded_jobs(self, session: AsyncSession) -> list[Job]:
        """Return jobs without an embedding row for the current model + text version."""
        stmt = (
            select(Job)
            .where(
                ~Job.id.in_(
                    select(JobEmbedding.job_id).where(
                        JobEmbedding.model              == self.model_name,
                        JobEmbedding.input_text_version == TEXT_VERSION,
                    )
                )
            )
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    # ── Step 2: encode a batch with the local model ────────────────────────────

    def _encode_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Synchronous CPU encoding via SentenceTransformer.
        normalize_embeddings=True → unit vectors → dot product == cosine similarity.
        Called via run_in_executor so the async event loop stays free during encode.
        """
        vectors = self.model.encode(
            texts,
            batch_size=64,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return [vec.tolist() for vec in vectors]

    # ── Step 3: persist vectors ────────────────────────────────────────────────

    async def _store_embeddings(
        self,
        session: AsyncSession,
        jobs: list[Job],
        vectors: list[list[float]],
        texts: list[str],
    ) -> int:
        """Insert one JobEmbedding row per job. Returns count of newly inserted rows."""
        inserted = 0
        now = datetime.now(timezone.utc)

        for job, vector, text in zip(jobs, vectors, texts):
            exists = await session.execute(
                select(JobEmbedding).where(
                    JobEmbedding.job_id             == job.id,
                    JobEmbedding.model              == self.model_name,
                    JobEmbedding.input_text_version == TEXT_VERSION,
                )
            )
            if exists.scalar_one_or_none():
                continue

            session.add(JobEmbedding(
                id                 = str(uuid.uuid4()),
                job_id             = job.id,
                embedding          = vector,
                model              = self.model_name,
                input_text         = text,
                input_text_version = TEXT_VERSION,
                token_count        = len(text.split()),
                created_at         = now,
            ))
            inserted += 1

        await session.commit()
        return inserted

    # ── Single-job embed (synchronous) ─────────────────────────────────────────

    def embed_job(self, job: Job) -> JobEmbedding:
        """
        Embed a single job and return an unsaved JobEmbedding row.
        Caller is responsible for adding the row to a session and committing.
        """
        text   = _build_embedding_text(job)
        vector = self.model.encode(text, normalize_embeddings=True).tolist()
        return JobEmbedding(
            id                 = str(uuid.uuid4()),
            job_id             = job.id,
            embedding          = vector,
            model              = self.model_name,
            input_text         = text,
            input_text_version = TEXT_VERSION,
            token_count        = len(text.split()),
        )

    # ── Public entry point ─────────────────────────────────────────────────────

    async def embed_jobs(self) -> None:
        """
        Full pipeline:
          1. Fetch all unembedded jobs (filtered by model + TEXT_VERSION)
          2. Build canonical text for each job
          3. Encode in batches (local CPU — no network calls)
          4. Write vectors to DB

        One failed batch is logged and skipped; committed batches are preserved.
        """
        async with async_session() as session:
            jobs = await self._fetch_unembedded_jobs(session)

        total   = len(jobs)
        created = 0
        failed  = 0

        logger.info("Found %d jobs to embed (model=%s, text_version=%s)", total, self.model_name, TEXT_VERSION)
        if total == 0:
            logger.info("All jobs are already embedded — nothing to do.")
            return

        batches = [jobs[i : i + BATCH_SIZE] for i in range(0, total, BATCH_SIZE)]
        logger.info("%d batch(es) of up to %d", len(batches), BATCH_SIZE)

        loop = asyncio.get_event_loop()

        for batch_num, batch in enumerate(batches, start=1):
            try:
                texts   = [_build_embedding_text(j) for j in batch]
                vectors = await loop.run_in_executor(None, self._encode_batch, texts)
            except Exception as exc:
                logger.error("Batch %d/%d encode failed: %s", batch_num, len(batches), exc)
                failed += len(batch)
                continue

            try:
                async with async_session() as session:
                    n = await self._store_embeddings(session, batch, vectors, texts)
                created += n
                logger.info("Batch %d/%d → %d stored", batch_num, len(batches), n)
            except Exception as exc:
                logger.error("Batch %d/%d DB write failed: %s", batch_num, len(batches), exc)
                failed += len(batch)

        logger.info("Done — %d created, %d failed, %d total", created, failed, total)


# ── CLI entry point ────────────────────────────────────────────────────────────
# python -m core.embeddings.job_embedder

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    asyncio.run(JobEmbedder().embed_jobs())
