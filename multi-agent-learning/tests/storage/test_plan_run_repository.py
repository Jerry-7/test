from datetime import datetime, timezone

import pytest

from storage.db.models import ExecutionRow, PlanRow, PlanRunTaskRow
from storage.repositories.plan_run_repository import PlanRunRepository


@pytest.mark.postgres
def test_create_and_finish_run_roundtrip(db_session):
    plan = PlanRow(
        source_goal="goal",
        provider="openai",
        model_name="gpt-5-nano",
        thinking_mode="default",
    )
    db_session.add(plan)
    db_session.commit()
    plan_id = str(plan.plan_id)

    repo = PlanRunRepository(session_factory=lambda: db_session)
    run_id = repo.create_run(
        plan_id=plan_id,
        max_workers=2,
        started_at="2026-04-21T00:00:00+00:00",
    )

    created = repo.get_run(run_id)
    assert created["status"] == "running"
    assert created["plan_id"] == plan_id
    assert created["max_workers"] == 2
    assert datetime.fromisoformat(created["started_at"]).astimezone(
        timezone.utc
    ) == datetime(2026, 4, 21, 0, 0, 0, tzinfo=timezone.utc)
    assert created["ended_at"] is None

    repo.finish_run(
        run_id=run_id,
        status="completed",
        ended_at="2026-04-21T00:00:03+00:00",
    )

    finished = repo.get_run(run_id)
    assert finished["status"] == "completed"
    assert datetime.fromisoformat(finished["ended_at"]).astimezone(
        timezone.utc
    ) == datetime(2026, 4, 21, 0, 0, 3, tzinfo=timezone.utc)


@pytest.mark.postgres
def test_upsert_task_state_updates_existing_row(db_session):
    plan = PlanRow(
        source_goal="goal",
        provider="openai",
        model_name="gpt-5-nano",
        thinking_mode="default",
    )
    db_session.add(plan)
    db_session.commit()
    plan_id = str(plan.plan_id)

    execution = ExecutionRow(
        task_id="exec-1",
        task_text="task",
        agent_name="AnalysisAgent",
        status="completed",
        output="ok",
        error="",
        traceback="",
        started_at=datetime.fromisoformat("2026-04-21T00:00:00+00:00"),
        ended_at=datetime.fromisoformat("2026-04-21T00:00:01+00:00"),
        metadata_json={},
    )
    db_session.add(execution)
    db_session.commit()

    repo = PlanRunRepository(session_factory=lambda: db_session)
    run_id = repo.create_run(
        plan_id=plan_id,
        max_workers=1,
        started_at="2026-04-21T00:00:00+00:00",
    )

    repo.upsert_task_state(
        run_id=run_id,
        task_id="task-1",
        agent_name="AnalysisAgent",
        status="running",
        execution_task_id=None,
        state_snapshot={"task-1": "running"},
    )
    repo.upsert_task_state(
        run_id=run_id,
        task_id="task-1",
        agent_name="AnalysisAgent",
        status="completed",
        execution_task_id="exec-1",
        state_snapshot={"task-1": "completed"},
    )

    rows = (
        db_session.query(PlanRunTaskRow)
        .filter(
            PlanRunTaskRow.run_id == run_id,
            PlanRunTaskRow.task_id == "task-1",
        )
        .all()
    )
    assert len(rows) == 1
    assert rows[0].status == "completed"
    assert rows[0].execution_task_id == "exec-1"
    assert rows[0].state_snapshot == {"task-1": "completed"}
