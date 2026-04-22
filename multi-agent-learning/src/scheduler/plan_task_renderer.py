from __future__ import annotations

from models.agent_task import AgentTask
from models.plan_task import PlanTask


class PlanTaskRenderer:
    """计划任务渲染器。

    作用：
    - 把结构化 `PlanTask` 转成 `AgentTask`
    - 集中管理面向 Agent 的任务文本模板
    """

    def build(self, task: PlanTask) -> AgentTask:
        depends_on = ", ".join(task.depends_on) or "none"
        rendered_task = (
            f"Execute this subtask from a multi-agent plan.\n\n"
            f"Task id: {task.id}\n"
            f"Task priority: {task.priority}\n"
            f"Task type: {task.type}\n"
            f"Title: {task.title}\n"
            f"Depends on: {depends_on}\n\n"
            f"Please complete only this subtask."
        )
        return AgentTask(plan_task=task, rendered_task=rendered_task)
