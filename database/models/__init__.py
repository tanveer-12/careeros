"""Import all ORM models to ensure SQLAlchemy's mapper registry is fully populated."""

from database.models.clusters import ClusteringRun, JobClusterMembership, RoleCluster
from database.models.embeddings import ResumeEmbedding
from database.models.execution import ExecutionAction, ExecutionPlan
from database.models.jobs import Job, JobEmbedding
from database.models.rankings import Ranking
from database.models.resumes import Resume

__all__ = [
    "Job",
    "JobEmbedding",
    "ResumeEmbedding",
    "ClusteringRun",
    "RoleCluster",
    "JobClusterMembership",
    "Resume",
    "Ranking",
    "ExecutionPlan",
    "ExecutionAction",
]
