# database/models/clustering.py

from datetime import datetime, timezone
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import ARRAY, Boolean, Float, ForeignKey, Integer, DateTime, JSON, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pgvector.sqlalchemy import Vector
from database.models.base import Base


if TYPE_CHECKING:
    from database.models.jobs import JobClusterMembership


class ClusteringRun(Base):
    __tablename__ = "clustering_runs"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    model: Mapped[str] = mapped_column(String, nullable=False)
    algorithm: Mapped[str] = mapped_column(String, nullable=False, default="hdbscan")
    k: Mapped[int] = mapped_column(Integer, nullable=False)
    job_count: Mapped[int] = mapped_column(Integer, nullable=False)
    unassigned_count: Mapped[Optional[int]] = mapped_column(Integer)
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    notes: Mapped[Optional[str]] = mapped_column(String)

    clusters: Mapped[List["RoleCluster"]] = relationship(
        "RoleCluster", back_populates="run", cascade="all, delete-orphan"
    )


class RoleCluster(Base):
    __tablename__ = "role_clusters"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    run_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("clustering_runs.id"), nullable=False)
    cluster_index: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str] = mapped_column(String, nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(String)
    centroid: Mapped[Vector] = mapped_column(Vector(384), nullable=False)
    top_skills: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String), default=list)
    ctfidf_keywords: Mapped[Optional[List[str]]] = mapped_column(JSON, default=list)
    representative_job_ids: Mapped[Optional[List[str]]] = mapped_column(JSON, default=list)
    job_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    density: Mapped[Optional[float]] = mapped_column(Float)
    is_long_tail: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    run: Mapped["ClusteringRun"] = relationship(
        "ClusteringRun", back_populates="clusters"
    )
    memberships: Mapped[List["JobClusterMembership"]] = relationship(
        "JobClusterMembership", back_populates="cluster", cascade="all, delete-orphan"
    )
