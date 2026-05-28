# database/models/role_archetypes.py

from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy import ARRAY, DateTime, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from pgvector.sqlalchemy import Vector
from database.models.base import Base


class RoleArchetype(Base):
    __tablename__ = "role_archetypes"

    id:               Mapped[str]                = mapped_column(Uuid(as_uuid=False), primary_key=True)
    title:            Mapped[str]                = mapped_column(String, nullable=False, unique=True)
    category:         Mapped[str]                = mapped_column(String, nullable=False)
    canonical_skills: Mapped[List[str]]          = mapped_column(ARRAY(String), nullable=False, default=list)
    # centroid is NULL until bootstrapper runs for this archetype
    centroid:         Mapped[Optional[object]]   = mapped_column(Vector(384))
    # how many corpus jobs contributed to the centroid (0 = title-embedded fallback)
    job_count:        Mapped[int]                = mapped_column(Integer, nullable=False, default=0)
    built_at:         Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at:       Mapped[datetime]           = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
