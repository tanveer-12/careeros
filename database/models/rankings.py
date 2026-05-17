"""ORM model for resume-to-cluster rankings."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base

if TYPE_CHECKING:
    from database.models.clusters import ClusteringRun, RoleCluster
    from database.models.resumes import Resume


class FitCategory(enum.Enum):
    strong = "strong"
    adjacent = "adjacent"
    weak = "weak"


class Ranking(Base):
    __tablename__ = "rankings"
    __table_args__ = (UniqueConstraint("resume_id", "cluster_id", "run_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("uuid_generate_v4()"))
    resume_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("resumes.id", ondelete="CASCADE"))
    cluster_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("role_clusters.id", ondelete="CASCADE"))
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clustering_runs.id", ondelete="CASCADE"))

    cosine_similarity: Mapped[float] = mapped_column(Float)
    rank: Mapped[int] = mapped_column(Integer)

    fit_category: Mapped[FitCategory] = mapped_column(Enum(FitCategory, name="fit_category"))
    skill_gaps: Mapped[list[str]] = mapped_column(ARRAY(String), server_default=text("'{}'"))
    skill_matches: Mapped[list[str]] = mapped_column(ARRAY(String), server_default=text("'{}'"))
    reasoning: Mapped[Optional[str]] = mapped_column(Text, default=None)

    ranked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    resume: Mapped["Resume"] = relationship("Resume")
    cluster: Mapped["RoleCluster"] = relationship("RoleCluster")
    run: Mapped["ClusteringRun"] = relationship("ClusteringRun")
