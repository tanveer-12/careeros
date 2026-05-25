# database/models/enums.py

from enum import Enum


class JobSource(str, Enum):
    remotive = "remotive"
    manual = "manual"


class EmploymentType(str, Enum):
    full_time = "full_time"
    part_time = "part_time"
    contract = "contract"
    internship = "internship"
    freelance = "freelance"
    other = "other"


class WorkLocation(str, Enum):
    remote = "remote"
    hybrid = "hybrid"
    onsite = "onsite"


class FitCategory(str, Enum):
    strong = "strong"
    adjacent = "adjacent"
    weak = "weak"


class WeekPlanStatus(str, Enum):
    active = "active"
    completed = "completed"
    archived = "archived"
    failed = "failed"


class PlanStepType(str, Enum):
    learning_task = "learning_task"
    writing_task = "writing_task"
    apply_task = "apply_task"