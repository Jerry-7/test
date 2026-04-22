from __future__ import annotations

from agents.basic_agent import BasicAgent
from agents.worker_presets import (
    ANALYSIS_AGENT_NAME,
    ANALYSIS_AGENT_PROMPT,
    IMPLEMENTATION_AGENT_NAME,
    IMPLEMENTATION_AGENT_PROMPT,
    REVIEW_AGENT_NAME,
    REVIEW_AGENT_PROMPT,
)
from config.model_provider import ModelProviderConfig
from models.agent_task import AgentTask
from storage.execution_store import ExecutionStore


class AnalysisAgent(BasicAgent):
    """分析型 Worker。

    作用：
    - 执行分析/规划/设计类子任务
    - 在输入中强调问题拆解与约束边界
    """

    def __init__(
        self,
        store: ExecutionStore,
        provider_config: ModelProviderConfig,
        thinking_mode: str = "default",
    ):
        """初始化分析 Worker，注入对应角色提示词。"""
        super().__init__(
            store=store,
            provider_config=provider_config,
            thinking_mode=thinking_mode,
            name=ANALYSIS_AGENT_NAME,
            system_prompt=ANALYSIS_AGENT_PROMPT,
        )

    def build_agent_task_input(self, agent_task: AgentTask) -> str:
        """构建分析任务输入，强调拆解、概念与边界。"""
        return self.build_task_input(
            "请优先输出问题拆解、关键概念、输入输出边界和主要约束。\n"
            f"任务类型: {agent_task.plan_task.type}\n"
            f"任务优先级: {agent_task.plan_task.priority}\n"
            f"任务标题: {agent_task.plan_task.title}\n\n"
            f"{agent_task.rendered_task}"
        )


class ImplementationAgent(BasicAgent):
    """实现型 Worker。

    作用：
    - 执行实现类子任务
    - 在输入中强调可执行步骤与边界条件
    """

    def __init__(
        self,
        store: ExecutionStore,
        provider_config: ModelProviderConfig,
        thinking_mode: str = "default",
    ):
        """初始化实现 Worker，注入实现导向提示词。"""
        super().__init__(
            store=store,
            provider_config=provider_config,
            thinking_mode=thinking_mode,
            name=IMPLEMENTATION_AGENT_NAME,
            system_prompt=IMPLEMENTATION_AGENT_PROMPT,
        )

    def build_agent_task_input(self, agent_task: AgentTask) -> str:
        """构建实现任务输入，强调步骤、数据结构与边界条件。"""
        return self.build_task_input(
            "请优先输出最小可实现方案、实现步骤、关键数据结构和边界条件。\n"
            f"任务类型: {agent_task.plan_task.type}\n"
            f"任务优先级: {agent_task.plan_task.priority}\n"
            f"任务标题: {agent_task.plan_task.title}\n\n"
            f"{agent_task.rendered_task}"
        )


class ReviewAgent(BasicAgent):
    """评审型 Worker。

    作用：
    - 执行评审类子任务
    - 在输入中强调风险、遗漏与改进建议
    """

    def __init__(
        self,
        store: ExecutionStore,
        provider_config: ModelProviderConfig,
        thinking_mode: str = "default",
    ):
        """初始化评审 Worker，注入评审导向提示词。"""
        super().__init__(
            store=store,
            provider_config=provider_config,
            thinking_mode=thinking_mode,
            name=REVIEW_AGENT_NAME,
            system_prompt=REVIEW_AGENT_PROMPT,
        )

    def build_agent_task_input(self, agent_task: AgentTask) -> str:
        """构建评审任务输入，强调风险、遗漏与改进建议。"""
        return self.build_task_input(
            "请优先输出问题、风险、遗漏、可维护性隐患和改进建议。\n"
            f"任务类型: {agent_task.plan_task.type}\n"
            f"任务优先级: {agent_task.plan_task.priority}\n"
            f"任务标题: {agent_task.plan_task.title}\n\n"
            f"{agent_task.rendered_task}"
        )
