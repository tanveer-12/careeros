# database/models/two_week_plan_steps.py

from datetime import datetime, timezone
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Enum as SqlEnum, Float, JSON, Integer, DateTime, Boolean, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.models.base import Base
from database.models.enums import PlanStepType

if TYPE_CHECKING:
    from database.models.two_week_plans import TwoWeekPlan


class TwoWeekPlanStep(Base):
    __tablename__ = "two_week_plan_steps"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    plan_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("two_week_plans.id"), nullable=False)
    week_number: Mapped[int] = mapped_column(Integer, nullable=False)
    step_type: Mapped[PlanStepType] = mapped_column(SqlEnum(PlanStepType, name="plan_step_type", create_type=False), nullable=False)

    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    resource_links: Mapped[Optional[List[str]]] = mapped_column(JSON)
    estimated_hours: Mapped[Optional[float]] = mapped_column(Float)
    ai_explanation: Mapped[Optional[str]] = mapped_column(String)
    is_completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    plan: Mapped["TwoWeekPlan"] = relationship(
        "TwoWeekPlan", back_populates="steps"
    )
