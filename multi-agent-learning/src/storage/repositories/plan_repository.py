from __future__ import annotations

from typing import Callable
from uuid import UUID

from models.plan_task import PlanTask
from storage.db.models import PlanRow, PlanTaskRow


class PlanRepository:
    def __init__(self, session_factory: Callable[[], object]):
        self._session_factory = session_factory

    def save_plan(
        self,
        goal: str,
        provider: str,
        model_name: str,
        thinking_mode: str,
        tasks: list[PlanTask],
    ) -> str:
        with self._session_factory() as session:
            plan = PlanRow(
                source_goal=goal,
                provider=provider,
                model_name=model_name,
                thinking_mode=thinking_mode,
            )
            session.add(plan)
            session.flush()

            for item in tasks:
                session.add(
                    PlanTaskRow(
                        plan_id=plan.plan_id,
                        task_id=item.id,
                        title=item.title,
                        type=item.type,
                        priority=item.priority,
                        status=item.status,
                        depends_on=item.depends_on,
                    )
                )

            session.commit()
            return str(plan.plan_id)

    def load_plan(self, plan_id: str) -> list[PlanTask]:
        with self._session_factory() as session:
            rows = (
                session.query(PlanTaskRow)
                .filter(PlanTaskRow.plan_id == UUID(plan_id))
                .order_by(PlanTaskRow.priority.asc(), PlanTaskRow.task_id.asc())
                .all()
            )

            return [
                PlanTask(
                    id=row.task_id,
                    title=row.title,
                    type=row.type,
                    depends_on=row.depends_on,
                    status=row.status,
                    priority=row.priority,
                )
                for row in rows
            ]
