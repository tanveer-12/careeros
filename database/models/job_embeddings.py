# database/models/job_embeddings.py

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import ForeignKey, String, Integer, DateTime
from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pgvector.sqlalchemy import Vector
from database.models.jobs import Job
from database.models.base import Base


class JobEmbedding(Base):
    __tablename__ = "job_embeddings"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    job_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("jobs.id"), nullable=False)
    model: Mapped[str] = mapped_column(String, nullable=False)
    embedding: Mapped[Vector] = mapped_column(Vector(384), nullable=False)
    input_text: Mapped[str] = mapped_column(String, nullable=False)
    token_count: Mapped[Optional[int]] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    job: Mapped["Job"] = relationship(
        "Job", back_populates="embeddings"
    )