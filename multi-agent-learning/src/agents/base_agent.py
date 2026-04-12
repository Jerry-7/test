from __future__ import annotations

from abc import ABC, abstractmethod
import traceback
from typing import Any

from models.task import TaskExecution
from storage.execution_store import ExecutionStore
from utils.time_utils import utc_now_iso


class BaseAgent(ABC):
    def __init__(self, name: str, store: ExecutionStore):
        self.name = name
        self.store = store

    def run(self, task_text: str) -> TaskExecution:
        execution = TaskExecution.create(task_text=task_text, agent_name=self.name)
        execution.started_at = utc_now_iso()
        execution.status = "running"
        execution.metadata.update(self._build_execution_metadata())

        try:
            output, metadata = self._handle_task(task_text)
            execution.output = output
            execution.metadata.update(metadata)
            execution.status = "completed"
        except Exception as exc:
            execution.status = "failed"
            execution.error = f"{type(exc).__name__}: {exc}"
            execution.output = ""
            execution.traceback = traceback.format_exc()
        finally:
            execution.ended_at = utc_now_iso()
            self.store.append(execution)

        return execution

    def _build_execution_metadata(self) -> dict[str, Any]:
        return {}

    @abstractmethod
    def _handle_task(self, task_text: str) -> tuple[str, dict[str, Any]]:
        raise NotImplementedError

