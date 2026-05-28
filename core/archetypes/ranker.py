"""
core/archetypes/ranker.py

Persists ArchetypeMatch results from matcher.py into the rankings table.
Replaces previous rankings for the resume on each call (upsert-by-delete).
"""

import logging
import uuid

from sqlalchemy import delete

from database.models.enums import FitCategory
from database.models.rankings import Ranking
from database.session import async_session

from core.archetypes.matcher import ArchetypeMatch

logger = logging.getLogger("lumia.archetypes.ranker")


def _fit_category(similarity: float) -> FitCategory:
    if similarity >= 0.75:
        return FitCategory.strong
    if similarity >= 0.50:
        return FitCategory.adjacent
    return FitCategory.weak


async def save_rankings(resume_id: str, matches: list[ArchetypeMatch]) -> None:
    """Replace all rankings for resume_id with the provided matches."""
    async with async_session() as session:
        await session.execute(delete(Ranking).where(Ranking.resume_id == resume_id))
        for rank, match in enumerate(matches, start=1):
            session.add(Ranking(
                id=str(uuid.uuid4()),
                resume_id=resume_id,
                archetype_id=match.archetype_id,
                cosine_similarity=match.similarity,
                rank=rank,
                fit_category=_fit_category(match.similarity),
                skill_gaps=match.skill_gaps,
                skill_matches=match.skill_matches,
            ))
        await session.commit()

    logger.info("Saved %d rankings for resume %s", len(matches), resume_id)
