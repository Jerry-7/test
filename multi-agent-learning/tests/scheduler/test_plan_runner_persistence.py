from __future__ import annotations

import pytest

from models.plan_task import PlanTask
from models.task import TaskExecution
from scheduler.batch_executor import BatchExecutor
from scheduler.dispatcher import Dispatcher
from scheduler.plan_runner import PlanRunner
from scheduler.plan_validator import PlanValidator


class _FakePlanRepository:
    def __init__(self, tasks: list[PlanTask]):
        self.tasks = tasks
        self.loaded_plan_id: str | None = None

    def load_plan(self, plan_id: str) -> list[PlanTask]:
        self.loaded_plan_id = plan_id
        return self.tasks


class _FakePlanRunRepository:
    def __init__(self):
        self.created: list[dict] = []
        self.finished: list[dict] = []
        self.upserts: list[dict] = []

    def create_run(self, plan_id: str, max_workers: int, started_at: str) -> str:
        self.created.append(
            {
                "plan_id": plan_id,
                "max_workers": max_workers,
                "started_at": started_at,
            }
        )
        return "run-1"

    def finish_run(self, run_id: str, status: str, ended_at: str) -> None:
        self.finished.append(
            {
                "run_id": run_id,
                "status": status,
                "ended_at": ended_at,
            }
        )

    def upsert_task_state(
        self,
        run_id: str,
        task_id: str,
        agent_name: str,
        status: str,
        execution_task_id: str | None,
        state_snapshot: dict,
    ) -> None:
        self.upserts.append(
            {
                "run_id": run_id,
                "task_id": task_id,
                "agent_name": agent_name,
                "status": status,
                "execution_task_id": execution_task_id,
                "state_snapshot": state_snapshot,
            }
        )


class _CompletedBatchExecutor(BatchExecutor):
    def execute(self, selected_tasks, task_states, running_task_ids):
        task = selected_tasks[0]
        execution = TaskExecution.create(
            task_text=task.title,
            agent_name="AnalysisAgent",
        )
        execution.status = "completed"
        execution.started_at = "2026-04-21T00:00:00+00:00"
        execution.ended_at = "2026-04-21T00:00:01+00:00"
        return [(task, execution)]


class _ErrorBatchExecutor(BatchExecutor):
    def execute(self, selected_tasks, task_states, running_task_ids):
        raise RuntimeError("executor boom")


def _single_task_plan() -> list[PlanTask]:
    return [
        PlanTask(
            id="task-1",
            title="Analyze",
            type="analysis",
            depends_on=[],
            status="pending",
            priority=1,
        )
    ]


def test_run_from_plan_id_persists_run_lifecycle_success():
    plan_repo = _FakePlanRepository(tasks=_single_task_plan())
    run_repo = _FakePlanRunRepository()
    runner = PlanRunner(
        dispatcher=Dispatcher(),
        plan_validator=PlanValidator(),
        plan_repository=plan_repo,
        plan_run_repository=run_repo,
        batch_executor=_CompletedBatchExecutor(),
    )

    executions = runner.run_from_plan_id("plan-1")

    assert len(executions) == 1
    assert plan_repo.loaded_plan_id == "plan-1"
    assert len(run_repo.created) == 1
    assert run_repo.finished[-1]["status"] == "completed"
    assert len(run_repo.upserts) == 1
    assert run_repo.upserts[0]["status"] == "completed"


def test_run_from_plan_id_marks_failed_when_executor_errors():
    plan_repo = _FakePlanRepository(tasks=_single_task_plan())
    run_repo = _FakePlanRunRepository()
    runner = PlanRunner(
        dispatcher=Dispatcher(),
        plan_validator=PlanValidator(),
        plan_repository=plan_repo,
        plan_run_repository=run_repo,
        batch_executor=_ErrorBatchExecutor(),
    )

    with pytest.raises(RuntimeError, match="executor boom"):
        runner.run_from_plan_id("plan-1")

    assert len(run_repo.created) == 1
    assert run_repo.upserts == []
    assert run_repo.finished[-1]["status"] == "failed"


def test_run_from_plan_id_reuses_explicit_run_id():
    plan_repo = _FakePlanRepository(tasks=_single_task_plan())
    run_repo = _FakePlanRunRepository()
    runner = PlanRunner(
        dispatcher=Dispatcher(),
        plan_validator=PlanValidator(),
        plan_repository=plan_repo,
        plan_run_repository=run_repo,
        batch_executor=_CompletedBatchExecutor(),
    )

    executions = runner.run_from_plan_id("plan-1", run_id="run-existing")

    assert len(executions) == 1
    assert run_repo.created == []
    assert run_repo.upserts[0]["run_id"] == "run-existing"
    assert run_repo.finished[-1]["run_id"] == "run-existing"
