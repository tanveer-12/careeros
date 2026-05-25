# database/models/rankings.py

from datetime import datetime, timezone
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import ForeignKey, JSON, Float, DateTime, Integer, String, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.models.base import Base
from database.models.enums import FitCategory


if TYPE_CHECKING:
    from database.models.user_resumes import UserResume
    from database.models.clustering import RoleCluster, ClusteringRun


class Ranking(Base):
    __tablename__ = "rankings"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    resume_id: Mapped[str] = mapped_column(String, ForeignKey("user_resumes.id"), nullable=False)
    cluster_id: Mapped[str] = mapped_column(String, ForeignKey("role_clusters.id"), nullable=False)
    run_id: Mapped[str] = mapped_column(String, ForeignKey("clustering_runs.id"), nullable=False)

    cosine_similarity: Mapped[float] = mapped_column(Float, nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)

    fit_category: Mapped[FitCategory] = mapped_column(Enum(FitCategory), nullable=False)
    skill_gaps: Mapped[Optional[List[str]]] = mapped_column(JSON, default=[])
    skill_matches: Mapped[Optional[List[str]]] = mapped_column(JSON, default=[])
    reasoning: Mapped[Optional[str]] = mapped_column(String)

    ranked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    resume: Mapped["UserResume"] = relationship("UserResume")
    cluster: Mapped["RoleCluster"] = relationship("RoleCluster")
    run: Mapped["ClusteringRun"] = relationship("ClusteringRun")