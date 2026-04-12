from __future__ import annotations


class DagScheduler:
    """A minimal sequential DAG scheduler for learning and debugging."""

    def run(self, plan: list[dict], assignments: list[dict]) -> dict:
        tasks = [self._copy_task(task) for task in plan]
        agent_by_task_id = {
            item.get("task_id", ""): item.get("agent_name", "BasicAgent")
            for item in assignments
        }
        trace: list[dict] = []
        completed_ids: set[str] = set()

        self._refresh_ready_tasks(tasks, completed_ids)

        while True:
            ready_task = next((task for task in tasks if task["status"] == "ready"), None)
            if ready_task is None:
                break

            ready_task["status"] = "running"
            trace.append(
                {
                    "task_id": ready_task["id"],
                    "event": "running",
                    "agent_name": agent_by_task_id.get(ready_task["id"], "BasicAgent"),
                }
            )

            ready_task["status"] = "completed"
            completed_ids.add(ready_task["id"])
            trace.append(
                {
                    "task_id": ready_task["id"],
                    "event": "completed",
                    "agent_name": agent_by_task_id.get(ready_task["id"], "BasicAgent"),
                }
            )

            self._refresh_ready_tasks(tasks, completed_ids)

        blocked_tasks = [task for task in tasks if task["status"] == "pending"]
        for task in blocked_tasks:
            task["status"] = "blocked"
            trace.append(
                {
                    "task_id": task["id"],
                    "event": "blocked",
                    "agent_name": agent_by_task_id.get(task["id"], "BasicAgent"),
                }
            )

        return {
            "tasks": tasks,
            "trace": trace,
            "completed_count": len(completed_ids),
            "blocked_count": len(blocked_tasks),
        }

    def _refresh_ready_tasks(self, tasks: list[dict], completed_ids: set[str]) -> None:
        for task in tasks:
            if task["status"] != "pending":
                continue

            depends_on = task.get("depends_on", [])
            if all(dep in completed_ids for dep in depends_on):
                task["status"] = "ready"

    def _copy_task(self, task: dict) -> dict:
        return {
            "id": task.get("id", ""),
            "title": task.get("title", ""),
            "type": task.get("type", ""),
            "depends_on": list(task.get("depends_on", [])),
            "status": str(task.get("status", "pending")),
        }
