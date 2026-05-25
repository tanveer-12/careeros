# database/models/two_week_plans.py

from datetime import datetime, timezone
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import ForeignKey, JSON, Enum, String, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.models.base import Base
from database.models.enums import WeekPlanStatus


if TYPE_CHECKING:
    from database.models.user_resumes import UserResume
    from database.models.clustering import RoleCluster
    from database.models.two_week_plan_steps import TwoWeekPlanStep


class TwoWeekPlan(Base):
    __tablename__ = "two_week_plans"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    resume_id: Mapped[str] = mapped_column(String, ForeignKey("user_resumes.id"), nullable=False)
    cluster_id: Mapped[str] = mapped_column(String, ForeignKey("role_clusters.id"), nullable=False)

    target_location: Mapped[Optional[str]] = mapped_column(String)
    target_work_style: Mapped[Optional[str]] = mapped_column(String)
    target_employment_type: Mapped[Optional[str]] = mapped_column(String)

    status: Mapped[WeekPlanStatus] = mapped_column(
        Enum(WeekPlanStatus), nullable=False, default=WeekPlanStatus.active
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    resume: Mapped["UserResume"] = relationship("UserResume")
    cluster: Mapped["RoleCluster"] = relationship("RoleCluster")
    steps: Mapped[List["TwoWeekPlanStep"]] = relationship(
        "TwoWeekPlanStep", back_populates="plan", cascade="all, delete-orphan"
    )
