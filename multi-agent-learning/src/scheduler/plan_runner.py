from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from models.plan_constants import (
    TASK_STATUS_COMPLETED,
    TASK_STATUS_FAILED,
    TASK_STATUS_PENDING,
    TASK_STATUS_READY,
    TaskStateMap,
)
from models.plan_task import PlanTask
from models.task import TaskExecution
from scheduler.batch_executor import BatchExecutor, SerialBatchExecutor
from scheduler.dispatcher import Dispatcher
from scheduler.plan_task_renderer import PlanTaskRenderer
from scheduler.plan_validator import PlanValidator
from scheduler.task_selection_policy import (
    PriorityTaskSelectionPolicy,
    TaskSelectionPolicy,
)


class PlanRunner:
    """按批次执行结构化计划。

    Dispatcher 只负责“选 Agent”，PlanRunner 负责“按顺序执行”。
    """

    def __init__(
        self,
        dispatcher: Dispatcher,
        plan_validator: PlanValidator,
        plan_repository: object | None = None,
        plan_run_repository: object | None = None,
        task_renderer: PlanTaskRenderer | None = None,
        task_selection_policy: TaskSelectionPolicy | None = None,
        batch_executor: BatchExecutor | None = None,
        max_workers: int = 1,
    ):
        if max_workers <= 0:
            raise ValueError("max_workers must be > 0.")

        self.dispatcher = dispatcher
        self.plan_validator = plan_validator
        self.plan_repository = plan_repository
        self.plan_run_repository = plan_run_repository
        self.task_renderer = task_renderer or PlanTaskRenderer()
        self.task_selection_policy = (
            task_selection_policy or PriorityTaskSelectionPolicy()
        )
        self.batch_executor = (
            batch_executor
            or SerialBatchExecutor(
                dispatcher=self.dispatcher,
                task_renderer=self.task_renderer,
            )
        )
        self.max_workers = max_workers
        self._active_run_id: str | None = None

    def run(self, plan: list[PlanTask]) -> list[TaskExecution]:
        self.plan_validator.validate(plan_list=plan)
        task_states: TaskStateMap = {
            item.id: TASK_STATUS_PENDING for item in plan
        }
        running_task_ids: set[str] = set()

        executions: list[TaskExecution] = []
        while True:
            ready_tasks = self._get_ready_tasks(plan=plan, task_states=task_states)

            if not ready_tasks:
                if self._is_all_finished(task_states):
                    break
                raise ValueError(
                    "Plan is blocked: no ready tasks found, but unfinished tasks remain."
                )

            selected_tasks = self._select_ready_batch(
                ready_tasks=ready_tasks,
                running_task_ids=running_task_ids,
            )

            for ready_task in selected_tasks:
                task_states[ready_task.id] = TASK_STATUS_READY

            executed_items = self.batch_executor.execute(
                selected_tasks=selected_tasks,
                task_states=task_states,
                running_task_ids=running_task_ids,
            )

            should_stop = False
            for task, execution in executed_items:
                if self._finalize_execution(
                    execution=execution,
                    task=task,
                    task_states=task_states,
                    executions=executions,
                ):
                    should_stop = True

            if should_stop:
                break
        return executions

    def _finalize_execution(
        self,
        execution: TaskExecution,
        task: PlanTask,
        task_states: TaskStateMap,
        executions: list[TaskExecution],
    ) -> bool:
        if execution.status != TASK_STATUS_COMPLETED:
            task_states[task.id] = TASK_STATUS_FAILED
            self._attach_plan_metadata(
                execution=execution,
                task=task,
                task_states=task_states,
            )
            self._persist_task_state(
                execution=execution,
                task=task,
                task_states=task_states,
            )
            executions.append(execution)
            return True

        task_states[task.id] = TASK_STATUS_COMPLETED
        self._attach_plan_metadata(
            execution=execution,
            task=task,
            task_states=task_states,
        )
        self._persist_task_state(
            execution=execution,
            task=task,
            task_states=task_states,
        )
        executions.append(execution)
        return False

    def _select_ready_batch(
        self,
        ready_tasks: list[PlanTask],
        running_task_ids: set[str],
    ) -> list[PlanTask]:
        available_slots = self.max_workers - len(running_task_ids)
        if available_slots <= 0:
            raise ValueError(
                "No available worker slots for ready tasks. "
                f"max_workers={self.max_workers}, running={len(running_task_ids)}."
            )

        selected_tasks = self.task_selection_policy.select_many(
            ready_tasks=ready_tasks,
            limit=available_slots,
        )
        self._validate_selected_tasks(
            ready_tasks=ready_tasks,
            selected_tasks=selected_tasks,
            max_selected=available_slots,
        )
        return selected_tasks

    def _validate_selected_tasks(
        self,
        ready_tasks: list[PlanTask],
        selected_tasks: list[PlanTask],
        max_selected: int,
    ) -> None:
        if not selected_tasks:
            raise ValueError("TaskSelectionPolicy returned no task.")
        if len(selected_tasks) > max_selected:
            raise ValueError(
                "TaskSelectionPolicy returned too many tasks: "
                f"{len(selected_tasks)} > {max_selected}."
            )

        ready_task_ids = {task.id for task in ready_tasks}
        selected_task_ids = [task.id for task in selected_tasks]
        unique_selected_ids = set(selected_task_ids)

        if len(unique_selected_ids) != len(selected_task_ids):
            raise ValueError("TaskSelectionPolicy returned duplicated task.")
        if not unique_selected_ids.issubset(ready_task_ids):
            raise ValueError("TaskSelectionPolicy returned non-ready task.")

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
        return self.run(plan_tasks)

    def run_from_plan_id(self, plan_id: str) -> list[TaskExecution]:
        if self.plan_repository is None:
            raise RuntimeError("PlanRunner requires plan_repository for run_from_plan_id.")
        if self.plan_run_repository is None:
            raise RuntimeError(
                "PlanRunner requires plan_run_repository for run_from_plan_id."
            )

        plan_tasks = self.plan_repository.load_plan(plan_id)
        run_id = self.plan_run_repository.create_run(
            plan_id=plan_id,
            max_workers=self.max_workers,
            started_at=self._utc_now_iso(),
        )
        previous_run_id = self._active_run_id
        self._active_run_id = run_id
        try:
            executions = self.run(plan_tasks)
        except Exception:
            self.plan_run_repository.finish_run(
                run_id=run_id,
                status=TASK_STATUS_FAILED,
                ended_at=self._utc_now_iso(),
            )
            raise
        else:
            final_status = (
                TASK_STATUS_FAILED
                if any(item.status != TASK_STATUS_COMPLETED for item in executions)
                else TASK_STATUS_COMPLETED
            )
            self.plan_run_repository.finish_run(
                run_id=run_id,
                status=final_status,
                ended_at=self._utc_now_iso(),
            )
            return executions
        finally:
            self._active_run_id = previous_run_id

    def load_plan(self, path: str) -> list[PlanTask]:
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"Plan file not found: {path}")

        content = file_path.read_text(encoding="utf-8")
        plan = json.loads(content)
        if not isinstance(plan, list):
            raise ValueError("Plan file must contain a JSON list.")

        return [PlanTask.model_validate(item) for item in plan]

    def _persist_task_state(
        self,
        execution: TaskExecution,
        task: PlanTask,
        task_states: TaskStateMap,
    ) -> None:
        if self.plan_run_repository is None or self._active_run_id is None:
            return
        self.plan_run_repository.upsert_task_state(
            run_id=self._active_run_id,
            task_id=task.id,
            agent_name=execution.agent_name,
            status=task_states[task.id],
            execution_task_id=execution.task_id,
            state_snapshot=task_states.copy(),
        )

    def _utc_now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()
