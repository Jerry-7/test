from __future__ import annotations

import pytest

from models.plan_task import PlanTask
from models.task import TaskExecution
from storage.repositories.execution_repository import ExecutionRepository
from storage.repositories.plan_repository import PlanRepository
from storage.repositories.plan_run_repository import PlanRunRepository


@pytest.mark.postgres
def test_console_query_methods_return_summary_shapes(db_session):
    plan_repo = PlanRepository(session_factory=lambda: db_session)
    run_repo = PlanRunRepository(session_factory=lambda: db_session)
    execution_repo = ExecutionRepository(session_factory=lambda: db_session)

    plan_id = plan_repo.save_plan(
        goal="learn multi-agent scheduling",
        provider="openai",
        model_name="gpt-5-mini",
        thinking_mode="default",
        tasks=[
            PlanTask(
                id="task-1",
                title="Analyze architecture",
                type="analysis",
                depends_on=[],
                status="pending",
                priority=1,
            )
        ],
    )

    execution_repo.append(
        TaskExecution(
            task_id="exec-1",
            task_text="Analyze architecture",
            agent_name="AnalysisAgent",
            status="completed",
            output="ok",
            error="",
            traceback="",
            started_at="2026-04-22T00:00:00+00:00",
            ended_at="2026-04-22T00:00:01+00:00",
            metadata={"provider": "openai"},
        )
    )

    run_id = run_repo.create_run(
        plan_id=plan_id,
        max_workers=1,
        started_at="2026-04-22T00:00:00+00:00",
    )
    run_repo.upsert_task_state(
        run_id=run_id,
        task_id="task-1",
        agent_name="AnalysisAgent",
        status="completed",
        execution_task_id="exec-1",
        state_snapshot={"task-1": "completed"},
    )

    plan_summaries = plan_repo.list_plans()
    plan_summary = plan_repo.get_plan_summary(plan_id)
    run_summaries = run_repo.list_runs()
    run_summary = run_repo.get_run_summary(run_id)
    run_tasks = run_repo.list_run_tasks(run_id)
    executions = execution_repo.load_by_task_ids(["exec-1"])

    assert plan_summaries[0]["plan_id"] == plan_id
    assert plan_summary["tasks"][0]["task_id"] == "task-1"
    assert run_summaries[0]["run_id"] == run_id
    assert run_summary["run_id"] == run_id
    assert run_tasks[0]["execution_task_id"] == "exec-1"
    assert executions[0]["task_id"] == "exec-1"
