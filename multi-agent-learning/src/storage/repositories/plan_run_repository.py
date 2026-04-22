from __future__ import annotations

from datetime import datetime
from typing import Callable
from uuid import UUID

from models.plan_constants import TASK_STATUS_RUNNING
from storage.db.models import PlanRunRow, PlanRunTaskRow


class PlanRunRepository:
    def __init__(self, session_factory: Callable[[], object]):
        self._session_factory = session_factory

    def create_run(
        self,
        plan_id: str,
        max_workers: int,
        started_at: str,
    ) -> str:
        if max_workers <= 0:
            raise ValueError("max_workers must be > 0.")

        started_at_dt = self._parse_datetime_or_raise(
            value=started_at,
            field_name="started_at",
        )
        with self._session_factory() as session:
            row = PlanRunRow(
                plan_id=UUID(plan_id),
                max_workers=max_workers,
                status=TASK_STATUS_RUNNING,
                started_at=started_at_dt,
                ended_at=None,
            )
            session.add(row)
            session.commit()
            return str(row.run_id)

    def upsert_task_state(
        self,
        run_id: str,
        task_id: str,
        agent_name: str,
        status: str,
        execution_task_id: str | None,
        state_snapshot: dict,
    ) -> None:
        run_uuid = UUID(run_id)
        with self._session_factory() as session:
            row = (
                session.query(PlanRunTaskRow)
                .filter(
                    PlanRunTaskRow.run_id == run_uuid,
                    PlanRunTaskRow.task_id == task_id,
                )
                .one_or_none()
            )
            if row is None:
                row = PlanRunTaskRow(
                    run_id=run_uuid,
                    task_id=task_id,
                    agent_name=agent_name,
                    status=status,
                    execution_task_id=execution_task_id,
                    state_snapshot=dict(state_snapshot),
                )
                session.add(row)
            else:
                row.agent_name = agent_name
                row.status = status
                row.execution_task_id = execution_task_id
                row.state_snapshot = dict(state_snapshot)
            session.commit()

    def finish_run(self, run_id: str, status: str, ended_at: str) -> None:
        ended_at_dt = self._parse_datetime_or_raise(
            value=ended_at,
            field_name="ended_at",
        )
        with self._session_factory() as session:
            row = (
                session.query(PlanRunRow)
                .filter(PlanRunRow.run_id == UUID(run_id))
                .one()
            )
            row.status = status
            row.ended_at = ended_at_dt
            session.commit()

    def get_run(self, run_id: str) -> dict[str, object]:
        with self._session_factory() as session:
            row = (
                session.query(PlanRunRow)
                .filter(PlanRunRow.run_id == UUID(run_id))
                .one()
            )
            return {
                "run_id": str(row.run_id),
                "plan_id": str(row.plan_id),
                "max_workers": row.max_workers,
                "status": row.status,
                "started_at": row.started_at.isoformat(),
                "ended_at": row.ended_at.isoformat() if row.ended_at else None,
            }

    def _parse_datetime_or_raise(self, value: str, field_name: str) -> datetime:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError(f"{field_name} cannot be empty.")
        parsed = datetime.fromisoformat(cleaned)
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError(f"{field_name} must include timezone offset.")
        return parsed
