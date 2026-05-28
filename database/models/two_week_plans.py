# database/models/two_week_plans.py

from datetime import datetime, timezone
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import ForeignKey, JSON, Enum as SqlEnum, String, DateTime, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.models.base import Base
from database.models.enums import WeekPlanStatus


if TYPE_CHECKING:
    from database.models.user_resumes import UserResume
    from database.models.role_archetypes import RoleArchetype
    from database.models.two_week_plan_steps import TwoWeekPlanStep


class TwoWeekPlan(Base):
    __tablename__ = "two_week_plans"

    id:           Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    resume_id:    Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("user_resumes.id"), nullable=False)
    archetype_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("role_archetypes.id"), nullable=False)

    target_location:        Mapped[Optional[str]] = mapped_column(String)
    target_work_style:      Mapped[Optional[str]] = mapped_column(String)
    target_employment_type: Mapped[Optional[str]] = mapped_column(String)

    status: Mapped[WeekPlanStatus] = mapped_column(
        SqlEnum(WeekPlanStatus, name="week_plan_status", create_type=False), nullable=False, default=WeekPlanStatus.active
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    resume:    Mapped["UserResume"]    = relationship("UserResume")
    archetype: Mapped["RoleArchetype"] = relationship("RoleArchetype")
    steps: Mapped[List["TwoWeekPlanStep"]] = relationship(
        "TwoWeekPlanStep", back_populates="plan", cascade="all, delete-orphan"
    )
