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
        model_profile_id: str,
        provider: str,
        model_name: str,
        thinking_mode: str,
        tasks: list[PlanTask],
    ) -> str:
        with self._session_factory() as session:
            plan = PlanRow(
                model_profile_id=UUID(model_profile_id),
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

    def list_plans(self, limit: int = 20) -> list[dict[str, object]]:
        with self._session_factory() as session:
            rows = (
                session.query(PlanRow)
                .order_by(PlanRow.created_at.desc())
                .limit(limit)
                .all()
            )
            return [
                {
                    "plan_id": str(row.plan_id),
                    "model_profile_id": str(row.model_profile_id),
                    "source_goal": row.source_goal,
                    "provider": row.provider,
                    "model_name": row.model_name,
                    "thinking_mode": row.thinking_mode,
                    "created_at": row.created_at.isoformat(),
                }
                for row in rows
            ]

    def get_plan_summary(self, plan_id: str) -> dict[str, object]:
        with self._session_factory() as session:
            plan_row = (
                session.query(PlanRow)
                .filter(PlanRow.plan_id == UUID(plan_id))
                .one()
            )
            task_rows = (
                session.query(PlanTaskRow)
                .filter(PlanTaskRow.plan_id == UUID(plan_id))
                .order_by(PlanTaskRow.priority.asc(), PlanTaskRow.task_id.asc())
                .all()
            )
            return {
                "plan_id": str(plan_row.plan_id),
                "model_profile_id": str(plan_row.model_profile_id),
                "source_goal": plan_row.source_goal,
                "provider": plan_row.provider,
                "model_name": plan_row.model_name,
                "thinking_mode": plan_row.thinking_mode,
                "created_at": plan_row.created_at.isoformat(),
                "tasks": [
                    {
                        "task_id": row.task_id,
                        "title": row.title,
                        "type": row.type,
                        "priority": row.priority,
                        "status": row.status,
                        "depends_on": list(row.depends_on),
                    }
                    for row in task_rows
                ],
            }
