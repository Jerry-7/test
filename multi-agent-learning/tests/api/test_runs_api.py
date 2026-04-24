from __future__ import annotations

from fastapi.testclient import TestClient

from console_api.app import create_app
from console_api.routers.runs import get_run_service


def test_post_runs_requires_profile_id():
    app = create_app()
    app.dependency_overrides[get_run_service] = lambda: type(
        "RunService",
        (),
        {
            "start_run": lambda self, plan_id, profile_id, max_workers: {
                "run_id": "run-456",
                "plan_id": plan_id,
                "model_profile_id": profile_id,
                "status": "running",
            }
        },
    )()
    client = TestClient(app)

    response = client.post(
        "/api/runs",
        json={"plan_id": "plan-1", "profile_id": "profile-1", "max_workers": 1},
    )

    assert response.status_code == 201
    assert response.json()["model_profile_id"] == "profile-1"


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


def test_post_runs_retry_returns_new_run_id():
    app = create_app()
    app.dependency_overrides[get_run_service] = lambda: type(
        "RunService",
        (),
        {
            "retry_run": lambda self, run_id, profile_id=None: {
                "run_id": "run-789",
                "plan_id": "plan-1",
                "model_profile_id": profile_id or "profile-1",
                "status": "running",
            }
        },
    )()
    client = TestClient(app)

    response = client.post(
        "/api/runs/run-123/retry",
        json={"profile_id": "profile-2"},
    )

    assert response.status_code == 201
    assert response.json()["run_id"] == "run-789"
    assert response.json()["model_profile_id"] == "profile-2"
