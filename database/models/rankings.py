# database/models/rankings.py

from datetime import datetime
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import Float, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.models.base import Base
from database.models.enums import FitCategory


if TYPE_CHECKING:
    from database.models.user_resumes import UserResume
    from database.models.clustering import RoleCluster, ClusteringRun


class Ranking(Base):
    __tablename__ = "rankings"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    resume_id: Mapped[str] = mapped_column(String, nullable=False)
    cluster_id: Mapped[str] = mapped_column(String, nullable=False)
    run_id: Mapped[str] = mapped_column(String, nullable=False)

    cosine_similarity: Mapped[float] = mapped_column(Float, nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)

    fit_category: Mapped[FitCategory] = mapped_column(SqlEnum(FitCategory), nullable=False)
    skill_gaps: Mapped[Optional[List[str]]] = mapped_column(JSON, default=[])
    skill_matches: Mapped[Optional[List[str]]] = mapped_column(JSON, default=[])
    reasoning: Mapped[Optional[str]] = mapped_column(String)

    ranked_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    resume: Mapped["UserResume"] = relationship("UserResume")
    cluster: Mapped["RoleCluster"] = relationship("RoleCluster")
    run: Mapped["ClusteringRun"] = relationship("ClusteringRun")