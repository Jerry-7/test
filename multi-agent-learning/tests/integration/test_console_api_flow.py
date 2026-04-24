from __future__ import annotations

from fastapi.testclient import TestClient

from console_api.app import create_app


def test_console_api_wires_services_on_startup(monkeypatch):
    monkeypatch.setattr(
        "console_api.app.build_app_context",
        lambda **_: object(),
    )
    monkeypatch.setattr(
        "console_api.app._build_services",
        lambda ctx: {
            "model_profile_service": object(),
            "plan_service": type(
                "PlanService",
                (),
                {
                    "list_plans": lambda self: [],
                    "get_plan": lambda self, plan_id: {"plan_id": plan_id},
                    "create_plan": lambda self, task, profile_id: {
                        "plan_id": "plan-1",
                        "source_goal": task,
                        "model_profile_id": profile_id,
                        "tasks": [],
                    },
                },
            )(),
            "run_service": type(
                "RunService",
                (),
                {
                    "list_runs": lambda self: [],
                    "get_run_detail": lambda self, run_id: {
                        "run_id": run_id,
                        "tasks": [],
                        "executions": [],
                    },
                    "start_run": lambda self, plan_id, profile_id, max_workers: {
                        "run_id": "run-1",
                        "plan_id": plan_id,
                        "model_profile_id": profile_id,
                        "status": "running",
                    },
                    "retry_run": lambda self, run_id, profile_id=None: {
                        "run_id": "run-2",
                        "plan_id": "plan-1",
                        "model_profile_id": profile_id or "profile-1",
                        "status": "running",
                    },
                    "unsupported_control": lambda self, run_id, action: {
                        "run_id": run_id,
                        "action": action,
                        "status": "unsupported",
                        "message": "Current execution model does not support mid-run interruption.",
                    },
                },
            )(),
        },
    )

    with TestClient(create_app()) as client:
        response = client.get("/api/runs")

    assert response.status_code == 200
