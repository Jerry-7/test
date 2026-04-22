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
        plan_repository=type(
            "PlanRepo",
            (),
            {"get_plan_summary": lambda self, plan_id: {"plan_id": plan_id}},
        )(),
        plan_run_repository=type(
            "RunRepo",
            (),
            {
                "create_run": lambda self, plan_id, max_workers, started_at: "run-123",
                "list_runs": lambda self: [],
            },
        )(),
        execution_repository=type(
            "ExecRepo",
            (),
            {"load_by_task_ids": lambda self, ids: []},
        )(),
        plan_runner=type(
            "Runner",
            (),
            {"run_from_plan_id": lambda self, plan_id, run_id=None: calls.append((plan_id, run_id))},
        )(),
        utc_now=lambda: "2026-04-22T00:00:00+00:00",
    )

    result = service.start_run(plan_id="plan-abc", max_workers=2)

    assert result["run_id"] == "run-123"
    assert calls == [("plan-abc", "run-123")]


def test_get_run_detail_joins_tasks_and_executions():
    service = RunService(
        plan_repository=object(),
        plan_run_repository=type(
            "RunRepo",
            (),
            {
                "get_run_summary": lambda self, run_id: {"run_id": run_id, "plan_id": "plan-1"},
                "list_run_tasks": lambda self, run_id: [
                    {
                        "task_id": "task-1",
                        "status": "failed",
                        "execution_task_id": "exec-1",
                    }
                ],
            },
        )(),
        execution_repository=type(
            "ExecRepo",
            (),
            {"load_by_task_ids": lambda self, ids: [{"task_id": ids[0], "error": "boom"}]},
        )(),
        plan_runner=object(),
    )

    result = service.get_run_detail("run-123")

    assert result["run_id"] == "run-123"
    assert result["tasks"][0]["execution_task_id"] == "exec-1"
    assert result["executions"][0]["task_id"] == "exec-1"


def test_retry_run_uses_existing_plan_settings(monkeypatch):
    start_run_calls: list[dict[str, object]] = []
    service = RunService(
        plan_repository=object(),
        plan_run_repository=type(
            "RunRepo",
            (),
            {
                "get_run_summary": lambda self, run_id: {
                    "run_id": run_id,
                    "plan_id": "plan-1",
                    "max_workers": 3,
                }
            },
        )(),
        execution_repository=object(),
        plan_runner=object(),
    )
    monkeypatch.setattr(
        service,
        "start_run",
        lambda *, plan_id, max_workers: start_run_calls.append(
            {"plan_id": plan_id, "max_workers": max_workers}
        )
        or {"run_id": "run-456", "plan_id": plan_id, "status": "running"},
    )

    result = service.retry_run("run-123")

    assert result["run_id"] == "run-456"
    assert start_run_calls == [{"plan_id": "plan-1", "max_workers": 3}]
