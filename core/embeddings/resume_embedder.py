"""
core/embeddings/resume_embedder.py

Embeds a single resume into the SAME vector space as jobs so that
cosine similarity scores between a resume and job clusters are meaningful.

CRITICAL RULE: This file must use the exact same model as job_embedder.py.
If you change the model in one file, change it in both — and re-embed
everything from scratch, because different models produce incompatible spaces.
"""

import asyncio
import logging
from datetime import datetime, timezone

from sentence_transformers import SentenceTransformer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import settings
from database.models import Resume, ResumeEmbedding  # adjust to your actual model paths
from database.session import async_session              # adjust to your actual session helper
from core.embeddings import MODEL_NAME, EMBEDDING_DIMENSIONS, MAX_CHARS

logger = logging.getLogger("careeros.embeddings.resume_embedder")



# ─────────────────────────────────────────────
# Helper — build the text that gets embedded
# ─────────────────────────────────────────────

def _build_embedding_text(resume: Resume) -> str:
    """
    Construct the string that becomes the resume's vector.

    Priority order (mirrors job_embedder's philosophy):
      1. current/last role  — highest signal, always preserved
      2. skills (joined)    — strong signal, preserved unless extreme overflow
      3. raw_text[:600]     — background context, first to be trimmed

    Placing the highest-signal content at the front means the model's
    attention window captures it even if the text overflows the limit.
    """
    role       = (resume.parsed_titles[0] if resume.parsed_titles else "").strip()
    skills_str = ", ".join(resume.parsed_skills or [])

    # Cap raw_text here before joining — it can be very long
    raw_snippet = (resume.raw_text or "")[:600].strip()

    parts = []
    if role:
        parts.append(f"Role: {role}")
    if skills_str:
        parts.append(f"Skills: {skills_str}")
    if raw_snippet:
        parts.append(f"Background: {raw_snippet}")

    return " | ".join(parts)[:MAX_CHARS]


# ─────────────────────────────────────────────
# Main class
# ─────────────────────────────────────────────

class ResumeEmbedder:
    """
    Generates a vector embedding for a single resume and stores it
    in resume_embeddings. Uses the same local model as JobEmbedder
    so resume vectors and job vectors are directly comparable.

    Usage:
        embedder = ResumeEmbedder()
        success = await embedder.embed_resume("your-resume-id")
    """

    def __init__(self) -> None:
        # Reuse the cached model — no re-download if JobEmbedder already ran
        logger.info("Loading local embedding model: %s", MODEL_NAME)
        self.model      = SentenceTransformer(MODEL_NAME)
        self.model_name = MODEL_NAME
        logger.info("Model ready — %d dimensions", EMBEDDING_DIMENSIONS)

    # ── Fetch ───────────────────────────────────────────────────────

    async def _fetch_resume(self, session: AsyncSession, resume_id: str) -> Resume | None:
        """Load the resume row from DB. Returns None if not found."""
        result = await session.execute(
            select(Resume).where(Resume.id == resume_id)
        )
        return result.scalar_one_or_none()

    # ── Idempotency check ───────────────────────────────────────────

    async def _already_embedded(self, session: AsyncSession, resume_id: str) -> bool:
        """
        Return True if a resume_embeddings row already exists for this
        resume + model pair. Makes embed_resume() safe to call multiple times.
        """
        result = await session.execute(
            select(ResumeEmbedding).where(
                ResumeEmbedding.resume_id   == resume_id,
                ResumeEmbedding.model  == self.model_name,
            )
        )
        return result.scalar_one_or_none() is not None

    # ── Encode (synchronous, runs in thread) ────────────────────────

    def _encode(self, text: str) -> list[float]:
        """
        Encode a single text to a unit-length vector.

        normalize_embeddings=True is critical — it ensures dot product
        between any two vectors equals their cosine similarity,
        which is what Phase 6's ranking math relies on.
        """
        vector = self.model.encode(
            text,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return vector.tolist()  # convert numpy → plain Python list for pgvector

    # ── Store ───────────────────────────────────────────────────────

    async def _store_embedding(
        self,
        session: AsyncSession,
        resume: Resume,
        vector: list[float],
        text: str,    
    ) -> None:
        """
        Insert the ResumeEmbedding row and mark resume.is_embedded=True.
        Both changes are committed in one transaction.
        """
        session.add(ResumeEmbedding(
            resume_id  = resume.id,
            embedding  = vector,        # pgvector column
            model      = self.model_name,   # 'model' not 'model_name'
            input_text = text,              # required field
            created_at = datetime.now(timezone.utc),
        ))
        resume.is_embedded = True
        await session.commit()

    # ── Public entry point ──────────────────────────────────────────

    async def embed_resume(self, resume_id: str) -> bool:
        """
        Full pipeline for one resume:
          1. Load from DB
          2. Skip if already embedded (idempotent)
          3. Build text (role → skills → raw_text)
          4. Encode locally (no network call)
          5. Store vector + update status

        Returns True on success, False if the resume wasn't found or
        encoding failed. Logs details either way.
        """
        async with async_session() as session:
            resume = await self._fetch_resume(session, resume_id)

            if resume is None:
                logger.error("Resume not found: id=%s", resume_id)
                return False

            if await self._already_embedded(session, resume_id):
                logger.info("Resume %s already embedded — skipping.", resume_id)
                return True

            # Build the text that will become the vector
            text = _build_embedding_text(resume)

            # Log which skills are being encoded (useful for debugging fit scores)
            logger.debug("Resume %s | skills in embedding: %s", resume_id, resume.parsed_skills or [])
            logger.debug("Resume %s | embedding text (%d chars): %s", resume_id, len(text), text[:120])

            # Encode in a thread so the event loop stays free
            loop   = asyncio.get_event_loop()
            try:
                vector = await loop.run_in_executor(None, self._encode, text)
            except Exception as exc:
                logger.error("Encoding failed for resume %s: %s", resume_id, exc)
                return False

            await self._store_embedding(session, resume, vector,text)

        logger.info(
            "Resume %s embedded successfully (model=%s, dims=%d)",
            resume_id, self.model_name, EMBEDDING_DIMENSIONS,
        )
        return True


# ─────────────────────────────────────────────
# CLI entry point
# python -m core.embeddings.resume_embedder <resume_id>
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    if len(sys.argv) < 2:
        print("Usage: python -m core.embeddings.resume_embedder <resume_id>")
        sys.exit(1)

    success = asyncio.run(ResumeEmbedder().embed_resume(sys.argv[1]))
    sys.exit(0 if success else 1)
