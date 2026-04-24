from __future__ import annotations

from application.services.run_service import RunService


def test_start_run_uses_selected_profile_and_reuses_created_run_id(monkeypatch):
    calls: list[tuple[str, str, str, int]] = []

    class _FakeThread:
        def __init__(self, *, target, args, daemon):
            self._target = target
            self._args = args
            self.daemon = daemon

        def start(self):
            self._target(*self._args)

    monkeypatch.setattr("application.services.run_service.threading.Thread", _FakeThread)

    service = RunService(
        model_profile_service=type(
            "ProfileService",
            (),
            {
                "resolve_runtime_profile": lambda self, profile_id: type(
                    "Profile",
                    (),
                    {
                        "profile_id": profile_id,
                        "provider": "openai",
                        "model_name": "gpt-5-mini",
                        "api_key": "sk-openai-1234",
                        "base_url": None,
                        "thinking_mode": "default",
                    },
                )()
            },
        )(),
        plan_repository=type(
            "PlanRepo",
            (),
            {
                "get_plan_summary": lambda self, plan_id: {
                    "plan_id": plan_id,
                    "model_profile_id": "profile-plan",
                }
            },
        )(),
        plan_run_repository=type(
            "RunRepo",
            (),
            {
                "create_run": lambda self, plan_id, model_profile_id, max_workers, started_at: "run-123",
                "get_run_summary": lambda self, run_id: {
                    "run_id": run_id,
                    "plan_id": "plan-1",
                    "model_profile_id": "profile-2",
                    "max_workers": 2,
                },
                "list_runs": lambda self: [],
            },
        )(),
        execution_repository=type(
            "ExecRepo",
            (),
            {"load_by_task_ids": lambda self, ids: []},
        )(),
        plan_runner_factory=lambda profile, max_workers: type(
            "Runner",
            (),
            {
                "run_from_plan_id": lambda self, plan_id, run_id=None: calls.append(
                    (profile.profile_id, plan_id, run_id, max_workers)
                )
            },
        )(),
        utc_now=lambda: "2026-04-23T00:00:00+00:00",
    )

    result = service.start_run(plan_id="plan-1", profile_id="profile-2", max_workers=2)

    assert result["run_id"] == "run-123"
    assert calls == [("profile-2", "plan-1", "run-123", 2)]


def test_get_run_detail_joins_tasks_and_executions():
    service = RunService(
        model_profile_service=object(),
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
        plan_runner_factory=object(),
    )

    result = service.get_run_detail("run-123")

    assert result["run_id"] == "run-123"
    assert result["tasks"][0]["execution_task_id"] == "exec-1"
    assert result["executions"][0]["task_id"] == "exec-1"


def test_retry_run_uses_existing_plan_settings(monkeypatch):
    start_run_calls: list[dict[str, object]] = []
    service = RunService(
        model_profile_service=object(),
        plan_repository=object(),
        plan_run_repository=type(
            "RunRepo",
            (),
            {
                "get_run_summary": lambda self, run_id: {
                    "run_id": run_id,
                    "plan_id": "plan-1",
                    "model_profile_id": "profile-2",
                    "max_workers": 3,
                }
            },
        )(),
        execution_repository=object(),
        plan_runner_factory=object(),
    )
    monkeypatch.setattr(
        service,
        "start_run",
        lambda *, plan_id, profile_id, max_workers: start_run_calls.append(
            {
                "plan_id": plan_id,
                "profile_id": profile_id,
                "max_workers": max_workers,
            }
        )
        or {"run_id": "run-456", "plan_id": plan_id, "status": "running"},
    )

    result = service.retry_run("run-123")

    assert result["run_id"] == "run-456"
    assert start_run_calls == [
        {"plan_id": "plan-1", "profile_id": "profile-2", "max_workers": 3}
    ]
