from __future__ import annotations

from typing import Iterable


class Dispatcher:
    """Map plan task types to agent names."""

    DEFAULT_TYPE_TO_AGENT = {
        "analysis": "PlannerAgent",
        "planning": "PlannerAgent",
        "design": "BasicAgent",
        "research": "BasicAgent",
        "writing": "BasicAgent",
        "review": "BasicAgent",
    }

    def __init__(self, type_to_agent: dict[str, str] | None = None):
        self.type_to_agent = dict(self.DEFAULT_TYPE_TO_AGENT)
        if type_to_agent:
            self.type_to_agent.update(type_to_agent)

    def dispatch(self, plan: Iterable[dict]) -> list[dict]:
        assignments: list[dict] = []
        for task in plan:
            task_type = str(task.get("type", "")).strip()
            assignments.append(
                {
                    "task_id": task.get("id", ""),
                    "task_type": task_type,
                    "agent_name": self._resolve_agent_name(task_type),
                    "depends_on": list(task.get("depends_on", [])),
                }
            )
        return assignments

    def _resolve_agent_name(self, task_type: str) -> str:
        return self.type_to_agent.get(task_type, "BasicAgent")
