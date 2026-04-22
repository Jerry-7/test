from __future__ import annotations

from abc import ABC, abstractmethod

from models.plan_task import PlanTask


class TaskSelectionPolicy(ABC):
    """任务选择策略抽象。

    作用：
    - 定义“从 ready_tasks 中选哪个任务执行”的统一接口
    - 允许在不改 `PlanRunner` 的前提下替换调度策略
    """

    def select(self, ready_tasks: list[PlanTask]) -> PlanTask:
        selected_tasks = self.select_many(ready_tasks=ready_tasks, limit=1)
        if not selected_tasks:
            raise ValueError("TaskSelectionPolicy returned no task.")
        return selected_tasks[0]

    @abstractmethod
    def select_many(
        self,
        ready_tasks: list[PlanTask],
        limit: int,
    ) -> list[PlanTask]:
        raise NotImplementedError


class PriorityTaskSelectionPolicy(TaskSelectionPolicy):
    """按优先级选择任务的默认策略。

    作用：
    - 优先选择 `priority` 更小的任务
    - 在同优先级下按 `task.id` 稳定排序
    """

    def select_many(
        self,
        ready_tasks: list[PlanTask],
        limit: int,
    ) -> list[PlanTask]:
        if not ready_tasks:
            raise ValueError("ready_tasks cannot be empty.")
        if limit <= 0:
            raise ValueError("limit must be > 0.")

        sorted_tasks = sorted(
            ready_tasks,
            key=lambda task: (task.priority, task.id),
        )
        return sorted_tasks[:limit]
