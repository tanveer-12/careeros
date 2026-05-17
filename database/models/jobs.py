"""ORM models for job postings and their vector embeddings."""

import enum
import uuid
from datetime import datetime
from typing import Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
    BOOLEAN,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base


class JobSource(enum.Enum):
    greenhouse = "greenhouse"
    lever = "lever"
    ashby = "ashby"
    manual = "manual"


class JobStatus(enum.Enum):
    raw = "raw"
    normalized = "normalized"
    embedded = "embedded"
    clustered = "clustered"


class EmploymentType(enum.Enum):
    full_time = "full_time"
    part_time = "part_time"
    contract = "contract"
    internship = "internship"
    other = "other"


class WorkLocation(enum.Enum):
    remote = "remote"
    hybrid = "hybrid"
    onsite = "onsite"


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (UniqueConstraint("source", "external_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("uuid_generate_v4()"))
    source: Mapped[JobSource] = mapped_column(Enum(JobSource, name="job_source"))
    external_id: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(Text)
    raw_payload: Mapped[dict] = mapped_column(JSONB)
    scraped_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    title: Mapped[Optional[str]] = mapped_column(Text, default=None)
    company: Mapped[Optional[str]] = mapped_column(Text, default=None)
    location: Mapped[Optional[str]] = mapped_column(Text, default=None)
    work_location: Mapped[Optional[WorkLocation]] = mapped_column(
        Enum(WorkLocation, name="work_location"), default=None
    )
    employment_type: Mapped[Optional[EmploymentType]] = mapped_column(
        Enum(EmploymentType, name="employment_type"), default=None
    )
    description: Mapped[Optional[str]] = mapped_column(Text, default=None)
    skills: Mapped[Optional[list[str]]] = mapped_column(ARRAY(String), default=None)
    domain: Mapped[Optional[str]] = mapped_column(Text, default=None)
    seniority: Mapped[Optional[str]] = mapped_column(Text, default=None)
    salary_min: Mapped[Optional[int]] = mapped_column(Integer, default=None)
    salary_max: Mapped[Optional[int]] = mapped_column(Integer, default=None)
    salary_currency: Mapped[Optional[str]] = mapped_column(String(3), default=None)
    posted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), default=None)
    closes_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), default=None)
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="job_status"), default=JobStatus.raw
    )
    normalized_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    embeddings: Mapped[list["JobEmbedding"]] = relationship(
        "JobEmbedding", back_populates="job", cascade="all, delete-orphan"
    )


class JobEmbedding(Base):
    __tablename__ = "job_embeddings"
    __table_args__ = (UniqueConstraint("job_id", "model"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("uuid_generate_v4()"))
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    model: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(1536))
    input_text: Mapped[str] = mapped_column(Text)
    token_count: Mapped[Optional[int]] = mapped_column(Integer, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    job: Mapped["Job"] = relationship("Job", back_populates="embeddings")