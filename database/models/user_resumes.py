# database/models/user_resumes.py

from datetime import datetime, timezone
from typing import Optional, List, TYPE_CHECKING

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, JSON, String, Boolean, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.models.base import Base


if TYPE_CHECKING:
    from database.models.resume_embeddings import ResumeEmbedding
    from database.models.rankings import Ranking


class UserResume(Base):
    __tablename__ = "user_resumes"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, nullable=False)

    file_name: Mapped[str] = mapped_column(String, nullable=False)
    file_path: Mapped[Optional[str]] = mapped_column(String)

    raw_text: Mapped[str] = mapped_column(String, nullable=False)
    parsed_skills: Mapped[Optional[List[str]]] = mapped_column(JSON, default=[])
    parsed_titles: Mapped[Optional[List[str]]] = mapped_column(JSON, default=[])
    parsed_years_exp: Mapped[Optional[int]] = mapped_column(Integer)

    is_embedded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    embeddings: Mapped["ResumeEmbedding"] = relationship(
        "ResumeEmbedding", back_populates="resume", cascade="all, delete-orphan"
    )


class ResumeEmbedding(Base):
    __tablename__ = "resume_embeddings"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    resume_id: Mapped[str] = mapped_column(String, ForeignKey("user_resumes.id"), nullable=False)

    model: Mapped[str] = mapped_column(String, nullable=False)
    embedding: Mapped[Vector] = mapped_column(Vector(384), nullable=False)
    input_text: Mapped[str] = mapped_column(String, nullable=False)
    token_count: Mapped[Optional[int]] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    resume: Mapped["UserResume"] = relationship(
        "UserResume", back_populates="embeddings"
    )