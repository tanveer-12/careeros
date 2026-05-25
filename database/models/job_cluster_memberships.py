# database/models/job_cluster_memberships.py

from typing import Optional, TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.models.base import Base


if TYPE_CHECKING:
    from database.models.jobs import Job
    from database.models.clustering import ClusteringRun, RoleCluster


class JobClusterMembership(Base):
    __tablename__ = "job_cluster_memberships"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    job_id: Mapped[str] = mapped_column(String, ForeignKey("jobs.id"), nullable=False)
    cluster_id: Mapped[str] = mapped_column(String, ForeignKey("role_clusters.id"), nullable=False)
    run_id: Mapped[str] = mapped_column(String, ForeignKey("clustering_runs.id"), nullable=False)
    distance_to_centroid: Mapped[float] = mapped_column(Float, nullable=False)

    job: Mapped["Job"] = relationship(
        "Job", back_populates="memberships"
    )
    run: Mapped["ClusteringRun"] = relationship(
        "ClusteringRun"
    )
    cluster: Mapped["RoleCluster"] = relationship(
        "RoleCluster", back_populates="memberships"
    )