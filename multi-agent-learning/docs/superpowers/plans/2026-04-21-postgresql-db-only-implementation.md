# PostgreSQL DB-Only Persistence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace JSON persistence with PostgreSQL for executions, plans, and run-plan state while keeping current scheduling behavior stable.

**Architecture:** Keep business logic in agents/scheduler and move all SQL into repository layer. Keep `ExecutionStore` public API stable but delegate internally to `ExecutionRepository`. Add `PlanRepository` and `PlanRunRepository`, then wire them through `main.py` runtime assembly.

**Tech Stack:** Python 3.13, SQLAlchemy 2.x, psycopg 3, pytest

---

## File Structure Map

- Create: `src/storage/db/__init__.py`
- Create: `src/storage/db/session.py`
- Create: `src/storage/db/models.py`
- Create: `src/storage/repositories/__init__.py`
- Create: `src/storage/repositories/execution_repository.py`
- Create: `src/storage/repositories/plan_repository.py`
- Create: `src/storage/repositories/plan_run_repository.py`
- Create: `src/models/planner_run_result.py`
- Create: `tests/conftest.py`
- Create: `tests/storage/test_db_models.py`
- Create: `tests/storage/test_execution_repository.py`
- Create: `tests/storage/test_plan_repository.py`
- Create: `tests/storage/test_plan_run_repository.py`
- Create: `pytest.ini`
- Modify: `requirements.txt`
- Modify: `src/storage/execution_store.py`
- Modify: `src/agents/planner_agent.py`
- Modify: `src/scheduler/plan_runner.py`
- Modify: `src/main.py`
- Modify: `README.md`
- Modify: `.env.example`

---

### Task 1: Add PostgreSQL Foundation and Schema Models

**Files:**
- Create: `src/storage/db/__init__.py`
- Create: `src/storage/db/session.py`
- Create: `src/storage/db/models.py`
- Create: `tests/conftest.py`
- Create: `tests/storage/test_db_models.py`
- Create: `pytest.ini`
- Modify: `requirements.txt`

- [ ] **Step 1: Write the failing test**

```python
# tests/storage/test_db_models.py
from storage.db.models import Base


def test_schema_contains_required_tables():
    table_names = set(Base.metadata.tables.keys())
    assert "executions" in table_names
    assert "plans" in table_names
    assert "plan_tasks" in table_names
    assert "plan_runs" in table_names
    assert "plan_run_tasks" in table_names
```

```python
# tests/conftest.py
import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from storage.db.models import Base


@pytest.fixture(scope="session")
def test_database_url() -> str:
    url = os.getenv("TEST_DATABASE_URL", "").strip()
    if not url:
        pytest.skip("TEST_DATABASE_URL is required for postgres tests")
    return url


@pytest.fixture()
def db_session(test_database_url: str):
    engine = create_engine(test_database_url, future=True)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -3 -m pytest tests/storage/test_db_models.py -v`
Expected: `FAIL` with `ModuleNotFoundError: No module named 'storage.db'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/storage/db/session.py
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def create_engine_from_url(database_url: str):
    cleaned = database_url.strip()
    if not cleaned:
        raise ValueError("database_url cannot be empty.")
    return create_engine(cleaned, pool_pre_ping=True, future=True)


def create_session_factory(database_url: str):
    engine = create_engine_from_url(database_url)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
```

```python
# src/storage/db/models.py
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ExecutionRow(Base):
    __tablename__ = "executions"

    task_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    task_text: Mapped[str] = mapped_column(Text, nullable=False)
    agent_name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    output: Mapped[str] = mapped_column(Text, nullable=False, default="")
    error: Mapped[str] = mapped_column(Text, nullable=False, default="")
    traceback: Mapped[str] = mapped_column(Text, nullable=False, default="")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class PlanRow(Base):
    __tablename__ = "plans"

    plan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_goal: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    thinking_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class PlanTaskRow(Base):
    __tablename__ = "plan_tasks"

    plan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("plans.plan_id", ondelete="CASCADE"), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    depends_on: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)


class PlanRunRow(Base):
    __tablename__ = "plan_runs"

    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("plans.plan_id", ondelete="CASCADE"), nullable=False)
    max_workers: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PlanRunTaskRow(Base):
    __tablename__ = "plan_run_tasks"

    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("plan_runs.run_id", ondelete="CASCADE"), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    agent_name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    execution_task_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("executions.task_id"), nullable=True)
    state_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
```

```python
# src/storage/db/__init__.py
from .models import Base
from .session import create_engine_from_url, create_session_factory
```

