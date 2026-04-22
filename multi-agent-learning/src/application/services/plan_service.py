from __future__ import annotations


class PlanService:
    def __init__(self, *, plan_agent, plan_repository):
        self._plan_agent = plan_agent
        self._plan_repository = plan_repository

    def create_plan(self, *, task: str) -> dict[str, object]:
        result = self._plan_agent.run(task)
        return self._plan_repository.get_plan_summary(result.plan_id)

    def list_plans(self) -> list[dict[str, object]]:
        return self._plan_repository.list_plans()

    def get_plan(self, plan_id: str) -> dict[str, object]:
        return self._plan_repository.get_plan_summary(plan_id)

