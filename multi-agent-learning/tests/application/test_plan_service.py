from __future__ import annotations

from types import SimpleNamespace

from application.services.plan_service import PlanService


def test_create_plan_returns_persisted_plan_summary():
    fake_agent = SimpleNamespace(
        run=lambda task: SimpleNamespace(plan_id="plan-123", tasks=[]),
    )
    fake_repo = SimpleNamespace(
        get_plan_summary=lambda plan_id: {"plan_id": plan_id, "tasks": []}
    )
    service = PlanService(plan_agent=fake_agent, plan_repository=fake_repo)

    result = service.create_plan(task="learn multi-agent")

    assert result["plan_id"] == "plan-123"