```ini
# pytest.ini
[pytest]
pythonpath = src
markers =
    postgres: tests that require PostgreSQL
```

```text
# requirements.txt
langchain==1.2.15
langchain-openai==1.1.12
sqlalchemy==2.0.41
psycopg[binary]==3.2.9
pytest==8.3.5
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -3 -m pytest tests/storage/test_db_models.py -v`
Expected: `PASS`

- [ ] **Step 5: Commit**

```bash
git add requirements.txt pytest.ini tests/conftest.py tests/storage/test_db_models.py src/storage/db/__init__.py src/storage/db/session.py src/storage/db/models.py
git commit -m "feat: add postgres schema foundation and test harness"
```

### Task 2: Implement Execution Repository and Delegate ExecutionStore

**Files:**
- Create: `src/storage/repositories/execution_repository.py`
- Create: `src/storage/repositories/__init__.py`
- Modify: `src/storage/execution_store.py`
- Create: `tests/storage/test_execution_repository.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/storage/test_execution_repository.py
from models.task import TaskExecution
from storage.repositories.execution_repository import ExecutionRepository


def test_append_and_load_all_roundtrip(db_session):
    repo = ExecutionRepository(session_factory=lambda: db_session)
    execution = TaskExecution.create(task_text="hello", agent_name="BasicAgent")
    execution.status = "completed"
    execution.output = "ok"
    execution.started_at = "2026-04-21T00:00:00+00:00"
    execution.ended_at = "2026-04-21T00:00:01+00:00"

    repo.append(execution)
    records = repo.load_all()

    assert len(records) == 1
    assert records[0]["task_id"] == execution.task_id
    assert records[0]["output"] == "ok"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -3 -m pytest tests/storage/test_execution_repository.py -v -m postgres`
Expected: `FAIL` with `ModuleNotFoundError: No module named 'storage.repositories.execution_repository'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/storage/repositories/execution_repository.py
from __future__ import annotations

from datetime import datetime

from models.task import TaskExecution, TaskExecutionRecord
from storage.db.models import ExecutionRow


class ExecutionRepository:
    def __init__(self, session_factory):
        self._session_factory = session_factory

    def append(self, execution: TaskExecution) -> None:
        with self._session_factory() as session:
            row = ExecutionRow(
                task_id=execution.task_id,
                task_text=execution.task_text,
                agent_name=execution.agent_name,
                status=execution.status,
                output=execution.output,
                error=execution.error,
                traceback=execution.traceback,
                started_at=datetime.fromisoformat(execution.started_at),
                ended_at=datetime.fromisoformat(execution.ended_at),
                metadata_json=execution.metadata,
            )
            session.add(row)
            session.commit()

    def load_all(self) -> list[TaskExecutionRecord]:
        with self._session_factory() as session:
            rows = session.query(ExecutionRow).order_by(ExecutionRow.created_at.asc()).all()
            return [
                {
                    "task_id": row.task_id,
                    "task_text": row.task_text,
                    "agent_name": row.agent_name,
                    "status": row.status,
                    "output": row.output,
                    "error": row.error,
                    "traceback": row.traceback,
                    "started_at": row.started_at.isoformat(),
                    "ended_at": row.ended_at.isoformat(),
                    "metadata": row.metadata_json,
                }
                for row in rows
            ]
```

```python
# src/storage/execution_store.py
from __future__ import annotations

from models.task import TaskExecution, TaskExecutionRecord
from storage.db.session import create_session_factory
from storage.repositories.execution_repository import ExecutionRepository


class ExecutionStore:
    def __init__(self, database_url: str):
        session_factory = create_session_factory(database_url)
        self._repository = ExecutionRepository(session_factory=session_factory)

    def append(self, execution: TaskExecution) -> None:
        self._repository.append(execution)

    def load_all(self) -> list[TaskExecutionRecord]:
        return self._repository.load_all()
```

```python
# src/storage/repositories/__init__.py
from .execution_repository import ExecutionRepository
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -3 -m pytest tests/storage/test_execution_repository.py -v -m postgres`
Expected: `PASS`

- [ ] **Step 5: Commit**

```bash
git add src/storage/repositories/__init__.py src/storage/repositories/execution_repository.py src/storage/execution_store.py tests/storage/test_execution_repository.py
git commit -m "feat: add execution repository and delegate execution store"
```

### Task 3: Implement PlanRepository and Persist Planner Output

