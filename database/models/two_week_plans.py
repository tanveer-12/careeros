# database/models/two_week_plans.py

from datetime import datetime
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import JSON, String, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.models.base import Base
from database.models.enums import WeekPlanStatus, PlanStepType


if TYPE_CHECKING:
    from database.models.user_resumes import UserResume
    from database.models.clustering import RoleCluster
    from database.models.two_week_plan_steps import TwoWeekPlanStep


class TwoWeekPlan(Base):
    __tablename__ = "two_week_plans"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    resume_id: Mapped[str] = mapped_column(String, nullable=False)
    cluster_id: Mapped[str] = mapped_column(String, nullable=False)

    target_location: Mapped[Optional[str]] = mapped_column(String)
    target_work_style: Mapped[Optional[str]] = mapped_column(String)
    target_employment_type: Mapped[Optional[str]] = mapped_column(String)

    status: Mapped[WeekPlanStatus] = mapped_column(
        SqlEnum(WeekPlanStatus), nullable=False, default=WeekPlanStatus.active
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    resume: Mapped["UserResume"] = relationship("UserResume")
    cluster: Mapped["RoleCluster"] = relationship("RoleCluster")
    steps: Mapped[List["TwoWeekPlanStep"]] = relationship(
        "TwoWeekPlanStep", back_populates="plan", cascade="all, delete-orphan"
    )


class TwoWeekPlanStep(Base):
    __tablename__ = "two_week_plan_steps"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    plan_id: Mapped[str] = mapped_column(String, nullable=False)
    week_number: Mapped[int] = mapped_column(Integer, nullable=False)
    step_type: Mapped[PlanStepType] = mapped_column(SqlEnum(PlanStepType), nullable=False)

    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    resource_links: Mapped[Optional[List[str]]] = mapped_column(JSON)
    estimated_hours: Mapped[Optional[float]] = mapped_column(Float)
    ai_explanation: Mapped[Optional[str]] = mapped_column(String)
    is_completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    plan: Mapped["TwoWeekPlan"] = relationship("TwoWeekPlan", back_populates="steps")