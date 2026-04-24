from __future__ import annotations


class PlanService:
    def __init__(self, *, model_profile_service, planner_agent_factory, plan_repository):
        self._model_profile_service = model_profile_service
        self._planner_agent_factory = planner_agent_factory
        self._plan_repository = plan_repository

    def create_plan(self, *, task: str, profile_id: str) -> dict[str, object]:
        runtime_profile = self._model_profile_service.resolve_runtime_profile(profile_id)
        planner_agent = self._planner_agent_factory(runtime_profile)
        result = planner_agent.run(task)
        return self._plan_repository.get_plan_summary(result.plan_id)

    def list_plans(self) -> list[dict[str, object]]:
        return self._plan_repository.list_plans()

    def get_plan(self, plan_id: str) -> dict[str, object]:
        return self._plan_repository.get_plan_summary(plan_id)