**Files:**
- Create: `src/storage/repositories/plan_repository.py`
- Create: `src/models/planner_run_result.py`
- Modify: `src/agents/planner_agent.py`
- Create: `tests/storage/test_plan_repository.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/storage/test_plan_repository.py
from models.plan_task import PlanTask
from storage.repositories.plan_repository import PlanRepository


def test_save_and_load_plan_roundtrip(db_session):
    repo = PlanRepository(session_factory=lambda: db_session)
    plan_id = repo.save_plan(
        goal="build feature",
        provider="openai",
        model_name="gpt-5-nano",
        thinking_mode="default",
        tasks=[
            PlanTask(id="task-1", title="Analyze", type="analysis", depends_on=[], status="pending", priority=1),
            PlanTask(id="task-2", title="Implement", type="implementation", depends_on=["task-1"], status="pending", priority=2),
        ],
    )

    loaded = repo.load_plan(plan_id)

    assert [item.id for item in loaded] == ["task-1", "task-2"]
    assert loaded[1].depends_on == ["task-1"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -3 -m pytest tests/storage/test_plan_repository.py -v -m postgres`
Expected: `FAIL` with `ModuleNotFoundError: No module named 'storage.repositories.plan_repository'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/storage/repositories/plan_repository.py
from __future__ import annotations

from uuid import UUID

from models.plan_task import PlanTask
from storage.db.models import PlanRow, PlanTaskRow


class PlanRepository:
    def __init__(self, session_factory):
        self._session_factory = session_factory

    def save_plan(
        self,
        goal: str,
        provider: str,
        model_name: str,
        thinking_mode: str,
        tasks: list[PlanTask],
    ) -> str:
        with self._session_factory() as session:
            plan = PlanRow(
                source_goal=goal,
                provider=provider,
                model_name=model_name,
                thinking_mode=thinking_mode,
            )
            session.add(plan)
            session.flush()
            for item in tasks:
                session.add(
                    PlanTaskRow(
                        plan_id=plan.plan_id,
                        task_id=item.id,
                        title=item.title,
                        type=item.type,
                        priority=item.priority,
                        status=item.status,
                        depends_on=item.depends_on,
                    )
                )
            session.commit()
            return str(plan.plan_id)

    def load_plan(self, plan_id: str) -> list[PlanTask]:
        with self._session_factory() as session:
            rows = (
                session.query(PlanTaskRow)
                .filter(PlanTaskRow.plan_id == UUID(plan_id))
                .order_by(PlanTaskRow.priority.asc(), PlanTaskRow.task_id.asc())
                .all()
            )
            return [
                PlanTask(
                    id=row.task_id,
                    title=row.title,
                    type=row.type,
                    depends_on=row.depends_on,
                    status=row.status,
                    priority=row.priority,
                )
                for row in rows
            ]
```

```python
# src/models/planner_run_result.py
from __future__ import annotations

from dataclasses import dataclass

from models.plan_task import PlanTask


@dataclass(frozen=True)
class PlannerRunResult:
    plan_id: str
    tasks: list[PlanTask]
```

```python
# src/agents/planner_agent.py (replace run method)
def run(self, goal: str) -> PlannerRunResult:
    cleaned_goal = goal.strip()
    if not cleaned_goal:
        raise ValueError("Goal cannot be empty.")

    try:
        plan = self._handle_goal(cleaned_goal)
        plan_id = self.plan_repository.save_plan(
            goal=cleaned_goal,
            provider=self.provider_config.provider,
            model_name=self.provider_config.model_name,
            thinking_mode=self.thinking_mode,
            tasks=plan,
        )
        return PlannerRunResult(plan_id=plan_id, tasks=plan)
    except Exception as exc:
        raise RuntimeError(f"PlannerAgent failed: {exc}") from exc
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -3 -m pytest tests/storage/test_plan_repository.py -v -m postgres`
Expected: `PASS`

- [ ] **Step 5: Commit**

```bash
git add src/storage/repositories/plan_repository.py src/models/planner_run_result.py src/agents/planner_agent.py tests/storage/test_plan_repository.py
git commit -m "feat: add plan repository and persist planner output"
```

### Task 4: Implement PlanRunRepository and Wire PlanRunner Runtime State

**Files:**
- Create: `src/storage/repositories/plan_run_repository.py`
- Modify: `src/scheduler/plan_runner.py`
- Create: `tests/storage/test_plan_run_repository.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/storage/test_plan_run_repository.py
from storage.db.models import PlanRow
from storage.repositories.plan_run_repository import PlanRunRepository


def test_create_and_finish_run(db_session):
    plan = PlanRow(
        source_goal="goal",
        provider="openai",
        model_name="gpt-5-nano",
        thinking_mode="default",
    )
    db_session.add(plan)
    db_session.commit()

    repo = PlanRunRepository(session_factory=lambda: db_session)
    run_id = repo.create_run(
        plan_id=str(plan.plan_id),
        max_workers=2,
        started_at="2026-04-21T00:00:00+00:00",
    )

    repo.finish_run(
        run_id=run_id,
        status="completed",
        ended_at="2026-04-21T00:00:03+00:00",
    )

    row = repo.get_run(run_id)
    assert row["status"] == "completed"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -3 -m pytest tests/storage/test_plan_run_repository.py -v -m postgres`
