"""ORM model for resumes and their tailored variants."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base
from database.models.embeddings import ResumeEmbedding


class ResumeVariantType(enum.Enum):
    base = "base"
    tailored = "tailored"


class Resume(Base):
    __tablename__ = "resumes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("uuid_generate_v4()"))
    variant: Mapped[ResumeVariantType] = mapped_column(
        Enum(ResumeVariantType, name="resume_variant_type"),
        server_default=text("'base'"),
    )
    parent_resume_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("resumes.id", ondelete="SET NULL"), default=None
    )

    file_name: Mapped[str] = mapped_column(Text)
    file_path: Mapped[Optional[str]] = mapped_column(Text, default=None)

    target_cluster_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("role_clusters.id", ondelete="SET NULL"), default=None
    )

    raw_text: Mapped[str] = mapped_column(Text)
    parsed_skills: Mapped[list[str]] = mapped_column(ARRAY(String), server_default=text("'{}'"))
    parsed_titles: Mapped[list[str]] = mapped_column(ARRAY(String), server_default=text("'{}'"))
    parsed_years_exp: Mapped[Optional[int]] = mapped_column(Integer, default=None)

    is_embedded: Mapped[bool] = mapped_column(Boolean, server_default=text("FALSE"))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    parent: Mapped[Optional["Resume"]] = relationship(
        "Resume", remote_side="Resume.id", foreign_keys=[parent_resume_id]
    )
    embeddings: Mapped[list["ResumeEmbedding"]] = relationship(
        "ResumeEmbedding", back_populates="resume", cascade="all, delete-orphan"
    )
