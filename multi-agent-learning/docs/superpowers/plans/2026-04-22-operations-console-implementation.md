# Operations Console Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local-first operations console that can create plans, launch runs, inspect run/task state, retry runs, and surface honest unsupported pause/cancel controls on top of the current CLI and PostgreSQL execution core.

**Architecture:** Keep `PlannerAgent`, `PlanRunner`, repositories, and PostgreSQL as the only execution core. Add a shared application-service layer for reusable use cases, expose those services through a thin FastAPI API, and build a small React/Vite frontend that polls the API instead of touching the database or CLI directly.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2.x, pytest, React 18, TypeScript, Vite, Vitest

---

## File Structure Map

- Create: `src/application/__init__.py`
- Create: `src/application/context.py`
- Create: `src/application/services/__init__.py`
- Create: `src/application/services/plan_service.py`
- Create: `src/application/services/run_service.py`
- Create: `src/console_api/__init__.py`
- Create: `src/console_api/app.py`
- Create: `src/console_api/schemas.py`
- Create: `src/console_api/routers/__init__.py`
- Create: `src/console_api/routers/plans.py`
- Create: `src/console_api/routers/runs.py`
- Create: `tests/application/test_context.py`
- Create: `tests/application/test_plan_service.py`
- Create: `tests/application/test_run_service.py`
- Create: `tests/api/test_plans_api.py`
- Create: `tests/api/test_runs_api.py`
- Create: `tests/integration/test_console_api_flow.py`
- Create: `tests/storage/test_console_queries.py`
- Create: `console/package.json`
- Create: `console/tsconfig.json`
- Create: `console/vite.config.ts`
- Create: `console/index.html`
- Create: `console/src/main.tsx`
- Create: `console/src/App.tsx`
- Create: `console/src/api/client.ts`
- Create: `console/src/components/AppShell.tsx`
- Create: `console/src/components/StatusBadge.tsx`
- Create: `console/src/routes/DashboardPage.tsx`
- Create: `console/src/routes/PlansPage.tsx`
- Create: `console/src/routes/PlanDetailPage.tsx`
- Create: `console/src/routes/RunsPage.tsx`
- Create: `console/src/routes/RunDetailPage.tsx`
- Create: `console/src/test/App.test.tsx`
- Create: `console/src/test/RunDetailPage.test.tsx`
- Modify: `requirements.txt`
- Modify: `.gitignore`
- Modify: `README.md`
- Modify: `src/main.py`
- Modify: `src/scheduler/plan_runner.py`
- Modify: `src/storage/repositories/execution_repository.py`
- Modify: `src/storage/repositories/plan_repository.py`
- Modify: `src/storage/repositories/plan_run_repository.py`

---

### Task 1: Add Shared Runtime Context and Backend Web Dependencies

**Files:**
- Create: `src/application/__init__.py`
- Create: `src/application/context.py`
- Create: `tests/application/test_context.py`
- Modify: `requirements.txt`
- Modify: `src/main.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/application/test_context.py
from __future__ import annotations

from types import SimpleNamespace

from application.context import build_service_context


def test_build_service_context_uses_resolved_database_url(monkeypatch):
    monkeypatch.setattr(
        "application.context._resolve_database_url",
        lambda database_url, runtime_config: "postgresql://json.example/app",
    )
    monkeypatch.setattr(
        "application.context.resolve_provider_config",
        lambda **_: SimpleNamespace(provider="openai", model_name="gpt-5-mini"),
    )
    monkeypatch.setattr(
        "application.context.create_session_factory",
        lambda database_url: f"session:{database_url}",
    )

    ctx = build_service_context(
        provider="openai",
        model=None,
        base_url=None,
        thinking="default",
        database_url=None,
        runtime_config="config/runtime.json",
    )

    assert ctx.database_url == "postgresql://json.example/app"
    assert ctx.session_factory == "session:postgresql://json.example/app"
    assert ctx.provider_config.provider == "openai"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -3 -m pytest tests/application/test_context.py -v`
Expected: `FAIL` with `ModuleNotFoundError: No module named 'application'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/application/context.py
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from config import ModelProviderConfig, resolve_provider_config
from storage.db.session import create_session_factory


@dataclass(frozen=True)
class ServiceContext:
    provider_config: ModelProviderConfig
    thinking_mode: str
    database_url: str
    session_factory: object


def _load_runtime_config(config_path: str | None) -> dict:
    cleaned = (config_path or "").strip()
    if not cleaned:
        return {}

    raw_path = Path(cleaned)
    resolved_path = raw_path if raw_path.is_absolute() else Path.cwd() / raw_path
    if not resolved_path.exists():
        return {}

    content = resolved_path.read_text(encoding="utf-8").strip()
    if not content:
        return {}

    data = json.loads(content)
    if not isinstance(data, dict):
        raise ValueError("runtime config must be a JSON object.")
    return data


def _resolve_database_url(database_url: str | None, runtime_config: str | None) -> str:
    cleaned_database_url = (database_url or "").strip()
    if cleaned_database_url:
        return cleaned_database_url

    env_database_url = os.getenv("DATABASE_URL", "").strip()
    if env_database_url:
        return env_database_url

    config = _load_runtime_config(runtime_config)
    raw_config_database_url = config.get("database_url") or config.get("DATABASE_URL")
    if isinstance(raw_config_database_url, str) and raw_config_database_url.strip():
        return raw_config_database_url.strip()

    return ""


def build_service_context(
    *,
    provider: str,
    model: str | None,
    base_url: str | None,
    thinking: str,
    database_url: str | None,
    runtime_config: str | None,
) -> ServiceContext:
    provider_config = resolve_provider_config(
        provider=provider,
        model_name=model,
        base_url=base_url,
    )
    resolved_database_url = _resolve_database_url(database_url, runtime_config)
    session_factory = create_session_factory(resolved_database_url)
    return ServiceContext(
        provider_config=provider_config,
        thinking_mode=thinking,
        database_url=resolved_database_url,
        session_factory=session_factory,
    )
```

