# database/models/clustering.py

from datetime import datetime, timezone
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, DateTime, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pgvector.sqlalchemy import Vector
from database.models.base import Base
from database.models.enums import FitCategory


if TYPE_CHECKING:
    from database.models.jobs import JobClusterMembership
    from database.models.rankings import Ranking


class ClusteringRun(Base):
    __tablename__ = "clustering_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    model: Mapped[str] = mapped_column(String, nullable=False)
    k: Mapped[int] = mapped_column(Integer, nullable=False)
    job_count: Mapped[int] = mapped_column(Integer, nullable=False)
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    notes: Mapped[Optional[str]] = mapped_column(String)

    clusters: Mapped[List["RoleCluster"]] = relationship(
        "RoleCluster", back_populates="run", cascade="all, delete-orphan"
    )


class RoleCluster(Base):
    __tablename__ = "role_clusters"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(String, ForeignKey("clustering_runs.id"), nullable=False)
    cluster_index: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str] = mapped_column(String, nullable=False)
    centroid: Mapped[Vector] = mapped_column(Vector(384), nullable=False)
    top_skills: Mapped[Optional[List[str]]] = mapped_column(JSON, default=[])
    job_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    run: Mapped["ClusteringRun"] = relationship(
        "ClusteringRun", back_populates="clusters"
    )
    memberships: Mapped[List["JobClusterMembership"]] = relationship(
        "JobClusterMembership", back_populates="cluster", cascade="all, delete-orphan"
    )

    # Association in ORM (no explicit table here; JobClusterMembership is separate)