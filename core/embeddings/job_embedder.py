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
import uuid
from datetime import datetime, timezone
from sentence_transformers import SentenceTransformer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import settings
from database.models import Job, JobEmbedding
from database.session import async_session
from core.embeddings import MODEL_NAME, EMBEDDING_DIMENSIONS, MAX_CHARS

logger = logging.getLogger("careeros.embeddings.job_embedder")

# how many jobs to send in one batch
BATCH_SIZE = 128

def _build_embedding_text(job: Job) -> str:
    """
    combine the most signal-rich job fields into a single string.
    Priority order (highest signal first):
      1. title + company + location  → always preserved, never truncated
      2. description[:500]           → truncated first when space is tight
      3. skills (comma-separated)    → dropped last if still over budget
 
    We keep the format consistent across every job so that
    cosine similarity scores are comparable across the whole corpus.
    """
    title = (job.title or "").strip()
    company = (job.company or "").strip()
    location = (job.location or "").strip()

    # Truncate description early — it's the longest field
    description = (job.description or "")[:400].strip()
    skills_str  = ", ".join(job.skills or [])

    parts = [f"{title} at {company} in {location}"]
    if description:
        parts.append(description)
    if skills_str:
        parts.append(f"Skills: {skills_str}")

    # Hard cap to stay within the model's token window
    return " | ".join(parts)[:MAX_CHARS]



class JobEmbedder:
    """
    Fetches unembedded jobs, encodes them in batches with a local
    SentenceTransformer model, and writes vectors to job_embeddings.
 
    The model is loaded once in __init__ and reused for all batches.
 
    Usage:
        embedder = JobEmbedder()
        await embedder.embed_jobs()
    """
 
    def __init__(self) -> None:
        # Load model from local HuggingFace cache (downloads on first run)
        logger.info("Loading local embedding model: %s", MODEL_NAME)
        self.model_name = MODEL_NAME
        self.model      = SentenceTransformer(MODEL_NAME)
        logger.info("Model ready — %d dimensions", EMBEDDING_DIMENSIONS)

    # ── Step 1: fetch jobs that still need embeddings ──────────────
 
    async def _fetch_unembedded_jobs(self, session: AsyncSession) -> list[Job]:
        """
        Return all jobs that don't yet have a row in job_embeddings for the
        current model. The NOT IN subquery makes repeated runs idempotent.
        """
        stmt = (
            select(Job)
            .where(
                ~Job.id.in_(
                    select(JobEmbedding.job_id).where(
                        JobEmbedding.model == self.model_name
                    )
                )
            )
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())
    
    # ── Step 2: encode a batch with the local model ─────────────────
 
    def _encode_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Synchronous CPU encoding via SentenceTransformer.
 
        normalize_embeddings=True gives unit-length vectors so that
        dot product == cosine similarity. This simplifies all the
        ranking math in Phase 6 (no need to divide by norms).
 
        Called via run_in_executor so the async event loop stays free
        during the CPU-heavy encode step.
        """
        vectors = self.model.encode(
            texts,
            batch_size=64,             # internal mini-batch for the model
            normalize_embeddings=True, # L2-normalize → dot = cosine
            show_progress_bar=False,
        )
        # encode() returns a numpy ndarray; pgvector needs plain Python lists
        return [vec.tolist() for vec in vectors]
    
    # ── Step 3: persist vectors + update job status ─────────────────
 
    async def _store_embeddings(
        self,
        session: AsyncSession,
        jobs: list[Job],
        vectors: list[list[float]],
        texts: list[str],
    ) -> int:
        """
        Insert one JobEmbedding row per job and set job.status='embedded'.
        Returns the count of newly inserted rows.
        """
        inserted = 0
        now = datetime.now(timezone.utc)
 
        for job, (vector, text) in zip(jobs, zip(vectors,texts)):
            # Row-level idempotency check (belt-and-suspenders)
            exists = await session.execute(
                select(JobEmbedding).where(
                    JobEmbedding.job_id     == job.id,
                    JobEmbedding.model == self.model_name,
                )
            )
            if exists.scalar_one_or_none():
                continue  # already stored — skip without error
 
            session.add(JobEmbedding(
                id         = str(uuid.uuid4()),
                job_id     = job.id,
                embedding  = vector,
                model      = self.model_name,
                input_text = text,
                created_at = now,
            ))
            inserted += 1
 
        await session.commit()
        return inserted
    
    # ── Single-job embed (synchronous) ─────────────────────────────

    def embed_job(self, job: Job) -> JobEmbedding:
        """
        Embed a single job and return an unsaved JobEmbedding row.
        Text: title + description + skills (space-joined).
        Caller is responsible for adding the row to a session and committing.
        """
        title = (job.title or "").strip()
        description = (job.description or "").strip()
        skills_str = " ".join(job.skills or [])
        text = f"{title} {description} {skills_str}".strip()

        vector = self.model.encode(text, normalize_embeddings=True).tolist()

        return JobEmbedding(
            id=str(uuid.uuid4()),
            job_id=job.id,
            embedding=vector,
            model="bge-small-en",
            input_text=text,
        )

    # ── Public entry point ──────────────────────────────────────────

    async def embed_jobs(self) -> None:
        """
        Full pipeline:
          1. Fetch all unembedded jobs from DB
          2. Build text for each job
          3. Encode in batches (local CPU — no network calls)
          4. Write vectors to DB
 
        One failed batch is logged and skipped; the rest continue.
        All committed batches are preserved even if the run crashes.
        """
        async with async_session() as session:
            jobs = await self._fetch_unembedded_jobs(session)
 
        total   = len(jobs)
        created = 0
        failed  = 0
 
        logger.info("Found %d jobs to embed (model=%s)", total, self.model_name)
        if total == 0:
            logger.info("All jobs are already embedded — nothing to do.")
            return
 
        batches = [jobs[i : i + BATCH_SIZE] for i in range(0, total, BATCH_SIZE)]
        logger.info("%d batch(es) of up to %d", len(batches), BATCH_SIZE)
 
        loop = asyncio.get_event_loop()
 
        for batch_num, batch in enumerate(batches, start=1):
            try:
                texts   = [_build_embedding_text(j) for j in batch]
                # Run CPU-bound encode in a thread so we don't block the loop
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
 
        logger.info(
            "Done — %d created, %d failed, %d total",
            created, failed, total,
        )

# ─────────────────────────────────────────────
# CLI entry point
# python -m core.embeddings.job_embedder
# ─────────────────────────────────────────────
 
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    asyncio.run(JobEmbedder().embed_jobs())