Expected: `FAIL` with `ModuleNotFoundError: No module named 'storage.repositories.plan_run_repository'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/storage/repositories/plan_run_repository.py
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from storage.db.models import PlanRunRow, PlanRunTaskRow


class PlanRunRepository:
    def __init__(self, session_factory):
        self._session_factory = session_factory

    def create_run(self, plan_id: str, max_workers: int, started_at: str) -> str:
        with self._session_factory() as session:
            row = PlanRunRow(
                plan_id=UUID(plan_id),
                max_workers=max_workers,
                status="running",
                started_at=datetime.fromisoformat(started_at),
            )
            session.add(row)
            session.commit()
            return str(row.run_id)

    def upsert_task_state(
        self,
        run_id: str,
        task_id: str,
        agent_name: str,
        status: str,
        execution_task_id: str | None,
        state_snapshot: dict,
    ) -> None:
        with self._session_factory() as session:
            existing = (
                session.query(PlanRunTaskRow)
                .filter(
                    PlanRunTaskRow.run_id == UUID(run_id),
                    PlanRunTaskRow.task_id == task_id,
                )
                .one_or_none()
            )
            if existing is None:
                existing = PlanRunTaskRow(
                    run_id=UUID(run_id),
                    task_id=task_id,
                    agent_name=agent_name,
                    status=status,
                    execution_task_id=execution_task_id,
                    state_snapshot=state_snapshot,
                )
                session.add(existing)
            else:
                existing.agent_name = agent_name
                existing.status = status
                existing.execution_task_id = execution_task_id
                existing.state_snapshot = state_snapshot
            session.commit()

    def finish_run(self, run_id: str, status: str, ended_at: str) -> None:
        with self._session_factory() as session:
            row = session.query(PlanRunRow).filter(PlanRunRow.run_id == UUID(run_id)).one()
            row.status = status
            row.ended_at = datetime.fromisoformat(ended_at)
            session.commit()

    def get_run(self, run_id: str) -> dict[str, str]:
        with self._session_factory() as session:
            row = session.query(PlanRunRow).filter(PlanRunRow.run_id == UUID(run_id)).one()
            return {"run_id": str(row.run_id), "status": row.status}
```

```python
# src/scheduler/plan_runner.py (new constructor args + runtime writes)
def __init__(
    self,
    dispatcher,
    plan_validator,
    plan_repository,
    plan_run_repository,
    task_renderer=None,
    task_selection_policy=None,
    batch_executor=None,
    max_workers: int = 1,
):
    self.plan_repository = plan_repository
    self.plan_run_repository = plan_run_repository


def run_from_plan_id(self, plan_id: str) -> list[TaskExecution]:
    plan_tasks = self.plan_repository.load_plan(plan_id)
    run_id = self.plan_run_repository.create_run(
        plan_id=plan_id,
        max_workers=self.max_workers,
        started_at=utc_now_iso(),
    )
    executions = self.run(plan_tasks)
    final_status = "failed" if any(item.status != "completed" for item in executions) else "completed"
    self.plan_run_repository.finish_run(run_id=run_id, status=final_status, ended_at=utc_now_iso())
    return executions
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -3 -m pytest tests/storage/test_plan_run_repository.py -v -m postgres`
Expected: `PASS`

- [ ] **Step 5: Commit**

```bash
git add src/storage/repositories/plan_run_repository.py src/scheduler/plan_runner.py tests/storage/test_plan_run_repository.py
git commit -m "feat: persist run-plan state with plan run repository"
```

### Task 5: Wire CLI to Database URL and Plan ID (DB-Only Contract)

**Files:**
- Modify: `src/main.py`
- Modify: `src/agents/planner_agent.py`
- Modify: `README.md`
- Modify: `.env.example`

- [ ] **Step 1: Write the failing test**

```python
# tests/storage/test_cli_contract.py
import argparse

from main import build_parser


def test_run_plan_requires_plan_id_when_agent_is_run_plan():
    parser: argparse.ArgumentParser = build_parser()
    args = parser.parse_args(["--agent", "run-plan", "--database-url", "postgresql+psycopg://u:p@h:5432/db"])
    assert args.plan_id is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -3 -m pytest tests/storage/test_cli_contract.py -v`
