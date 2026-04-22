from __future__ import annotations

import os
import warnings

from config import ModelProviderConfig, build_chat_model_kwargs
from models.plan_constants import TASK_STATUS_PENDING, TASK_TYPES
from models.plan_task import PlanResult, PlanTask
from models.planner_run_result import PlannerRunResult
from storage.db.session import create_session_factory
from storage.repositories.plan_repository import PlanRepository

try:
    from langchain.agents import create_agent
    from langchain.agents.structured_output import ToolStrategy
    from langchain_openai import ChatOpenAI
except ImportError:
    create_agent = None
    ToolStrategy = None
    ChatOpenAI = None


class PlannerAgent:
    def __init__(
        self,
        provider_config: ModelProviderConfig,
        thinking_mode: str = "default",
        plan_repository: PlanRepository | None = None,
    ):
        self.name = "PlannerAgent"
        self.provider_config = provider_config
        self.thinking_mode = thinking_mode
        self.plan_repository = plan_repository or self._build_default_plan_repository()
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
        path: str | None = None,
    ) -> PlannerRunResult:
        if path:
            warnings.warn(
                "`path` is deprecated in db-only mode and is ignored. "
                "Use database persistence with plan_id instead.",
                DeprecationWarning,
                stacklevel=2,
            )

        cleaned_goal = goal.strip()
        if not cleaned_goal:
            raise ValueError("Goal cannot be empty.")

        plan = self._handle_goal(cleaned_goal)
        plan_id = self.plan_repository.save_plan(
            goal=cleaned_goal,
            provider=self.provider_config.provider,
            model_name=self.provider_config.model_name,
            thinking_mode=self.thinking_mode,
            tasks=plan,
        )
        return PlannerRunResult(plan_id=plan_id, tasks=tuple(plan))

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

    def _build_default_plan_repository(self) -> PlanRepository:
        database_url = os.getenv("DATABASE_URL", "").strip()
        if not database_url:
            raise RuntimeError(
                "PlannerAgent requires plan_repository or DATABASE_URL."
            )
        session_factory = create_session_factory(database_url)
        return PlanRepository(session_factory=session_factory)
