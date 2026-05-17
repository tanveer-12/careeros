"""ORM models for clustering runs, role clusters, and job-cluster memberships."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base


class ClusteringRun(Base):
    __tablename__ = "clustering_runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("uuid_generate_v4()"))
    model: Mapped[str] = mapped_column(Text)
    k: Mapped[int] = mapped_column(Integer)
    job_count: Mapped[int] = mapped_column(Integer)
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    notes: Mapped[Optional[str]] = mapped_column(Text, default=None)

    clusters: Mapped[list["RoleCluster"]] = relationship(
        "RoleCluster", back_populates="run", cascade="all, delete-orphan"
    )


class RoleCluster(Base):
    __tablename__ = "role_clusters"
    __table_args__ = (UniqueConstraint("run_id", "cluster_index"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("uuid_generate_v4()"))
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clustering_runs.id", ondelete="CASCADE"))
    cluster_index: Mapped[int] = mapped_column(Integer)
    label: Mapped[str] = mapped_column(Text)
    centroid: Mapped[list[float]] = mapped_column(Vector(1536))
    top_skills: Mapped[list[str]] = mapped_column(ARRAY(String), server_default=text("'{}'"))
    job_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    run: Mapped["ClusteringRun"] = relationship("ClusteringRun", back_populates="clusters")
    memberships: Mapped[list["JobClusterMembership"]] = relationship(
        "JobClusterMembership", back_populates="cluster", cascade="all, delete-orphan"
    )


class JobClusterMembership(Base):
    __tablename__ = "job_cluster_memberships"
    __table_args__ = (UniqueConstraint("job_id", "run_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("uuid_generate_v4()"))
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    cluster_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("role_clusters.id", ondelete="CASCADE"))
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clustering_runs.id", ondelete="CASCADE"))
    distance_to_centroid: Mapped[float] = mapped_column(Float)

    cluster: Mapped["RoleCluster"] = relationship("RoleCluster", back_populates="memberships")
