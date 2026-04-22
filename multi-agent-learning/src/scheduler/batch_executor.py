from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from abc import ABC, abstractmethod

from models.plan_constants import TASK_STATUS_COMPLETED, TASK_STATUS_RUNNING, TaskStateMap
from models.plan_task import PlanTask
from models.task import TaskExecution
from scheduler.dispatcher import Dispatcher
from scheduler.plan_task_renderer import PlanTaskRenderer


class BatchExecutor(ABC):
    """批次执行器抽象。

    作用：
    - 负责“本轮已选任务”的具体执行方式
    - 为后续替换线程池/并发执行器预留统一接口
    """

    @abstractmethod
    def execute(
        self,
        selected_tasks: list[PlanTask],
        task_states: TaskStateMap,
        running_task_ids: set[str],
    ) -> list[tuple[PlanTask, TaskExecution]]:
        raise NotImplementedError


class SerialBatchExecutor(BatchExecutor):
    """串行批次执行器。

    当前逐个执行 selected_tasks；遇到失败任务后立即停止本批次。
    """

    def __init__(self, dispatcher: Dispatcher, task_renderer: PlanTaskRenderer):
        self.dispatcher = dispatcher
        self.task_renderer = task_renderer

    def execute(
        self,
        selected_tasks: list[PlanTask],
        task_states: TaskStateMap,
        running_task_ids: set[str],
    ) -> list[tuple[PlanTask, TaskExecution]]:
        executed_items: list[tuple[PlanTask, TaskExecution]] = []
        for ready_task in selected_tasks:
            agent = self.dispatcher.dispatch(ready_task)
            task_states[ready_task.id] = TASK_STATUS_RUNNING
            running_task_ids.add(ready_task.id)
            try:
                agent_task = self.task_renderer.build(ready_task)
                execution = agent.run_agent_task(agent_task)
            finally:
                running_task_ids.remove(ready_task.id)

            executed_items.append((ready_task, execution))
            if execution.status != TASK_STATUS_COMPLETED:
                break

        return executed_items


class ThreadPoolBatchExecutor(BatchExecutor):
    """线程池批次执行器。

    作用：
    - 并发执行同一批次 selected_tasks
    - 返回结果顺序与 selected_tasks 保持一致
    """

    def __init__(self, dispatcher: Dispatcher, task_renderer: PlanTaskRenderer):
        self.dispatcher = dispatcher
        self.task_renderer = task_renderer

    def execute(
        self,
        selected_tasks: list[PlanTask],
        task_states: TaskStateMap,
        running_task_ids: set[str],
    ) -> list[tuple[PlanTask, TaskExecution]]:
        for task in selected_tasks:
            task_states[task.id] = TASK_STATUS_RUNNING
            running_task_ids.add(task.id)

        future_to_task: dict[object, PlanTask] = {}
        executed_items_by_id: dict[str, tuple[PlanTask, TaskExecution]] = {}
        first_error: Exception | None = None

        with ThreadPoolExecutor(
            max_workers=len(selected_tasks),
            thread_name_prefix="plan-runner",
        ) as executor:
            for task in selected_tasks:
                future = executor.submit(self._execute_one_task, task)
                future_to_task[future] = task

            for future in as_completed(future_to_task):
                task = future_to_task[future]
                try:
                    execution = future.result()
                    executed_items_by_id[task.id] = (task, execution)
                except Exception as exc:
                    if first_error is None:
                        first_error = exc
                finally:
                    running_task_ids.remove(task.id)

        if first_error is not None:
            raise RuntimeError("ThreadPoolBatchExecutor failed.") from first_error

        return [
            executed_items_by_id[task.id]
            for task in selected_tasks
        ]

    def _execute_one_task(self, task: PlanTask) -> TaskExecution:
        agent = self.dispatcher.dispatch(task)
        agent_task = self.task_renderer.build(task)
        return agent.run_agent_task(agent_task)
