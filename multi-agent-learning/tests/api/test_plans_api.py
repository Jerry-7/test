from __future__ import annotations

from fastapi.testclient import TestClient

from console_api.app import create_app
from console_api.routers.plans import get_plan_service


def test_post_plans_returns_created_plan():
    app = create_app()
    app.dependency_overrides[get_plan_service] = lambda: type(
        "PlanService",
        (),
        {
            "create_plan": lambda self, task: {
                "plan_id": "plan-123",
                "source_goal": task,
                "tasks": [],
            }
        },
    )()
    client = TestClient(app)

    response = client.post(
        "/api/plans",
        json={"task": "learn multi-agent", "provider": "openai"},
    )

    assert response.status_code == 201
    assert response.json()["plan_id"] == "plan-123"
