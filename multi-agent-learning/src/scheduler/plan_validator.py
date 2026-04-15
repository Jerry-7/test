from models.plan_task import PlanTask
from models.plan_constants import TASK_STATUS_PENDING
class PlanValidator:
    def validate(self, plan_list: list[PlanTask]) -> None:
        if plan_list is None or len(plan_list) == 0:
            raise ValueError("plan list is null.")
        exist_ids = set()
        
        for plan in plan_list:
            if plan.id in exist_ids:
                raise ValueError("Duplicated plan id.")
            exist_ids.add(plan.id)

        for plan in plan_list:
            if plan.status != TASK_STATUS_PENDING:
                raise ValueError(f"Task status is abnormal : {plan.status}.")
            if plan.priority <= 0:
                raise ValueError("Task priority less than 0.")
            for depend_task in plan.depends_on:
                if depend_task not in exist_ids:
                    raise ValueError("Depend task is not exist.")