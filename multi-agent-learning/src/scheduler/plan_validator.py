from __future__ import annotations

from models.plan_constants import TASK_STATUS_PENDING
from models.plan_task import PlanTask


class PlanValidator:
    """计划校验器。

    作用：
    - 校验计划任务的字段合法性与引用完整性
    - 在执行前阻断重复 id、非法依赖、循环依赖等问题
    """

    def validate(self, plan_list: list[PlanTask]) -> None:
        if not plan_list:
            raise ValueError("Plan list cannot be empty.")
        task_ids = [item.id for item in plan_list]
        exist_ids = set(task_ids)
        if len(exist_ids) != len(task_ids):
            raise ValueError("Duplicated plan id.")

        for plan in plan_list:
            if plan.status != TASK_STATUS_PENDING:
                raise ValueError(f"Task status is abnormal: {plan.status}.")
            if plan.priority <= 0:
                raise ValueError(f"Task priority must be > 0: {plan.id}.")

            for depend_task in plan.depends_on:
                if depend_task not in exist_ids:
                    raise ValueError(
                        f"Dependency task does not exist: {depend_task}."
                    )

        self._validate_no_dependency_cycles(plan_list)

    def _validate_no_dependency_cycles(self, plan_list: list[PlanTask]) -> None:
        dependency_graph = {
            item.id: item.depends_on for item in plan_list
        }
        visiting: set[str] = set()
        visited: set[str] = set()

        for task_id in dependency_graph:
            self._dfs_check_cycle(
                task_id=task_id,
                dependency_graph=dependency_graph,
                visiting=visiting,
                visited=visited,
                stack=[],
            )

    def _dfs_check_cycle(
        self,
        task_id: str,
        dependency_graph: dict[str, list[str]],
        visiting: set[str],
        visited: set[str],
        stack: list[str],
    ) -> None:
        if task_id in visited:
            return
        if task_id in visiting:
            cycle_path = " -> ".join([*stack, task_id])
            raise ValueError(f"Cyclic dependency detected: {cycle_path}.")

        visiting.add(task_id)
        next_stack = [*stack, task_id]

        for dep_id in dependency_graph[task_id]:
            self._dfs_check_cycle(
                task_id=dep_id,
                dependency_graph=dependency_graph,
                visiting=visiting,
                visited=visited,
                stack=next_stack,
            )

        visiting.remove(task_id)
        visited.add(task_id)
