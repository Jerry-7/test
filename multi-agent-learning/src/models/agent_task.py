from __future__ import annotations

from dataclasses import dataclass

from models.plan_task import PlanTask


@dataclass(frozen=True)
class AgentTask:
    """面向 Agent 的结构化任务输入。"""

    plan_task: PlanTask
    rendered_task: str