```python
# src/application/__init__.py
from .context import ServiceContext, build_service_context
```

```text
# requirements.txt
langchain==1.2.15
langchain-openai==1.1.12
sqlalchemy==2.0.41
psycopg[binary]==3.2.9
pytest==8.3.5
fastapi==0.116.1
uvicorn==0.35.0
httpx==0.28.1
```

```python
# src/main.py
from application.context import build_service_context


def build_runtime(args: argparse.Namespace) -> RuntimeContext:
    service_context = build_service_context(
        provider=args.provider,
        model=args.model,
        base_url=args.base_url,
        thinking=args.thinking,
        database_url=args.database_url,
        runtime_config=getattr(args, "runtime_config", None),
    )
    provider_config = service_context.provider_config
    session_factory = service_context.session_factory
    database_url = service_context.database_url
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -3 -m pytest tests/application/test_context.py -v`
Expected: `PASS`

- [ ] **Step 5: Commit**

```bash
git add requirements.txt src/application/__init__.py src/application/context.py src/main.py tests/application/test_context.py
git commit -m "feat: add shared runtime context for cli and api"
```

### Task 2: Extend Repositories for Console Read Models and Reusable Run IDs

**Files:**
- Modify: `src/storage/repositories/plan_repository.py`
- Modify: `src/storage/repositories/plan_run_repository.py`
- Modify: `src/storage/repositories/execution_repository.py`
- Modify: `src/scheduler/plan_runner.py`
- Create: `tests/storage/test_console_queries.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/storage/test_console_queries.py
from __future__ import annotations

from models.plan_task import PlanTask
from storage.repositories.plan_repository import PlanRepository
from storage.repositories.plan_run_repository import PlanRunRepository


def test_console_query_methods_return_summary_shapes(db_session):
    plan_repo = PlanRepository(session_factory=lambda: db_session)
    run_repo = PlanRunRepository(session_factory=lambda: db_session)

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
    run_summary = run_repo.get_run_summary(run_id)
    run_tasks = run_repo.list_run_tasks(run_id)

    assert plan_summaries[0]["plan_id"] == plan_id
    assert run_summary["run_id"] == run_id
    assert run_tasks[0]["execution_task_id"] == "exec-1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -3 -m pytest tests/storage/test_console_queries.py -v`
Expected: `FAIL` with `AttributeError` for missing repository query methods

- [ ] **Step 3: Write minimal implementation**

```python
# src/storage/repositories/plan_repository.py
def list_plans(self, limit: int = 20) -> list[dict[str, object]]:
    with self._session_factory() as session:
        plan_rows = (
            session.query(PlanRow)
            .order_by(PlanRow.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "plan_id": str(row.plan_id),
                "source_goal": row.source_goal,
                "provider": row.provider,
                "model_name": row.model_name,
                "thinking_mode": row.thinking_mode,
                "created_at": row.created_at.isoformat(),
            }
            for row in plan_rows
        ]


def get_plan_summary(self, plan_id: str) -> dict[str, object]:
    with self._session_factory() as session:
        plan_row = session.query(PlanRow).filter(PlanRow.plan_id == UUID(plan_id)).one()
        task_rows = (
            session.query(PlanTaskRow)
            .filter(PlanTaskRow.plan_id == UUID(plan_id))
            .order_by(PlanTaskRow.priority.asc(), PlanTaskRow.task_id.asc())
            .all()
        )
        return {
            "plan_id": str(plan_row.plan_id),
            "source_goal": plan_row.source_goal,
            "provider": plan_row.provider,
            "model_name": plan_row.model_name,
            "thinking_mode": plan_row.thinking_mode,
            "created_at": plan_row.created_at.isoformat(),
            "tasks": [
                {
                    "task_id": row.task_id,
                    "title": row.title,
                    "type": row.type,
                    "priority": row.priority,
                    "status": row.status,
                    "depends_on": list(row.depends_on),
                }
                for row in task_rows
            ],
        }
```

```python
# src/storage/repositories/plan_run_repository.py
def get_run_summary(self, run_id: str) -> dict[str, object]:
    return self.get_run(run_id)


def list_runs(self, limit: int = 20) -> list[dict[str, object]]:
    with self._session_factory() as session:
        rows = (
            session.query(PlanRunRow)
            .order_by(PlanRunRow.started_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "run_id": str(row.run_id),
                "plan_id": str(row.plan_id),
                "max_workers": row.max_workers,
                "status": row.status,
                "started_at": row.started_at.isoformat(),
                "ended_at": row.ended_at.isoformat() if row.ended_at else None,
            }
            for row in rows
        ]


def list_run_tasks(self, run_id: str) -> list[dict[str, object]]:
    with self._session_factory() as session:
        rows = (
            session.query(PlanRunTaskRow)
            .filter(PlanRunTaskRow.run_id == UUID(run_id))
            .order_by(PlanRunTaskRow.updated_at.asc(), PlanRunTaskRow.task_id.asc())
            .all()
        )
        return [
            {
                "task_id": row.task_id,
                "agent_name": row.agent_name,
                "status": row.status,
                "execution_task_id": row.execution_task_id,
                "state_snapshot": dict(row.state_snapshot),
                "updated_at": row.updated_at.isoformat(),
            }
            for row in rows
        ]
```

