# database/models/jobs.py

from datetime import datetime
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import JSON, String, Boolean, Integer, DateTime, Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pgvector.sqlalchemy import Vector
from database.models.base import Base
from database.models.enums import JobSource, EmploymentType, WorkLocation


if TYPE_CHECKING:
    from database.models.job_embeddings import JobEmbedding
    from database.models.job_cluster_memberships import JobClusterMembership


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    source: Mapped[JobSource] = mapped_column(SqlEnum(JobSource), nullable=False)
    external_id: Mapped[str] = mapped_column(String, nullable=False)
    source_url: Mapped[str] = mapped_column(String, nullable=False)

    raw_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    scraped_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    title: Mapped[Optional[str]] = mapped_column(String)
    company: Mapped[Optional[str]] = mapped_column(String)
    location: Mapped[Optional[str]] = mapped_column(String)
    work_location: Mapped[Optional[WorkLocation]] = mapped_column(SqlEnum(WorkLocation))
    employment_type: Mapped[Optional[EmploymentType]] = mapped_column(SqlEnum(EmploymentType))
    description: Mapped[Optional[str]] = mapped_column(String)
    skills: Mapped[Optional[List[str]]] = mapped_column(JSON)
    domain: Mapped[Optional[str]] = mapped_column(String)
    seniority: Mapped[Optional[str]] = mapped_column(String)
    salary_currency: Mapped[Optional[str]] = mapped_column(String(3), default=None)
    salary_min: Mapped[Optional[int]] = mapped_column(Integer, default=None)
    salary_max: Mapped[Optional[int]] = mapped_column(Integer, default=None)
    posted_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    closes_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    embeddings: Mapped["JobEmbedding"] = relationship(
        "JobEmbedding", back_populates="job", cascade="all, delete-orphan"
    )
    memberships: Mapped[List["JobClusterMembership"]] = relationship(
        "JobClusterMembership", back_populates="job", cascade="all, delete-orphan"
    )


class JobEmbedding(Base):
    __tablename__ = "job_embeddings"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    job_id: Mapped[str] = mapped_column(String, nullable=False)

    model: Mapped[str] = mapped_column(String, nullable=False)
    embedding: Mapped[Vector] = mapped_column(Vector(384), nullable=False)
    input_text: Mapped[str] = mapped_column(String, nullable=False)
    token_count: Mapped[Optional[int]] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        # ForeignKey to jobs.id (mapped in SQLAlchemy relationship)
        # In the DB, this is enforced via DDL; in ORM, we keep it simple
    )


    