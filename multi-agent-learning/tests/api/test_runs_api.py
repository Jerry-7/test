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


def test_post_runs_retry_returns_new_run_id():
    app = create_app()
    app.dependency_overrides[get_run_service] = lambda: type(
        "RunService",
        (),
        {
            "retry_run": lambda self, run_id: {
                "run_id": "run-456",
                "plan_id": "plan-123",
                "status": "running",
            }
        },
    )()
    client = TestClient(app)

    response = client.post("/api/runs/run-123/retry")

    assert response.status_code == 201
    assert response.json()["run_id"] == "run-456"
