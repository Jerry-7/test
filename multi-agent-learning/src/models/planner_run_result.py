from __future__ import annotations

from dataclasses import dataclass

from models.plan_task import PlanTask


@dataclass(frozen=True)
class PlannerRunResult:
    plan_id: str
    tasks: tuple[PlanTask, ...]
