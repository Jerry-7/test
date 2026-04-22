from __future__ import annotations

import os
from typing import Callable

from models.task import TaskExecution, TaskExecutionRecord
from storage.db.session import create_session_factory
from storage.repositories.execution_repository import ExecutionRepository


class ExecutionStore:
    """TaskExecution 持久化存储（PostgreSQL）。"""

    def __init__(
        self,
        database_url: str | None = None,
        *,
        repository: ExecutionRepository | None = None,
        session_factory: Callable[[], object] | None = None,
    ):
        if repository is not None:
            self._repository = repository
            return

        if session_factory is not None:
            self._repository = ExecutionRepository(
                session_factory=session_factory
            )
            return

        resolved_database_url = self._resolve_database_url(database_url)
        resolved_session_factory = create_session_factory(resolved_database_url)
        self._repository = ExecutionRepository(
            session_factory=resolved_session_factory
        )

    def append(self, execution: TaskExecution) -> None:
        self._repository.append(execution)

    def load_all(self) -> list[TaskExecutionRecord]:
        return self._repository.load_all()

    def _resolve_database_url(self, database_url: str | None) -> str:
        cleaned = (database_url or "").strip()
        if "://" in cleaned:
            return cleaned

        env_database_url = os.getenv("DATABASE_URL", "").strip()
        if env_database_url:
            return env_database_url

        raise ValueError(
            "ExecutionStore now requires a database URL. "
            "Please pass --database-url or set DATABASE_URL."
        )
