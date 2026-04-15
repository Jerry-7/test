from __future__ import annotations

import json
from pathlib import Path

from agents.base_agent import BaseAgent
from config import ModelProviderConfig, build_chat_model_kwargs
from models.plan_constants import TASK_STATUS_PENDING, TASK_TYPES
from models.plan_task import PlanResult, PlanTask

try:
    from langchain.agents import create_agent
    from langchain.agents.structured_output import ToolStrategy
    from langchain_openai import ChatOpenAI
except ImportError:
    create_agent = None
    ToolStrategy = None
    ChatOpenAI = None


class PlannerAgent(BaseAgent):
    """阶段 2 的 LangChain 版 PlannerAgent。

    目标是把复杂学习目标转换成结构化计划，并保存为 `plan.json`。
    """

    def __init__(
        self,
        provider_config: ModelProviderConfig,
        thinking_mode: str = "default",
    ):
        super().__init__(name="PlannerAgent")
        self.provider_config = provider_config
        self.thinking_mode = thinking_mode
        self.system_prompt = (
            "你是一个计划者。"
            "请把用户的任务拆成 1 到 5 个清晰、循序渐进的任务。"
            "每个任务必须包含以下字段："
            "id、title、type、depends_on、status、priority。"
            "priority 使用正整数，数字越小优先级越高。"
            "如果多个任务同时可执行，优先级更高的任务应该有更小的 priority。"
            "任务之间要体现合理依赖。"
            f"status 一律初始化为 {TASK_STATUS_PENDING}。"
            f"type 只使用 {', '.join(TASK_TYPES)} 这些值。"
            "输出必须严格符合结构化 schema。"
        )
        self.agent = self._build_agent()

    def run(
        self,
        goal: str,
        path: str = "data/plans/plan.json",
    ) -> list[PlanTask]:
        cleaned_goal = goal.strip()
        if not cleaned_goal:
            raise ValueError("Goal cannot be empty.")

        try:
            plan = self._handle_goal(cleaned_goal)
            self.save_plan(plan, path=path)
            return plan
        except Exception as exc:
            raise RuntimeError(f"PlannerAgent failed: {exc}") from exc

    def _handle_goal(self, goal: str) -> list[PlanTask]:
        response = self.agent.invoke(
            {"messages": [{"role": "user", "content": goal}]}
        )
        structured_response = response.get("structured_response")
        if structured_response is None:
            raise RuntimeError("PlannerAgent did not return structured_response.")

        if isinstance(structured_response, PlanResult):
            return structured_response.tasks

        raise RuntimeError(
            f"Unexpected structured response type: {type(structured_response).__name__}"
        )

    def _build_agent(self):
        if create_agent is None or ToolStrategy is None or ChatOpenAI is None:
            raise RuntimeError(
                "Missing LangChain dependencies. Install them with "
                "`pip install -r requirements.txt`."
            )

        model_kwargs = build_chat_model_kwargs(
            self.provider_config,
            thinking_mode=self.thinking_mode,
        )
        model = ChatOpenAI(**model_kwargs)
        return create_agent(
            model=model,
            tools=[],
            system_prompt=self.system_prompt,
            response_format=ToolStrategy(PlanResult),
        )

    def save_plan(
        self,
        plan: list[PlanTask],
        path: str = "data/plans/plan.json",
    ) -> None:
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(
            json.dumps(
                [task.model_dump() for task in plan],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
