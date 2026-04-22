from datetime import datetime, timezone

import pytest

from models.task import TaskExecution
from storage.execution_store import ExecutionStore
from storage.repositories.execution_repository import ExecutionRepository


def test_append_and_load_all_roundtrip(db_session):
    repo = ExecutionRepository(session_factory=lambda: db_session)
    execution = TaskExecution.create(task_text="hello", agent_name="BasicAgent")
    execution.status = "completed"
    execution.output = "ok"
    execution.error = ""
    execution.traceback = ""
    execution.started_at = "2026-04-21T00:00:00+00:00"
    execution.ended_at = "2026-04-21T00:00:01+00:00"
    execution.metadata = {"provider": "openai", "requested_model": "gpt-5-nano"}

    repo.append(execution)
    records = repo.load_all()

    assert len(records) == 1
    assert records[0]["task_id"] == execution.task_id
    assert records[0]["task_text"] == "hello"
    assert records[0]["agent_name"] == "BasicAgent"
    assert records[0]["status"] == "completed"
    assert records[0]["output"] == "ok"
    assert records[0]["error"] == ""
    assert records[0]["traceback"] == ""
    started_at = datetime.fromisoformat(records[0]["started_at"])
    ended_at = datetime.fromisoformat(records[0]["ended_at"])
    assert started_at.astimezone(timezone.utc) == datetime(
        2026, 4, 21, 0, 0, 0, tzinfo=timezone.utc
    )
    assert ended_at.astimezone(timezone.utc) == datetime(
        2026, 4, 21, 0, 0, 1, tzinfo=timezone.utc
    )
    assert records[0]["metadata"] == {
        "provider": "openai",
        "requested_model": "gpt-5-nano",
    }


def test_append_rejects_naive_datetime(db_session):
    repo = ExecutionRepository(session_factory=lambda: db_session)
    execution = TaskExecution.create(task_text="hello", agent_name="BasicAgent")
    execution.status = "completed"
    execution.output = "ok"
    execution.started_at = "2026-04-21T00:00:00"
    execution.ended_at = "2026-04-21T00:00:01+00:00"

    with pytest.raises(ValueError, match="timezone offset"):
        repo.append(execution)


def test_append_rejects_ended_before_started(db_session):
    repo = ExecutionRepository(session_factory=lambda: db_session)
    execution = TaskExecution.create(task_text="hello", agent_name="BasicAgent")
    execution.status = "completed"
    execution.output = "ok"
    execution.started_at = "2026-04-21T00:00:02+00:00"
    execution.ended_at = "2026-04-21T00:00:01+00:00"

    with pytest.raises(ValueError, match="ended_at must be >= started_at"):
        repo.append(execution)


class _FakeRepository:
    def __init__(self):
        self.saved: list[dict] = []

    def append(self, execution: TaskExecution) -> None:
        self.saved.append(execution.to_dict())

    def load_all(self):
        return list(self.saved)


def test_execution_store_accepts_injected_repository_without_database_url():
    fake = _FakeRepository()
    store = ExecutionStore(repository=fake)
    execution = TaskExecution.create(task_text="x", agent_name="BasicAgent")
    execution.started_at = "2026-04-21T00:00:00+00:00"
    execution.ended_at = "2026-04-21T00:00:01+00:00"
    store.append(execution)
    assert len(store.load_all()) == 1


def test_execution_store_accepts_session_factory_without_database_url():
    class _FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def add(self, _):
            return None

        def commit(self):
            return None

        def query(self, _):
            class _Q:
                def order_by(self, *_args, **_kwargs):
                    return self

                def all(self):
                    return []

            return _Q()

    store = ExecutionStore(session_factory=lambda: _FakeSession())
    assert store.load_all() == []