Expected: `FAIL` because `--plan-id` argument does not exist yet

- [ ] **Step 3: Write minimal implementation**

```python
# src/main.py (argument changes)
parser.add_argument(
    "--database-url",
    default=None,
    help="PostgreSQL URL, e.g. postgresql+psycopg://user:pwd@host:5432/db",
)
parser.add_argument(
    "--plan-id",
    default=None,
    help="Plan ID generated by planner mode, used by run-plan mode.",
)
```

```python
# src/main.py (validation changes)
if not args.database_url:
    parser.error("--database-url is required.")
if args.agent == "run-plan" and not args.plan_id:
    parser.error("--plan-id is required when --agent is run-plan.")
```

```python
# README.md (command examples)
py -3 src/main.py --agent planner --provider openai --database-url "postgresql+psycopg://user:pwd@localhost:5432/agents" --task "build a multi-agent learning roadmap"

py -3 src/main.py --agent run-plan --provider openai --database-url "postgresql+psycopg://user:pwd@localhost:5432/agents" --plan-id "11111111-1111-1111-1111-111111111111" --max-workers 2
```

```text
# .env.example
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/multi_agent_learning
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -3 -m pytest tests/storage/test_cli_contract.py -v`
Expected: `PASS`

- [ ] **Step 5: Commit**

```bash
git add src/main.py src/agents/planner_agent.py README.md .env.example tests/storage/test_cli_contract.py
git commit -m "feat: switch cli contract to database-url and plan-id"
```

### Task 6: End-to-End Regression for Basic / Planner / Run-Plan

**Files:**
- Create: `tests/integration/test_db_only_flow.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_db_only_flow.py
import subprocess


def test_basic_planner_run_plan_flow_with_postgres(monkeypatch):
    # This test is intentionally integration-level and requires a live TEST_DATABASE_URL.
    # It should fail first because planner output does not yet include plan_id contract.
    assert False, "planner output and run-plan handoff not wired yet"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -3 -m pytest tests/integration/test_db_only_flow.py -v -m postgres`
Expected: `FAIL` with assertion message about planner output handoff

- [ ] **Step 3: Write minimal implementation**

```python
# tests/integration/test_db_only_flow.py
import os
import re
import subprocess

import pytest


def _run(command: list[str]) -> str:
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    return result.stdout


@pytest.mark.postgres
def test_basic_planner_run_plan_flow_with_postgres():
    database_url = os.getenv("TEST_DATABASE_URL", "").strip()
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is required")

    basic_out = _run([
        "py", "-3", "src/main.py",
        "--agent", "basic",
        "--provider", "openai",
        "--database-url", database_url,
        "--task", "ping",
    ])
    assert "status: completed" in basic_out

    planner_out = _run([
        "py", "-3", "src/main.py",
        "--agent", "planner",
        "--provider", "openai",
        "--database-url", database_url,
        "--task", "make a tiny plan",
    ])

    matched = re.search(r"plan_id: ([0-9a-fA-F-]{36})", planner_out)
    assert matched is not None
    plan_id = matched.group(1)

    run_out = _run([
        "py", "-3", "src/main.py",
        "--agent", "run-plan",
        "--provider", "openai",
        "--database-url", database_url,
        "--plan-id", plan_id,
        "--max-workers", "1",
    ])
    assert "agent: PlanRunner" in run_out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -3 -m pytest tests/integration/test_db_only_flow.py -v -m postgres`
Expected: `PASS`

- [ ] **Step 5: Commit**

```bash
git add tests/integration/test_db_only_flow.py
git commit -m "test: add postgres db-only end-to-end regression"
```

---

## Global Verification Commands

Run: `py -3 -m pytest tests/storage -v -m postgres`
Expected: all storage tests `PASS`

Run: `py -3 -m pytest tests/integration/test_db_only_flow.py -v -m postgres`
Expected: integration `PASS`

Run: `py -3 -m compileall src`
Expected: compile success without syntax errors

---

## Rollback Plan

- Revert by commit granularity (`git revert <task-commit-sha>`), from Task 6 back to Task 1.
- If DB schema migration partially applied, drop test database and recreate clean schema before rerun.

---

## Notes for Implementers

- Always initialize schema once before running app in new database: `Base.metadata.create_all(engine)`.
- Keep SQL out of `agents/*` and `scheduler/*`; repository is the only DB write/read boundary.
- Preserve task state names from `models/plan_constants.py` to avoid status drift.