```python
# src/storage/repositories/execution_repository.py
def load_by_task_ids(self, task_ids: list[str]) -> list[TaskExecutionRecord]:
    if not task_ids:
        return []
    with self._session_factory() as session:
        rows = (
            session.query(ExecutionRow)
            .filter(ExecutionRow.task_id.in_(task_ids))
            .order_by(ExecutionRow.created_at.asc())
            .all()
        )
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
# src/scheduler/plan_runner.py
def run_from_plan_id(self, plan_id: str, run_id: str | None = None) -> list[TaskExecution]:
    if self.plan_repository is None:
        raise RuntimeError("PlanRunner requires plan_repository for run_from_plan_id.")
    if self.plan_run_repository is None:
        raise RuntimeError("PlanRunner requires plan_run_repository for run_from_plan_id.")

    plan_tasks = self.plan_repository.load_plan(plan_id)
    resolved_run_id = run_id or self.plan_run_repository.create_run(
        plan_id=plan_id,
        max_workers=self.max_workers,
        started_at=self._utc_now_iso(),
    )
    previous_run_id = self._active_run_id
    self._active_run_id = resolved_run_id
    try:
        executions = self.run(plan_tasks)
    except Exception:
        self.plan_run_repository.finish_run(
            run_id=resolved_run_id,
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
            run_id=resolved_run_id,
            status=final_status,
            ended_at=self._utc_now_iso(),
        )
        return executions
    finally:
        self._active_run_id = previous_run_id
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -3 -m pytest tests/storage/test_console_queries.py -v`
Expected: `PASS`

- [ ] **Step 5: Commit**

```bash
git add src/storage/repositories/plan_repository.py src/storage/repositories/plan_run_repository.py src/storage/repositories/execution_repository.py src/scheduler/plan_runner.py tests/storage/test_console_queries.py
git commit -m "feat: add console query methods for plans and runs"
```

### Task 3: Add Application Services for Plan Creation, Run Launch, and Retry

**Files:**
- Create: `src/application/services/__init__.py`
- Create: `src/application/services/plan_service.py`
- Create: `src/application/services/run_service.py`
- Create: `tests/application/test_plan_service.py`
- Create: `tests/application/test_run_service.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/application/test_plan_service.py
from __future__ import annotations

from types import SimpleNamespace

from application.services.plan_service import PlanService


def test_create_plan_returns_persisted_plan_summary():
    fake_agent = SimpleNamespace(
        run=lambda task: SimpleNamespace(plan_id="plan-123", tasks=[]),
    )
    fake_repo = SimpleNamespace(get_plan_summary=lambda plan_id: {"plan_id": plan_id, "tasks": []})
    service = PlanService(plan_agent=fake_agent, plan_repository=fake_repo)

    result = service.create_plan(task="learn multi-agent")

    assert result["plan_id"] == "plan-123"
```

```python
# tests/application/test_run_service.py
from __future__ import annotations

from application.services.run_service import RunService


def test_start_run_creates_run_and_spawns_background_worker(monkeypatch):
    calls: list[tuple[str, str]] = []

    class _FakeThread:
        def __init__(self, *, target, args, daemon):
            self._target = target
            self._args = args
            self.daemon = daemon

        def start(self):
            self._target(*self._args)

    monkeypatch.setattr("application.services.run_service.threading.Thread", _FakeThread)

    service = RunService(
        plan_repository=type("PlanRepo", (), {"get_plan_summary": lambda self, plan_id: {"plan_id": plan_id}})(),
        plan_run_repository=type("RunRepo", (), {"create_run": lambda self, plan_id, max_workers, started_at: "run-123", "list_runs": lambda self: []})(),
        execution_repository=type("ExecRepo", (), {"load_by_task_ids": lambda self, ids: []})(),
        plan_runner=type("Runner", (), {"run_from_plan_id": lambda self, plan_id, run_id=None: calls.append((plan_id, run_id))})(),
        utc_now=lambda: "2026-04-22T00:00:00+00:00",
    )

    result = service.start_run(plan_id="plan-abc", max_workers=2)

    assert result["run_id"] == "run-123"
    assert calls == [("plan-abc", "run-123")]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `py -3 -m pytest tests/application/test_plan_service.py tests/application/test_run_service.py -v`
Expected: `FAIL` with `ModuleNotFoundError: No module named 'application.services'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/application/services/plan_service.py
from __future__ import annotations


class PlanService:
    def __init__(self, *, plan_agent, plan_repository):
        self._plan_agent = plan_agent
        self._plan_repository = plan_repository

    def create_plan(self, *, task: str) -> dict[str, object]:
        result = self._plan_agent.run(task)
        return self._plan_repository.get_plan_summary(result.plan_id)

    def list_plans(self) -> list[dict[str, object]]:
        return self._plan_repository.list_plans()

    def get_plan(self, plan_id: str) -> dict[str, object]:
        return self._plan_repository.get_plan_summary(plan_id)
```

```python
# src/application/services/run_service.py
from __future__ import annotations

import threading
from datetime import datetime, timezone


class RunService:
    def __init__(
        self,
        *,
        plan_repository,
        plan_run_repository,
        execution_repository,
        plan_runner,
        utc_now=None,
    ):
        self._plan_repository = plan_repository
        self._plan_run_repository = plan_run_repository
        self._execution_repository = execution_repository
        self._plan_runner = plan_runner
        self._utc_now = utc_now or (lambda: datetime.now(timezone.utc).isoformat())

    def start_run(self, *, plan_id: str, max_workers: int) -> dict[str, object]:
        self._plan_repository.get_plan_summary(plan_id)
        run_id = self._plan_run_repository.create_run(
            plan_id=plan_id,
            max_workers=max_workers,
            started_at=self._utc_now(),
        )
        worker = threading.Thread(
            target=self._plan_runner.run_from_plan_id,
            args=(plan_id, run_id),
            daemon=True,
        )
        worker.start()
        return {"run_id": run_id, "plan_id": plan_id, "status": "running"}

    def list_runs(self) -> list[dict[str, object]]:
        return self._plan_run_repository.list_runs()

    def get_run_detail(self, run_id: str) -> dict[str, object]:
        run_summary = self._plan_run_repository.get_run_summary(run_id)
        run_tasks = self._plan_run_repository.list_run_tasks(run_id)
        execution_ids = [item["execution_task_id"] for item in run_tasks if item["execution_task_id"]]
        executions = self._execution_repository.load_by_task_ids(execution_ids)
        return {**run_summary, "tasks": run_tasks, "executions": executions}

    def retry_run(self, run_id: str) -> dict[str, object]:
        run_summary = self._plan_run_repository.get_run_summary(run_id)
        return self.start_run(
            plan_id=run_summary["plan_id"],
            max_workers=run_summary["max_workers"],
        )

    def unsupported_control(self, run_id: str, action: str) -> dict[str, object]:
        self._plan_run_repository.get_run_summary(run_id)
        return {
            "run_id": run_id,
            "action": action,
            "status": "unsupported",
            "message": "Current execution model does not support mid-run interruption.",
        }
