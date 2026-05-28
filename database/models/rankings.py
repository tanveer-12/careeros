# database/models/rankings.py

from datetime import datetime, timezone
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import ForeignKey, Float, DateTime, Integer, String, Enum as SqlEnum, Uuid
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.models.base import Base
from database.models.enums import FitCategory


if TYPE_CHECKING:
    from database.models.user_resumes import UserResume
    from database.models.role_archetypes import RoleArchetype


class Ranking(Base):
    __tablename__ = "rankings"

    id:           Mapped[str]   = mapped_column(Uuid(as_uuid=False), primary_key=True)
    resume_id:    Mapped[str]   = mapped_column(Uuid(as_uuid=False), ForeignKey("user_resumes.id"), nullable=False)
    archetype_id: Mapped[str]   = mapped_column(Uuid(as_uuid=False), ForeignKey("role_archetypes.id"), nullable=False)

    cosine_similarity: Mapped[float]          = mapped_column(Float, nullable=False)
    rank:              Mapped[int]            = mapped_column(Integer, nullable=False)
    fit_category:      Mapped[FitCategory]    = mapped_column(SqlEnum(FitCategory, name="fit_category", create_type=False), nullable=False)
    skill_gaps:        Mapped[Optional[List[str]]] = mapped_column(ARRAY(String), default=[])
    skill_matches:     Mapped[Optional[List[str]]] = mapped_column(ARRAY(String), default=[])
    reasoning:         Mapped[Optional[str]]  = mapped_column(String)

    ranked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    resume:    Mapped["UserResume"]    = relationship("UserResume")
    archetype: Mapped["RoleArchetype"] = relationship("RoleArchetype")
