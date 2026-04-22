from __future__ import annotations

import argparse
from types import SimpleNamespace

import main


def test_build_parser_accepts_database_url_and_plan_id():
    parser = main.build_parser()

    args = parser.parse_args(
        [
            "--agent",
            "run-plan",
            "--database-url",
            "postgresql://example",
            "--plan-id",
            "plan-123",
        ]
    )

    assert args.database_url == "postgresql://example"
    assert args.plan_id == "plan-123"


def test_run_plan_uses_plan_id_only():
    class _FakeRunner:
        def __init__(self):
            self.called_plan_id: str | None = None
            self.called_path: str | None = None

        def run_from_plan_id(self, plan_id: str):
            self.called_plan_id = plan_id
            return ["ok"]

        def run_from_path(self, path: str):
            self.called_path = path
            raise AssertionError("run_from_path should not be used by run-plan.")

    runner = _FakeRunner()
    runtime = main.RuntimeContext(
        provider_config=SimpleNamespace(),
        plan_runner=runner,
    )
    args = argparse.Namespace(plan_id="plan-123", plan_path="legacy.json")

    result = main._run_plan(runtime, args)

    assert result == ["ok"]
    assert runner.called_plan_id == "plan-123"
    assert runner.called_path is None


def test_build_runtime_injects_db_repositories_for_run_plan(monkeypatch):
    created: dict[str, object] = {}
    session_factory_calls: list[str] = []

    monkeypatch.setattr(
        main,
        "resolve_provider_config",
        lambda **_: SimpleNamespace(provider="openai", model_name="gpt-x"),
    )

    class _FakeExecutionStore:
        def __init__(self, database_url: str, session_factory=None):
            created["execution_store_url"] = database_url
            created["execution_store_session_factory"] = session_factory

    class _FakePlanRepository:
        def __init__(self, session_factory):
            self.session_factory = session_factory
            created["plan_repository"] = self

    class _FakePlanRunRepository:
        def __init__(self, session_factory):
            self.session_factory = session_factory
            created["plan_run_repository"] = self

    monkeypatch.setattr(main, "ExecutionStore", _FakeExecutionStore)
    monkeypatch.setattr(
        main,
        "create_session_factory",
        lambda database_url: (
            session_factory_calls.append(database_url)
            or f"session-factory:{database_url}"
        ),
    )
    monkeypatch.setattr(main, "PlanRepository", _FakePlanRepository)
    monkeypatch.setattr(main, "PlanRunRepository", _FakePlanRunRepository)
    monkeypatch.setattr(
        main,
        "_build_worker_agents",
        lambda store, provider_config, thinking_mode: ("a", "i", "r"),
    )
    monkeypatch.setattr(
        main,
        "_build_dispatcher",
        lambda analysis_agent, implementation_agent, review_agent: "dispatcher",
    )

    def _fake_build_plan_runner(
        *,
        dispatcher,
        max_workers,
        plan_repository,
        plan_run_repository,
    ):
        created["plan_runner_args"] = {
            "dispatcher": dispatcher,
            "max_workers": max_workers,
            "plan_repository": plan_repository,
            "plan_run_repository": plan_run_repository,
        }
        return "plan-runner"

    monkeypatch.setattr(main, "_build_plan_runner", _fake_build_plan_runner)

    args = argparse.Namespace(
        task=None,
        agent="run-plan",
        provider="openai",
        model=None,
        base_url=None,
        thinking="default",
        database_url="postgresql://db.example/app",
        store_path="ignored-by-db-contract",
        plan_path="ignored-in-run-plan",
        plan_id="plan-123",
        max_workers=3,
    )

    runtime = main.build_runtime(args)

    assert runtime.plan_runner == "plan-runner"
    assert created["execution_store_url"] == "postgresql://db.example/app"
    assert created["plan_runner_args"] == {
        "dispatcher": "dispatcher",
        "max_workers": 3,
        "plan_repository": created["plan_repository"],
        "plan_run_repository": created["plan_run_repository"],
    }
    assert created["plan_repository"].session_factory == (
        "session-factory:postgresql://db.example/app"
    )
    assert created["plan_run_repository"].session_factory == (
        "session-factory:postgresql://db.example/app"
    )
    assert session_factory_calls == ["postgresql://db.example/app"]
