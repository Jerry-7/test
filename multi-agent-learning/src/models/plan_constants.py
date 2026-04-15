from __future__ import annotations

from typing import Literal, TypeAlias

TASK_TYPE_ANALYSIS = "analysis"
TASK_TYPE_PLANNING = "planning"
TASK_TYPE_DESIGN = "design"
TASK_TYPE_IMPLEMENTATION = "implementation"
TASK_TYPE_REVIEW = "review"

TASK_TYPES = (
    TASK_TYPE_ANALYSIS,
    TASK_TYPE_PLANNING,
    TASK_TYPE_DESIGN,
    TASK_TYPE_IMPLEMENTATION,
    TASK_TYPE_REVIEW,
)

TaskType: TypeAlias = Literal[
    "analysis",
    "planning",
    "design",
    "implementation",
    "review",
]

TASK_STATUS_PENDING = "pending"
TASK_STATUS_READY = "ready"
TASK_STATUS_RUNNING = "running"
TASK_STATUS_COMPLETED = "completed"
TASK_STATUS_FAILED = "failed"

TaskState: TypeAlias = Literal[
    "pending",
    "ready",
    "running",
    "completed",
    "failed",
]

TaskStateMap: TypeAlias = dict[str, TaskState]

DEFAULT_PRIORITY = 100