```

```python
# src/application/services/__init__.py
from .plan_service import PlanService
from .run_service import RunService
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `py -3 -m pytest tests/application/test_plan_service.py tests/application/test_run_service.py -v`
Expected: `PASS`

- [ ] **Step 5: Commit**

```bash
git add src/application/services/__init__.py src/application/services/plan_service.py src/application/services/run_service.py tests/application/test_plan_service.py tests/application/test_run_service.py
git commit -m "feat: add operations console application services"
```

### Task 4: Add FastAPI App and REST Endpoints for Plans and Runs

**Files:**
- Create: `src/console_api/__init__.py`
- Create: `src/console_api/app.py`
- Create: `src/console_api/schemas.py`
- Create: `src/console_api/routers/__init__.py`
- Create: `src/console_api/routers/plans.py`
- Create: `src/console_api/routers/runs.py`
- Create: `tests/api/test_plans_api.py`
- Create: `tests/api/test_runs_api.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/api/test_plans_api.py
from __future__ import annotations

from fastapi.testclient import TestClient

from console_api.app import create_app
from console_api.routers.plans import get_plan_service


def test_post_plans_returns_created_plan():
    app = create_app()
    app.dependency_overrides[get_plan_service] = lambda: type(
        "PlanService",
        (),
        {"create_plan": lambda self, task: {"plan_id": "plan-123", "source_goal": task, "tasks": []}},
    )()
    client = TestClient(app)

    response = client.post("/api/plans", json={"task": "learn multi-agent", "provider": "openai"})

    assert response.status_code == 201
    assert response.json()["plan_id"] == "plan-123"
```

```python
# tests/api/test_runs_api.py
from __future__ import annotations

from fastapi.testclient import TestClient

from console_api.app import create_app
from console_api.routers.runs import get_run_service


def test_post_runs_cancel_returns_409():
    app = create_app()
    app.dependency_overrides[get_run_service] = lambda: type(
        "RunService",
        (),
        {
            "unsupported_control": lambda self, run_id, action: {
                "run_id": run_id,
                "action": action,
                "status": "unsupported",
                "message": "Current execution model does not support mid-run interruption.",
            }
        },
    )()
    client = TestClient(app)

    response = client.post("/api/runs/run-123/cancel")

    assert response.status_code == 409
    assert response.json()["status"] == "unsupported"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `py -3 -m pytest tests/api/test_plans_api.py tests/api/test_runs_api.py -v`
Expected: `FAIL` with `ModuleNotFoundError: No module named 'console_api'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/console_api/schemas.py
from __future__ import annotations

from pydantic import BaseModel, Field


class CreatePlanRequest(BaseModel):
    task: str = Field(min_length=1)
    provider: str
    model: str | None = None
    thinking: str | None = "default"


class StartRunRequest(BaseModel):
    plan_id: str
    max_workers: int = Field(default=1, ge=1)
```

```python
# src/console_api/routers/plans.py
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status

from console_api.schemas import CreatePlanRequest

router = APIRouter(prefix="/api/plans", tags=["plans"])


def get_plan_service(request: Request):
    return request.app.state.plan_service


@router.post("", status_code=status.HTTP_201_CREATED)
def create_plan(payload: CreatePlanRequest, service=Depends(get_plan_service)):
    return service.create_plan(task=payload.task)


@router.get("")
def list_plans(service=Depends(get_plan_service)):
    return service.list_plans()


@router.get("/{plan_id}")
def get_plan(plan_id: str, service=Depends(get_plan_service)):
    return service.get_plan(plan_id)
```

```python
# src/console_api/routers/runs.py
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse

from console_api.schemas import StartRunRequest

router = APIRouter(prefix="/api/runs", tags=["runs"])


def get_run_service(request: Request):
    return request.app.state.run_service


@router.post("", status_code=status.HTTP_201_CREATED)
def start_run(payload: StartRunRequest, service=Depends(get_run_service)):
    return service.start_run(plan_id=payload.plan_id, max_workers=payload.max_workers)


@router.get("")
def list_runs(service=Depends(get_run_service)):
    return service.list_runs()


@router.get("/{run_id}")
def get_run_detail(run_id: str, service=Depends(get_run_service)):
    return service.get_run_detail(run_id)


@router.post("/{run_id}/retry", status_code=status.HTTP_201_CREATED)
def retry_run(run_id: str, service=Depends(get_run_service)):
    return service.retry_run(run_id)


@router.post("/{run_id}/pause")
def pause_run(run_id: str, service=Depends(get_run_service)):
    payload = service.unsupported_control(run_id, "pause")
    return JSONResponse(status_code=status.HTTP_409_CONFLICT, content=payload)


@router.post("/{run_id}/cancel")
def cancel_run(run_id: str, service=Depends(get_run_service)):
    payload = service.unsupported_control(run_id, "cancel")
    return JSONResponse(status_code=status.HTTP_409_CONFLICT, content=payload)
```

```python
# src/console_api/app.py
from __future__ import annotations

