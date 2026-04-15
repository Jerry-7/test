from __future__ import annotations

import json
from pathlib import Path

from models.plan_constants import (
    DEFAULT_PRIORITY,
    TASK_STATUS_COMPLETED,
    TASK_STATUS_FAILED,
    TASK_STATUS_PENDING,
    TASK_STATUS_READY,
    TASK_STATUS_RUNNING,
    TaskStateMap,
)
from models.plan_task import PlanTask
from models.task import TaskExecution
from scheduler.dispatcher import Dispatcher
from scheduler.plan_validator import PlanValidator


class PlanRunner:
    """串行执行结构化计划。

    Dispatcher 只负责“选 Agent”，PlanRunner 负责“按顺序执行”。
    """

    def __init__(self, dispatcher: Dispatcher, plan_validator: PlanValidator):
        self.dispatcher = dispatcher
        self.plan_validator = plan_validator

    def run(self, plan: list[PlanTask]) -> list[TaskExecution]:
        task_states: TaskStateMap = {
            item.id: TASK_STATUS_PENDING for item in plan
        }

        executions: list[TaskExecution] = []
        while True:
            ready_tasks = self._get_ready_tasks(plan=plan, task_states=task_states)

            if not ready_tasks:
                if self._is_all_finished(task_states):
                    break
                raise ValueError(
                    "Plan is blocked: no ready tasks found, but unfinished tasks remain."
                )
            ready_task = self._select_task(ready_tasks=ready_tasks)
            task_states[ready_task.id] = TASK_STATUS_READY

            agent = self.dispatcher.dispatch(ready_task)
            task_states[ready_task.id] = TASK_STATUS_RUNNING
            execution = agent.run(self._build_task_text(ready_task))

            if execution.status != TASK_STATUS_COMPLETED:
                task_states[ready_task.id] = TASK_STATUS_FAILED
                self._attach_plan_metadata(
                    execution=execution, task=ready_task, task_states=task_states
                )
                executions.append(execution)
                break

            task_states[ready_task.id] = TASK_STATUS_COMPLETED
            self._attach_plan_metadata(
                execution=execution, task=ready_task, task_states=task_states
            )

            executions.append(execution)
        return executions

    def _get_ready_tasks(
        self,
        plan: list[PlanTask],
        task_states: TaskStateMap,
    ) -> list[PlanTask]:

        ready_tasks: list[PlanTask] = []
        for item in plan:
            if task_states[item.id] != TASK_STATUS_PENDING:
                continue

            depends_on = item.depends_on
            if all(
                task_states.get(dep_id) == TASK_STATUS_COMPLETED
                for dep_id in depends_on
            ):
                ready_tasks.append(item)

        return ready_tasks

    def _select_task(self, ready_tasks: list[PlanTask]) -> PlanTask:
        return min(
            ready_tasks,
            key=lambda task: task.priority,
        )

    def _is_all_finished(self, task_states: TaskStateMap) -> bool:
        for val in task_states.values():
            if val not in {TASK_STATUS_COMPLETED, TASK_STATUS_FAILED}:
                return False
        return True

    def _attach_plan_metadata(
        self,
        execution: TaskExecution,
        task: PlanTask,
        task_states: TaskStateMap,
    ) -> None:
        execution.metadata["plan_task_id"] = task.id
        execution.metadata["plan_task_type"] = task.type
        execution.metadata["plan_task_title"] = task.title
        execution.metadata["plan_task_state"] = task_states[task.id]
        execution.metadata["plan_task_states"] = task_states.copy()

    def run_from_path(self, path: str) -> list[TaskExecution]:
        plan_tasks = self.load_plan(path)
        self.plan_validator.validate(plan_list=plan_tasks)
        return self.run(plan_tasks)

    def load_plan(self, path: str) -> list[PlanTask]:
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"Plan file not found: {path}")

        content = file_path.read_text(encoding="utf-8")
        plan = json.loads(content)
        if not isinstance(plan, list):
            raise ValueError("Plan file must contain a JSON list.")

        return [PlanTask.model_validate(item) for item in plan]

    def _build_task_text(self, task: PlanTask) -> str:
        depends_on = ", ".join(task.depends_on) or "none"
        priority = task.priority if task.priority else DEFAULT_PRIORITY
        return (
            f"Execute this subtask from a multi-agent plan.\n\n"
            f"Task id: {task.id}\n"
            f"Task priority: {priority}\n"
            f"Task type: {task.type}\n"
            f"Title: {task.title}\n"
            f"Depends on: {depends_on}\n\n"
            f"Please complete only this subtask."
        )
