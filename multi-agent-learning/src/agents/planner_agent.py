import json
from pathlib import Path
from models.plan_task import PlanTask
from dataclasses import asdict
from agents.base_agent import BaseAgent
from config import ModelProviderConfig
from storage.execution_store import ExecutionStore


class PlannerAgent(BaseAgent):
    def __init__(self, store: ExecutionStore, provider_config: ModelProviderConfig):
        super().__init__(name="PlannerAgent")
        self.provider_config = provider_config
        # system_prompt 用来固定 Agent 的角色与回答风格。
        # 后续你做多 Agent 时，不同角色最先分化的通常就是这里。
        self.system_prompt = "你是一个计划者，分解用户输入的目标任务，并逐步完成。"
        # Agent 在初始化时构建，这样 run() 内部逻辑更聚焦于执行过程。
        self.agent = self._build_agent()

    def run(self, goal: str) -> list[dict]:
        goal = goal.strip()
        if not goal:
            raise ValueError("Goal cannot be empty.")

        planList = [
            PlanTask(
                id="task-1",
                title=f"理解目标：{goal}",
                type="analysis",
            ),
            PlanTask(
                id="task-2",
                title="拆分关键学习阶段",
                type="planning",
                depends_on=["task-1"],
            ),
            PlanTask(
                id="task-3",
                title="设计每个阶段的 MVP 项目",
                type="design",
                depends_on=["task-2"],
            ),
        ]

        return [asdict(task) for task in planList]
    
    def _handle_goal(goal: str){
            
    }

    def save_plan(plan: list[dict], path: str = "data/plans/plan.json") -> None:
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(
            json.dumps(plan, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
