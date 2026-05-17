"""ORM models for execution plans and their decomposed weekly actions."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base


class ExecutionStatus(enum.Enum):
    pending = "pending"
    in_progress = "in_progress"
    complete = "complete"
    skipped = "skipped"
    failed = "failed"


class ExecutionPlan(Base):
    __tablename__ = "execution_plans"
    __table_args__ = (UniqueConstraint("resume_id", "run_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("uuid_generate_v4()"))
    resume_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("resumes.id", ondelete="CASCADE"))
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clustering_runs.id", ondelete="CASCADE"))

    plan: Mapped[dict] = mapped_column(JSONB)

    json_export_path: Mapped[Optional[str]] = mapped_column(Text, default=None)
    xlsx_export_path: Mapped[Optional[str]] = mapped_column(Text, default=None)

    status: Mapped[ExecutionStatus] = mapped_column(
        Enum(ExecutionStatus, name="execution_status"),
        server_default=text("'pending'"),
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    actions: Mapped[list["ExecutionAction"]] = relationship(
        "ExecutionAction", back_populates="plan", cascade="all, delete-orphan"
    )


class ExecutionAction(Base):
    __tablename__ = "execution_actions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("uuid_generate_v4()"))
    plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("execution_plans.id", ondelete="CASCADE"))
    week: Mapped[int] = mapped_column(Integer)
    day: Mapped[Optional[int]] = mapped_column(Integer, default=None)
    action_type: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    job_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("jobs.id", ondelete="SET NULL"), default=None
    )
    status: Mapped[ExecutionStatus] = mapped_column(
        Enum(ExecutionStatus, name="execution_status"),
        server_default=text("'pending'"),
    )
    due_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), default=None)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    plan: Mapped["ExecutionPlan"] = relationship("ExecutionPlan", back_populates="actions")