from fastapi import FastAPI

from console_api.routers import plans, runs


def create_app() -> FastAPI:
    app = FastAPI(title="Multi-Agent Learning Console API")
    app.state.plan_service = None
    app.state.run_service = None
    app.include_router(plans.router)
    app.include_router(runs.router)
    return app


app = create_app()
```

```python
# src/console_api/__init__.py
from .app import app, create_app
```

```python
# src/console_api/routers/__init__.py
from .plans import router as plans_router
from .runs import router as runs_router
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `py -3 -m pytest tests/api/test_plans_api.py tests/api/test_runs_api.py -v`
Expected: `PASS`

- [ ] **Step 5: Commit**

```bash
git add src/console_api/__init__.py src/console_api/app.py src/console_api/schemas.py src/console_api/routers/__init__.py src/console_api/routers/plans.py src/console_api/routers/runs.py tests/api/test_plans_api.py tests/api/test_runs_api.py
git commit -m "feat: add fastapi operations console endpoints"
```

### Task 5: Scaffold the React/Vite Console Shell

**Files:**
- Create: `console/package.json`
- Create: `console/tsconfig.json`
- Create: `console/vite.config.ts`
- Create: `console/index.html`
- Create: `console/src/main.tsx`
- Create: `console/src/App.tsx`
- Create: `console/src/api/client.ts`
- Create: `console/src/components/AppShell.tsx`
- Create: `console/src/components/StatusBadge.tsx`
- Create: `console/src/test/App.test.tsx`
- Modify: `.gitignore`

- [ ] **Step 1: Write the failing test**

```tsx
// console/src/test/App.test.tsx
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import App from "../App";

test("renders primary navigation", () => {
  render(
    <MemoryRouter>
      <App />
    </MemoryRouter>,
  );

  expect(screen.getByRole("link", { name: /dashboard/i })).toBeTruthy();
  expect(screen.getByRole("link", { name: /plans/i })).toBeTruthy();
  expect(screen.getByRole("link", { name: /runs/i })).toBeTruthy();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cmd /c npm --prefix console run test -- --run`
Expected: `FAIL` because the `console/` project does not exist yet

- [ ] **Step 3: Write minimal implementation**

```json
// console/package.json
{
  "name": "multi-agent-learning-console",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "test": "vitest"
  },
  "dependencies": {
    "react": "18.3.1",
    "react-dom": "18.3.1",
    "react-router-dom": "6.30.1"
  },
  "devDependencies": {
    "@testing-library/react": "16.3.0",
    "@types/react": "18.3.23",
    "@types/react-dom": "18.3.7",
    "@vitejs/plugin-react": "4.7.0",
    "typescript": "5.8.3",
    "vite": "7.1.3",
    "vitest": "3.2.4",
    "jsdom": "26.1.0"
  }
}
```

```json
// console/tsconfig.json
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "ESNext",
    "lib": ["DOM", "ES2020"],
    "jsx": "react-jsx",
    "moduleResolution": "Bundler",
    "strict": true,
    "noEmit": true
  },
  "include": ["src"]
}
```

```ts
// console/vite.config.ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
  },
});
```

```html
<!-- console/index.html -->
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Multi-Agent Learning Console</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

```tsx
// console/src/components/AppShell.tsx
import { PropsWithChildren } from "react";

export default function AppShell({ children }: PropsWithChildren) {
  return (
    <div>
      <header>
        <p>Multi-Agent Learning Console</p>
      </header>
      <main>{children}</main>
    </div>
  );
}
```

```tsx
// console/src/components/StatusBadge.tsx
export default function StatusBadge({ status }: { status: string }) {
  return <span>{status}</span>;
}
```

```ts
// console/src/api/client.ts
export {};
```

```tsx
// console/src/App.tsx
import { NavLink, Route, Routes } from "react-router-dom";
import AppShell from "./components/AppShell";

function Placeholder({ title }: { title: string }) {
  return <section><h1>{title}</h1></section>;
}

export default function App() {
  return (
    <AppShell>
      <nav>
        <NavLink to="/">Dashboard</NavLink>
        <NavLink to="/plans">Plans</NavLink>
        <NavLink to="/runs">Runs</NavLink>
      </nav>
      <Routes>
        <Route path="/" element={<Placeholder title="Dashboard" />} />
        <Route path="/plans" element={<Placeholder title="Plans" />} />
        <Route path="/runs" element={<Placeholder title="Runs" />} />
      </Routes>
    </AppShell>
  );
}
```

```tsx
// console/src/main.tsx
import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import App from "./App";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
);
```

```gitignore
# .gitignore
__pycache__/
*.pyc
.env
data/executions/executions.json
console/node_modules/
console/dist/
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cmd /c npm --prefix console install`
Expected: dependency installation completes

Run: `cmd /c npm --prefix console run test -- --run`
Expected: `PASS`

- [ ] **Step 5: Commit**

```bash
git add .gitignore console/package.json console/tsconfig.json console/vite.config.ts console/index.html console/src/main.tsx console/src/App.tsx console/src/api/client.ts console/src/components/AppShell.tsx console/src/components/StatusBadge.tsx console/src/test/App.test.tsx
git commit -m "feat: scaffold operations console frontend shell"
```

### Task 6: Build Dashboard, Plans, and Runs Pages with Polling

**Files:**
- Modify: `console/src/App.tsx`
- Modify: `console/src/api/client.ts`
- Create: `console/src/routes/DashboardPage.tsx`
- Create: `console/src/routes/PlansPage.tsx`
- Create: `console/src/routes/PlanDetailPage.tsx`
- Create: `console/src/routes/RunsPage.tsx`
- Modify: `console/src/test/App.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// console/src/test/App.test.tsx
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import App from "../App";

