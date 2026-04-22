from __future__ import annotations

from datetime import datetime
from typing import Callable

from models.task import TaskExecution, TaskExecutionRecord
from storage.db.models import ExecutionRow


class ExecutionRepository:
    def __init__(self, session_factory: Callable[[], object]):
        self._session_factory = session_factory

    def append(self, execution: TaskExecution) -> None:
        started_at = self._parse_datetime_or_raise(
            value=execution.started_at,
            field_name="started_at",
        )
        ended_at = self._parse_datetime_or_raise(
            value=execution.ended_at,
            field_name="ended_at",
        )
        if ended_at < started_at:
            raise ValueError("TaskExecution.ended_at must be >= started_at.")

        with self._session_factory() as session:
            row = ExecutionRow(
                task_id=execution.task_id,
                task_text=execution.task_text,
                agent_name=execution.agent_name,
                status=execution.status,
                output=execution.output,
                error=execution.error,
                traceback=execution.traceback,
                started_at=started_at,
                ended_at=ended_at,
                metadata_json=execution.metadata,
            )
            session.add(row)
            session.commit()

    def load_all(self) -> list[TaskExecutionRecord]:
        with self._session_factory() as session:
            rows = (
                session.query(ExecutionRow)
                .order_by(ExecutionRow.created_at.asc())
                .all()
            )
            return [
                {
                    "task_id": row.task_id,
                    "task_text": row.task_text,
                    "agent_name": row.agent_name,
                    "status": row.status,
                    "output": row.output,
                    "error": row.error,
                    "traceback": row.traceback,
                    "started_at": row.started_at.isoformat(),
                    "ended_at": row.ended_at.isoformat(),
                    "metadata": row.metadata_json,
                }
                for row in rows
            ]

    def _parse_datetime_or_raise(self, value: str, field_name: str) -> datetime:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError(f"TaskExecution.{field_name} cannot be empty.")
        parsed = datetime.fromisoformat(cleaned)
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError(
                f"TaskExecution.{field_name} must include timezone offset."
            )
        return parsed
