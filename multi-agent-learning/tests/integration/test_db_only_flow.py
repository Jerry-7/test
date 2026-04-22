from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from urllib.parse import urlparse
from uuid import UUID

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from models.agent_task import AgentTask
from models.plan_constants import (
    TASK_STATUS_COMPLETED,
    TASK_STATUS_PENDING,
    TASK_TYPE_ANALYSIS,
    TASK_TYPE_IMPLEMENTATION,
)
from models.plan_task import PlanTask
from models.task import TaskExecution
from scheduler.dispatcher import Dispatcher
from scheduler.plan_runner import PlanRunner
from scheduler.plan_validator import PlanValidator
from storage.db.models import (
    Base,
    ExecutionRow,
    PlanRow,
    PlanRunRow,
    PlanRunTaskRow,
    PlanTaskRow,
)
from storage.execution_store import ExecutionStore
from storage.repositories.plan_repository import PlanRepository
from storage.repositories.plan_run_repository import PlanRunRepository


def _resolve_safe_test_database_url() -> str:
    database_url = os.getenv("TEST_DATABASE_URL", "").strip()
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is required for postgres integration tests.")

    if os.getenv("TEST_DB_RESET_OK", "").strip() != "1":
        pytest.skip("Set TEST_DB_RESET_OK=1 to allow schema reset in integration test.")

    parsed = urlparse(database_url)
    host = (parsed.hostname or "").lower()
    db_name = parsed.path.lstrip("/").lower()
    if host not in {"localhost", "127.0.0.1"}:
        pytest.skip("Refusing to reset non-local database.")
    if not re.match(r"^(test($|_.+)|.+_test)$", db_name):
        pytest.skip(
            "Refusing to reset database not explicitly named as a test database."
        )

    return database_url


def _reset_schema(database_url: str) -> None:
    engine = create_engine(database_url, future=True)
    try:
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
    finally:
        engine.dispose()


class _DeterministicAgent:
    def __init__(self, name: str, store: ExecutionStore):
        self.name = name
        self.store = store

    def run(self, task_text: str) -> TaskExecution:
        execution = TaskExecution.create(task_text=task_text, agent_name=self.name)
        execution.status = TASK_STATUS_COMPLETED
        execution.output = "ok"
        execution.started_at = datetime.now(timezone.utc).isoformat()
        execution.ended_at = datetime.now(timezone.utc).isoformat()
        self.store.append(execution)
        return execution

    def run_agent_task(self, agent_task: AgentTask) -> TaskExecution:
        return self.run(agent_task.rendered_task)


@pytest.mark.postgres
def test_db_only_flow_without_external_llm():
    database_url = _resolve_safe_test_database_url()
    _reset_schema(database_url)

    engine = create_engine(database_url, future=True)
    try:
        session_factory = lambda: Session(engine)
        store = ExecutionStore(
            database_url=database_url,
            session_factory=session_factory,
        )
        plan_repository = PlanRepository(session_factory=session_factory)
        plan_run_repository = PlanRunRepository(session_factory=session_factory)

        # basic stage
        basic_execution = TaskExecution.create(
            task_text="ping",
            agent_name="BasicAgent",
        )
        basic_execution.status = TASK_STATUS_COMPLETED
        basic_execution.output = "pong"
        basic_execution.started_at = datetime.now(timezone.utc).isoformat()
        basic_execution.ended_at = datetime.now(timezone.utc).isoformat()
        store.append(basic_execution)

        # planner stage
        plan_id = plan_repository.save_plan(
            goal="local db-only integration",
            provider="local",
            model_name="stub",
            thinking_mode="default",
            tasks=[
                PlanTask(
                    id="task-1",
                    title="Analyze",
                    type=TASK_TYPE_ANALYSIS,
                    depends_on=[],
                    status=TASK_STATUS_PENDING,
                    priority=1,
                ),
                PlanTask(
                    id="task-2",
                    title="Implement",
                    type=TASK_TYPE_IMPLEMENTATION,
                    depends_on=["task-1"],
                    status=TASK_STATUS_PENDING,
                    priority=2,
                ),
            ],
        )

        # run-plan stage
        dispatcher = Dispatcher()
        dispatcher.register(
            TASK_TYPE_ANALYSIS,
            _DeterministicAgent("AnalysisAgent", store=store),
        )
        dispatcher.register(
            TASK_TYPE_IMPLEMENTATION,
            _DeterministicAgent("ImplementationAgent", store=store),
        )
        runner = PlanRunner(
            dispatcher=dispatcher,
            plan_validator=PlanValidator(),
            plan_repository=plan_repository,
            plan_run_repository=plan_run_repository,
            max_workers=1,
        )
        executions = runner.run_from_plan_id(plan_id)
        assert len(executions) == 2
        assert all(item.status == TASK_STATUS_COMPLETED for item in executions)

        with Session(engine) as session:
            plan_uuid = UUID(plan_id)
            assert session.get(PlanRow, plan_uuid) is not None
            assert (
                session.query(PlanTaskRow)
                .filter(PlanTaskRow.plan_id == plan_uuid)
                .count()
                == 2
            )

            run_row = (
                session.query(PlanRunRow)
                .filter(PlanRunRow.plan_id == plan_uuid)
                .one()
            )
            assert run_row.status == TASK_STATUS_COMPLETED
            assert (
                session.query(PlanRunTaskRow)
                .filter(PlanRunTaskRow.run_id == run_row.run_id)
                .count()
                == 2
            )
            assert session.query(ExecutionRow).count() == 3
    finally:
        engine.dispose()