vi.mock("../api/client", () => ({
  listPlans: vi.fn().mockResolvedValue([{ plan_id: "plan-1", source_goal: "Learn scheduling" }]),
  listRuns: vi.fn().mockResolvedValue([{ run_id: "run-1", plan_id: "plan-1", status: "running", max_workers: 1 }]),
  getPlan: vi.fn().mockResolvedValue({ plan_id: "plan-1", source_goal: "Learn scheduling", tasks: [] }),
}));

test("dashboard shows recent plan and run summaries", async () => {
  render(
    <MemoryRouter initialEntries={["/"]}>
      <App />
    </MemoryRouter>,
  );

  await waitFor(() => {
    expect(screen.getByText(/learn scheduling/i)).toBeTruthy();
    expect(screen.getByText(/run-1/i)).toBeTruthy();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cmd /c npm --prefix console run test -- --run`
Expected: `FAIL` because the list pages and client helpers are not implemented

- [ ] **Step 3: Write minimal implementation**

```ts
// console/src/api/client.ts
const API_BASE = "http://127.0.0.1:8000/api";

async function readJson(path: string, init?: RequestInit) {
  const response = await fetch(`${API_BASE}${path}`, init);
  if (!response.ok) {
    throw new Error(`API request failed: ${response.status}`);
  }
  return response.json();
}

export function listPlans() {
  return readJson("/plans");
}

export function getPlan(planId: string) {
  return readJson(`/plans/${planId}`);
}

export function listRuns() {
  return readJson("/runs");
}
```

```tsx
// console/src/routes/DashboardPage.tsx
import { useEffect, useState } from "react";
import { listPlans, listRuns } from "../api/client";

export default function DashboardPage() {
  const [plans, setPlans] = useState<any[]>([]);
  const [runs, setRuns] = useState<any[]>([]);

  useEffect(() => {
    let alive = true;
    async function load() {
      const [nextPlans, nextRuns] = await Promise.all([listPlans(), listRuns()]);
      if (alive) {
        setPlans(nextPlans);
        setRuns(nextRuns);
      }
    }
    void load();
    const timer = window.setInterval(load, 5000);
    return () => {
      alive = false;
      window.clearInterval(timer);
    };
  }, []);

  return (
    <section>
      <h1>Dashboard</h1>
      <ul>{plans.map((plan) => <li key={plan.plan_id}>{plan.source_goal}</li>)}</ul>
      <ul>{runs.map((run) => <li key={run.run_id}>{run.run_id}</li>)}</ul>
    </section>
  );
}
```

```tsx
// console/src/routes/PlansPage.tsx
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listPlans } from "../api/client";

export default function PlansPage() {
  const [plans, setPlans] = useState<any[]>([]);

  useEffect(() => {
    void listPlans().then(setPlans);
  }, []);

  return (
    <section>
      <h1>Plans</h1>
      <ul>
        {plans.map((plan) => (
          <li key={plan.plan_id}>
            <Link to={`/plans/${plan.plan_id}`}>{plan.source_goal}</Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
```

```tsx
// console/src/routes/PlanDetailPage.tsx
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { getPlan } from "../api/client";

export default function PlanDetailPage() {
  const { planId = "" } = useParams();
  const [plan, setPlan] = useState<any | null>(null);

  useEffect(() => {
    void getPlan(planId).then(setPlan);
  }, [planId]);

  if (!plan) {
    return <p>Loading plan</p>;
  }

  return (
    <section>
      <h1>{plan.source_goal}</h1>
      <ul>
        {plan.tasks.map((task: any) => (
          <li key={task.task_id}>{task.title}</li>
        ))}
      </ul>
    </section>
  );
}
```

```tsx
// console/src/routes/RunsPage.tsx
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listRuns } from "../api/client";

export default function RunsPage() {
  const [runs, setRuns] = useState<any[]>([]);

  useEffect(() => {
    void listRuns().then(setRuns);
  }, []);

  return (
    <section>
      <h1>Runs</h1>
      <ul>
        {runs.map((run) => (
          <li key={run.run_id}>
            <Link to={`/runs/${run.run_id}`}>{run.run_id}</Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
```

```tsx
// console/src/App.tsx
import { NavLink, Route, Routes } from "react-router-dom";
import AppShell from "./components/AppShell";
import DashboardPage from "./routes/DashboardPage";
import PlanDetailPage from "./routes/PlanDetailPage";
import PlansPage from "./routes/PlansPage";
import RunsPage from "./routes/RunsPage";

export default function App() {
  return (
    <AppShell>
      <nav>
        <NavLink to="/">Dashboard</NavLink>
        <NavLink to="/plans">Plans</NavLink>
        <NavLink to="/runs">Runs</NavLink>
      </nav>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/plans" element={<PlansPage />} />
        <Route path="/plans/:planId" element={<PlanDetailPage />} />
        <Route path="/runs" element={<RunsPage />} />
        <Route path="/runs/:runId" element={<p>Run detail placeholder</p>} />
      </Routes>
    </AppShell>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cmd /c npm --prefix console run test -- --run`
Expected: `PASS`

- [ ] **Step 5: Commit**

```bash
git add console/src/App.tsx console/src/api/client.ts console/src/routes/DashboardPage.tsx console/src/routes/PlansPage.tsx console/src/routes/PlanDetailPage.tsx console/src/routes/RunsPage.tsx console/src/test/App.test.tsx
git commit -m "feat: add dashboard plans and runs console pages"
```

### Task 7: Build Run Detail, Retry Action, and Honest Unsupported Controls

**Files:**
- Modify: `console/src/App.tsx`
- Modify: `console/src/api/client.ts`
- Create: `console/src/routes/RunDetailPage.tsx`
- Create: `console/src/test/RunDetailPage.test.tsx`
- Modify: `tests/api/test_runs_api.py`

- [ ] **Step 1: Write the failing test**

```tsx
// console/src/test/RunDetailPage.test.tsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import RunDetailPage from "../routes/RunDetailPage";

const retryRun = vi.fn().mockResolvedValue({ run_id: "run-2" });
const getRunDetail = vi.fn().mockResolvedValue({
  run_id: "run-1",
  plan_id: "plan-1",
  status: "failed",
  tasks: [{ task_id: "task-1", status: "failed", agent_name: "ReviewAgent", execution_task_id: "exec-1" }],
  executions: [{ task_id: "exec-1", error: "review failed", output: "" }],
});

vi.mock("../api/client", () => ({
  getRunDetail,
  retryRun,
  requestRunControl: vi.fn(),
}));

test("shows retry and disabled unsupported controls", async () => {
  render(
    <MemoryRouter initialEntries={["/runs/run-1"]}>
      <Routes>
        <Route path="/runs/:runId" element={<RunDetailPage />} />
      </Routes>
    </MemoryRouter>,
  );

  await waitFor(() => expect(screen.getByText(/review failed/i)).toBeTruthy());

  fireEvent.click(screen.getByRole("button", { name: /retry run/i }));
  await waitFor(() => expect(retryRun).toHaveBeenCalledWith("run-1"));

  expect(screen.getByRole("button", { name: /pause/i })).toBeDisabled();
  expect(screen.getByRole("button", { name: /cancel/i })).toBeDisabled();
});
```

```python
# tests/api/test_runs_api.py
from __future__ import annotations

from fastapi.testclient import TestClient

from console_api.app import create_app
from console_api.routers.runs import get_run_service


def test_post_runs_retry_returns_new_run_id():
    app = create_app()
    app.dependency_overrides[get_run_service] = lambda: type(
        "RunService",
        (),
        {"retry_run": lambda self, run_id: {"run_id": "run-456", "plan_id": "plan-123", "status": "running"}},
    )()
    client = TestClient(app)

    response = client.post("/api/runs/run-123/retry")

    assert response.status_code == 201
    assert response.json()["run_id"] == "run-456"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cmd /c npm --prefix console run test -- --run`
Expected: `FAIL` because `RunDetailPage` and retry helpers are not implemented

Run: `py -3 -m pytest tests/api/test_runs_api.py -v`
Expected: `FAIL` because the retry contract is not covered yet

- [ ] **Step 3: Write minimal implementation**

```ts
// console/src/api/client.ts
export function getRunDetail(runId: string) {
  return readJson(`/runs/${runId}`);
}

export function retryRun(runId: string) {
  return readJson(`/runs/${runId}/retry`, { method: "POST" });
}

export async function requestRunControl(runId: string, action: "pause" | "cancel") {
  const response = await fetch(`${API_BASE}/runs/${runId}/${action}`, { method: "POST" });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.message ?? `Run control failed: ${response.status}`);
  }
  return payload;
}
```

```tsx
// console/src/routes/RunDetailPage.tsx
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { getRunDetail, retryRun } from "../api/client";

export default function RunDetailPage() {
  const { runId = "" } = useParams();
  const [detail, setDetail] = useState<any | null>(null);

  useEffect(() => {
    let alive = true;
    async function load() {
      const next = await getRunDetail(runId);
      if (alive) {
        setDetail(next);
      }
    }
    void load();
    const timer = window.setInterval(load, 2000);
    return () => {
      alive = false;
      window.clearInterval(timer);
    };
  }, [runId]);

  if (!detail) {
    return <p>Loading run detail</p>;
  }

  return (
    <section>
      <h1>Run {detail.run_id}</h1>
      <button onClick={() => void retryRun(runId)}>Retry run</button>
      <button disabled>Pause</button>
      <button disabled>Cancel</button>
      <ul>
        {detail.tasks.map((task: any) => (
          <li key={task.task_id}>{task.task_id} - {task.status}</li>
        ))}
      </ul>
      <ul>
        {detail.executions.map((execution: any) => (
          <li key={execution.task_id}>{execution.error || execution.output}</li>
        ))}
      </ul>
    </section>
  );
}
```

```tsx
// console/src/App.tsx
import { NavLink, Route, Routes } from "react-router-dom";
import AppShell from "./components/AppShell";
import DashboardPage from "./routes/DashboardPage";
import PlanDetailPage from "./routes/PlanDetailPage";
import PlansPage from "./routes/PlansPage";
import RunDetailPage from "./routes/RunDetailPage";
import RunsPage from "./routes/RunsPage";

export default function App() {
  return (
    <AppShell>
      <nav>
        <NavLink to="/">Dashboard</NavLink>
        <NavLink to="/plans">Plans</NavLink>
        <NavLink to="/runs">Runs</NavLink>
      </nav>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/plans" element={<PlansPage />} />
        <Route path="/plans/:planId" element={<PlanDetailPage />} />
        <Route path="/runs" element={<RunsPage />} />
        <Route path="/runs/:runId" element={<RunDetailPage />} />
      </Routes>
    </AppShell>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cmd /c npm --prefix console run test -- --run`
Expected: `PASS`

Run: `py -3 -m pytest tests/api/test_runs_api.py -v`
Expected: `PASS`

- [ ] **Step 5: Commit**

```bash
git add console/src/routes/RunDetailPage.tsx console/src/test/RunDetailPage.test.tsx console/src/api/client.ts console/src/App.tsx tests/api/test_runs_api.py
git commit -m "feat: add run detail retry and control placeholders"
```

### Task 8: Wire Real Services into the API and Update Developer Docs

**Files:**
- Modify: `src/console_api/app.py`
- Create: `tests/integration/test_console_api_flow.py`
- Modify: `README.md`

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_console_api_flow.py
from __future__ import annotations

from fastapi.testclient import TestClient

from console_api.app import create_app


def test_console_api_wires_services_on_startup(monkeypatch):
    monkeypatch.setattr(
        "console_api.app.build_service_context",
        lambda **_: object(),
    )
    monkeypatch.setattr(
        "console_api.app._build_services",
        lambda ctx: {
            "plan_service": type("PlanService", (), {"list_plans": lambda self: [], "get_plan": lambda self, plan_id: {"plan_id": plan_id}, "create_plan": lambda self, task: {"plan_id": "plan-1", "source_goal": task, "tasks": []}})(),
            "run_service": type("RunService", (), {"list_runs": lambda self: [], "get_run_detail": lambda self, run_id: {"run_id": run_id, "tasks": [], "executions": []}, "start_run": lambda self, plan_id, max_workers: {"run_id": "run-1", "plan_id": plan_id, "status": "running"}, "retry_run": lambda self, run_id: {"run_id": "run-2", "plan_id": "plan-1", "status": "running"}, "unsupported_control": lambda self, run_id, action: {"run_id": run_id, "action": action, "status": "unsupported", "message": "Current execution model does not support mid-run interruption."}})(),
        },
    )

    with TestClient(create_app()) as client:
        response = client.get("/api/runs")

    assert response.status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -3 -m pytest tests/integration/test_console_api_flow.py -v`
Expected: `FAIL` because `create_app()` does not wire real services on startup yet

- [ ] **Step 3: Write minimal implementation**

```python
# src/console_api/app.py
from __future__ import annotations

from fastapi import FastAPI

from agents.planner_agent import PlannerAgent
from application.context import build_service_context
from application.services import PlanService, RunService
from console_api.routers import plans, runs
from main import _build_dispatcher, _build_plan_runner, _build_worker_agents
from storage.execution_store import ExecutionStore
from storage.repositories.execution_repository import ExecutionRepository
from storage.repositories.plan_repository import PlanRepository
from storage.repositories.plan_run_repository import PlanRunRepository


def _build_services(ctx) -> dict[str, object]:
    plan_repository = PlanRepository(session_factory=ctx.session_factory)
    plan_run_repository = PlanRunRepository(session_factory=ctx.session_factory)
    execution_repository = ExecutionRepository(session_factory=ctx.session_factory)
    store = ExecutionStore(database_url=ctx.database_url, session_factory=ctx.session_factory)
    plan_agent = PlannerAgent(
        provider_config=ctx.provider_config,
        thinking_mode=ctx.thinking_mode,
        plan_repository=plan_repository,
    )
    analysis_agent, implementation_agent, review_agent = _build_worker_agents(
        store=store,
        provider_config=ctx.provider_config,
        thinking_mode=ctx.thinking_mode,
    )
    dispatcher = _build_dispatcher(
        analysis_agent=analysis_agent,
        implementation_agent=implementation_agent,
        review_agent=review_agent,
    )
    plan_runner = _build_plan_runner(
        dispatcher=dispatcher,
        max_workers=1,
        plan_repository=plan_repository,
        plan_run_repository=plan_run_repository,
    )
    return {
        "plan_service": PlanService(plan_agent=plan_agent, plan_repository=plan_repository),
        "run_service": RunService(
            plan_repository=plan_repository,
            plan_run_repository=plan_run_repository,
            execution_repository=execution_repository,
            plan_runner=plan_runner,
        ),
    }


def create_app() -> FastAPI:
    app = FastAPI(title="Multi-Agent Learning Console API")
    app.state.plan_service = None
    app.state.run_service = None
    app.include_router(plans.router)
    app.include_router(runs.router)

    @app.on_event("startup")
    def _wire_dependencies() -> None:
        ctx = build_service_context(
            provider="openai",
            model=None,
            base_url=None,
            thinking="default",
            database_url=None,
            runtime_config="config/runtime.json",
        )
        services = _build_services(ctx)
        app.state.plan_service = services["plan_service"]
        app.state.run_service = services["run_service"]

    return app


app = create_app()
```

```md
# README.md
## Operations Console

Start the API:

    set PYTHONPATH=src
    py -3 -m uvicorn console_api.app:app --reload --port 8000

Start the UI:

    cmd /c npm --prefix console install
    cmd /c npm --prefix console run dev

The console supports:

- create plan
- start run
- inspect runs and task state
- retry a run as a new run
- view pause/cancel as unsupported control placeholders
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -3 -m pytest tests/integration/test_console_api_flow.py -v`
Expected: `PASS`

Run: `py -3 -m pytest tests/application tests/api tests/storage/test_console_queries.py tests/integration/test_console_api_flow.py -v`
Expected: all backend console tests `PASS`

Run: `cmd /c npm --prefix console run build`
Expected: frontend build completes successfully

- [ ] **Step 5: Commit**

```bash
git add README.md src/console_api/app.py tests/integration/test_console_api_flow.py
git commit -m "feat: wire operations console services and docs"
```

---

## Global Verification Commands

Run: `py -3 -m pytest tests/application tests/api tests/storage/test_console_queries.py tests/integration/test_console_api_flow.py -v`
Expected: backend console tests `PASS`

Run: `cmd /c npm --prefix console run test -- --run`
Expected: frontend tests `PASS`

Run: `cmd /c npm --prefix console run build`
Expected: frontend build `PASS`

Run: `py -3 -m compileall src`
Expected: compile success without syntax errors

---

## Rollback Plan

- Revert by commit granularity from Task 8 back to Task 1 using `git revert <sha>`.
- If the frontend scaffold is not wanted, revert Tasks 5-7 only; backend API work remains independently useful.
- If API startup wiring causes problems, revert Task 8 first; Tasks 1-7 still leave isolated, testable units.

---

## Notes for Implementers

- Keep CLI behavior intact. The console is additive, not a replacement.
- Do not imply that pause/cancel actually interrupt running tasks during V1.
- Keep polling simple and explicit. Do not add WebSocket or SSE in this plan.
- Prefer small service classes and small route modules over a single large web layer.
