"""
core/archetypes/matcher.py

Resume-to-archetype matching using pgvector cosine similarity.

Given a resume_id, fetches the stored resume embedding and returns the top-N
closest RoleArchetypes, with skill gaps and matches computed per archetype.

Usage:
    from core.archetypes.matcher import match_resume
    matches = await match_resume(resume_id="...", top_n=5)
    for m in matches:
        print(m.title, m.similarity, m.skill_gaps)
"""
import logging
from dataclasses import dataclass, field

from sqlalchemy import select, text

from core.embeddings import MODEL_NAME
from database.models.role_archetypes import RoleArchetype
from database.models.user_resumes import UserResume, ResumeEmbedding
from database.session import async_session

logger = logging.getLogger("lumia.archetypes.matcher")


@dataclass
class ArchetypeMatch:
    archetype_id:  str
    title:         str
    category:      str
    similarity:    float           # cosine similarity, 0.0–1.0
    skill_gaps:    list[str] = field(default_factory=list)   # in archetype, not in resume
    skill_matches: list[str] = field(default_factory=list)   # in both


async def match_resume(
    resume_id: str,
    top_n:     int = 5,
) -> list[ArchetypeMatch]:
    """
    Return top_n archetype matches for the given resume, ranked by cosine similarity.

    Raises ValueError if the resume has no embedding yet (run embed_resume first).
    """
    async with async_session() as session:
        # ── Fetch resume embedding + parsed skills ────────────────────────────
        row = (await session.execute(
            select(ResumeEmbedding.embedding, UserResume.parsed_skills)
            .join(UserResume, UserResume.id == ResumeEmbedding.resume_id)
            .where(ResumeEmbedding.resume_id == resume_id)
            .where(ResumeEmbedding.model == MODEL_NAME)
        )).one_or_none()

        if row is None:
            raise ValueError(
                f"No embedding found for resume {resume_id!r}. "
                "Run 'lumia ingest-resume' first."
            )

        resume_embedding = row.embedding
        resume_skills    = set(row.parsed_skills or [])

        # Build vector literal inline — safe because values come from our own model output
        vec_literal = "[" + ",".join(str(float(x)) for x in resume_embedding) + "]"

        # ── pgvector cosine similarity search ─────────────────────────────────
        # <=> returns cosine distance; ORDER BY ASC = most similar first.
        # The ::vector cast is inlined (not a bind param) to avoid asyncpg
        # misinterpreting the colon in "::vector" as a named-parameter prefix.
        result = await session.execute(
            text(f"""
                SELECT id,
                       title,
                       category,
                       canonical_skills,
                       1 - (centroid <=> '{vec_literal}'::vector) AS similarity
                FROM   role_archetypes
                WHERE  centroid IS NOT NULL
                ORDER  BY centroid <=> '{vec_literal}'::vector
                LIMIT  :top_n
            """),
            {"top_n": top_n},
        )
        rows = result.all()

    matches: list[ArchetypeMatch] = []
    for r in rows:
        archetype_skills = set(r.canonical_skills or [])
        matches.append(ArchetypeMatch(
            archetype_id  = r.id,
            title         = r.title,
            category      = r.category,
            similarity    = round(float(r.similarity), 4),
            skill_gaps    = sorted(archetype_skills - resume_skills),
            skill_matches = sorted(archetype_skills & resume_skills),
        ))

    logger.info(
        "Matched resume %s → top %d archetypes: %s",
        resume_id,
        len(matches),
        [m.title for m in matches],
    )
    return matches
