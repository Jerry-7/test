from __future__ import annotations

from application.services.plan_service import PlanService


def test_create_plan_resolves_runtime_profile_before_building_planner():
    captured: dict[str, object] = {}

    service = PlanService(
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
        planner_agent_factory=lambda profile: type(
            "PlannerAgent",
            (),
            {
                "run": lambda self, task: captured.update(
                    {"provider": profile.provider, "task": task}
                )
                or type(
                    "PlannerRunResult",
                    (),
                    {"plan_id": "plan-123"},
                )()
            },
        )(),
        plan_repository=type(
            "PlanRepository",
            (),
            {
                "get_plan_summary": lambda self, plan_id: {
                    "plan_id": plan_id,
                    "model_profile_id": "profile-1",
                    "tasks": [],
                }
            },
        )(),
    )

    result = service.create_plan(task="learn console", profile_id="profile-1")

    assert result["plan_id"] == "plan-123"
    assert captured == {"provider": "openai", "task": "learn console"}
