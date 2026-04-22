from __future__ import annotations

from agents.base_agent import BaseAgent
from models.plan_constants import TaskType
from models.plan_task import PlanTask


class Dispatcher:
    """任务分发器。

    作用：
    - 维护 `task_type -> agent` 映射
    - 根据任务类型选择对应执行 Agent
    """

    def __init__(self):
        self._agents: dict[TaskType, BaseAgent] = {}

    def register(self, task_type: TaskType, agent: BaseAgent) -> None:
        self._agents[task_type] = agent

    def dispatch(self, task: PlanTask) -> BaseAgent:
        if task.type not in self._agents:
            raise ValueError(f"No agent registered for task type: {task.type}.")

        return self._agents[task.type]
