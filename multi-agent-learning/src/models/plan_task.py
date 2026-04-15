from __future__ import annotations

from pydantic import BaseModel, Field

from models.plan_constants import (
    DEFAULT_PRIORITY,
    TASK_STATUS_PENDING,
    TASK_TYPES,
    TaskState,
    TaskType,
)


class PlanTask(BaseModel):
    """阶段 2 的结构化计划任务。"""


    id: str = Field(description="任务唯一标识，例如 task-1")
    title: str = Field(description="任务名称")
    type: TaskType = Field(
        description=f"任务类型，只使用 {', '.join(TASK_TYPES)}"
    )
    depends_on: list[str] = Field(
        default_factory=list,
        description="当前任务依赖的前置任务 id 列表",
    )
    status: TaskState = Field(
        default=TASK_STATUS_PENDING,
        description="任务状态，当前阶段统一为 pending",
    )
    priority: int = Field(
        default=DEFAULT_PRIORITY,
        description="任务优先级，数字越小越优先，1 表示最高优先级",
    )


class PlanResult(BaseModel):
    """PlannerAgent 的结构化输出。"""

    tasks: list[PlanTask] = Field(
        description="按执行顺序组织的学习计划任务列表"
    )
