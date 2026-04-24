from __future__ import annotations

import threading
from datetime import datetime, timezone


class RunService:
    def __init__(
        self,
        *,
        model_profile_service,
        plan_repository,
        plan_run_repository,
        execution_repository,
        plan_runner_factory,
        utc_now=None,
    ):
        self._model_profile_service = model_profile_service
        self._plan_repository = plan_repository
        self._plan_run_repository = plan_run_repository
        self._execution_repository = execution_repository
        self._plan_runner_factory = plan_runner_factory
        self._utc_now = utc_now or (lambda: datetime.now(timezone.utc).isoformat())

    def start_run(
        self,
        *,
        plan_id: str,
        profile_id: str,
        max_workers: int,
    ) -> dict[str, object]:
        self._plan_repository.get_plan_summary(plan_id)
        runtime_profile = self._model_profile_service.resolve_runtime_profile(profile_id)
        run_id = self._plan_run_repository.create_run(
            plan_id=plan_id,
            model_profile_id=profile_id,
            max_workers=max_workers,
            started_at=self._utc_now(),
        )
        plan_runner = self._plan_runner_factory(runtime_profile, max_workers)
        worker = threading.Thread(
            target=plan_runner.run_from_plan_id,
            args=(plan_id, run_id),
            daemon=True,
        )
        worker.start()
        return {
            "run_id": run_id,
            "plan_id": plan_id,
            "model_profile_id": profile_id,
            "status": "running",
        }

    def list_runs(self) -> list[dict[str, object]]:
        return self._plan_run_repository.list_runs()

    def get_run_detail(self, run_id: str) -> dict[str, object]:
        run_summary = self._plan_run_repository.get_run_summary(run_id)
        run_tasks = self._plan_run_repository.list_run_tasks(run_id)
        execution_ids = [
            item["execution_task_id"]
            for item in run_tasks
            if item["execution_task_id"]
        ]
        executions = self._execution_repository.load_by_task_ids(execution_ids)
        return {**run_summary, "tasks": run_tasks, "executions": executions}

    def retry_run(self, run_id: str, profile_id: str | None = None) -> dict[str, object]:
        run_summary = self._plan_run_repository.get_run_summary(run_id)
        return self.start_run(
            plan_id=run_summary["plan_id"],
            profile_id=profile_id or run_summary["model_profile_id"],
            max_workers=run_summary["max_workers"],
        )

    def unsupported_control(self, run_id: str, action: str) -> dict[str, object]:
        return {
            "run_id": run_id,
            "action": action,
            "status": "unsupported",
            "message": "Current execution model does not support mid-run interruption.",
        }
