from __future__ import annotations

import traceback
from typing import Any

from agents.base_agent import BaseAgent
from config import ModelProviderConfig, build_chat_model_kwargs
from models.agent_task import AgentTask
from models.plan_constants import (
    TASK_STATUS_COMPLETED,
    TASK_STATUS_FAILED,
    TASK_STATUS_RUNNING,
)
from models.task import TaskExecution
from storage.execution_store import ExecutionStore
from utils.time_utils import utc_now_iso

try:
    from langchain.agents import create_agent
    from langchain_openai import ChatOpenAI
except ImportError:
    # 这里不立即抛错，而是把错误延后到 _build_agent()。
    # 这样可以给用户更明确的安装提示。
    create_agent = None
    ChatOpenAI = None


class BasicAgent(BaseAgent):
    """阶段一的最小 LangChain Agent。

    这个类的重点不是“能力多强”，而是帮你看清以下结构：
    - 一个统一的 run() 生命周期
    - LangChain Agent 的创建方式
    - 模型响应如何被提取为纯文本
    - 执行记录如何被落盘
    """

    DEFAULT_SYSTEM_PROMPT = (
        "你是一个帮助用户学习多 Agent 调度的 Python 学习助手。"
        "请用清晰、结构化、适合初学者的方式回答。"
        "优先解释任务目标、关键组成、执行流程和下一步建议。"
    )

    def __init__(
        self,
        store: ExecutionStore,
        provider_config: ModelProviderConfig,
        thinking_mode: str = "default",
        name: str = "BasicAgent",
        system_prompt: str | None = None,
    ):
        """初始化基础 Agent。

        参数：
        - store: 执行记录存储器，用于落盘 TaskExecution。
        - provider_config: 模型提供方配置（model/api_key/base_url）。
        - thinking_mode: 推理模式开关（主要给兼容 provider 使用）。
        - name: Agent 名称，写入执行记录。
        - system_prompt: 可覆盖默认系统提示词。
        """
        super().__init__(name=name)
        self.store = store
        self.provider_config = provider_config
        self.thinking_mode = thinking_mode
        # system_prompt 用来固定 Agent 的角色与回答风格。
        # 后续你做多 Agent 时，不同角色最先分化的通常就是这里。
        self.system_prompt = system_prompt or self.DEFAULT_SYSTEM_PROMPT
        # Agent 在初始化时构建，这样 run() 内部逻辑更聚焦于执行过程。
        self.agent = self._build_agent()

    def run(self, task_text: str) -> TaskExecution:
        """普通字符串输入给Agent的任务。

        典型的 Agent 生命周期：
        create execution -> running -> completed/failed -> persist
        """
        cleaned = task_text.strip()
        if not cleaned:
            raise ValueError("Task text cannot be empty.")

        return self._execute(
            task_text=cleaned,
            agent_input=self.build_task_input(cleaned),
        )

    def _execute(self, task_text: str, agent_input: str) -> TaskExecution:
        """执行统一生命周期并落盘结果。

        参数：
        - task_text: 用于记录的任务文本（强调“任务语义”）。
        - agent_input: 实际发送给模型的输入文本（可包含增强上下文）。
        """
        # 先创建执行对象，后续所有状态和结果都挂在这个对象上。
        execution = TaskExecution.create(task_text=task_text, agent_name=self.name)
        execution.started_at = utc_now_iso()
        execution.status = TASK_STATUS_RUNNING

        # 记录请求时使用的模型名，便于后续做成本分析或问题排查。
        execution.metadata["provider"] = self.provider_config.provider
        execution.metadata["requested_model"] = self.provider_config.model_name
        execution.metadata["thinking_mode"] = self.thinking_mode
        if self.provider_config.base_url:
            execution.metadata["base_url"] = self.provider_config.base_url

        try:
            # 真正的模型调用逻辑被收敛到 _handle_task()。
            output, metadata = self._handle_task(agent_input)
            execution.output = output
            execution.metadata.update(metadata)
            execution.status = TASK_STATUS_COMPLETED
        except Exception as exc:
            # Agent 内部捕获异常后，依然会把失败记录写盘。
            # 这比直接崩溃更适合学习“可观测性”。
            execution.status = TASK_STATUS_FAILED
            execution.error = f"{type(exc).__name__}: {exc}"
            execution.output = ""
            execution.traceback = traceback.format_exc()
        finally:
            # 不论成功还是失败，都记录结束时间并持久化。
            execution.ended_at = utc_now_iso()
            self.store.append(execution)

        return execution

    def run_agent_task(self, agent_task: AgentTask) -> TaskExecution:
        """执行结构化任务入口。

        这里会先校验并构建 `agent_input`，再进入统一执行流程 `_execute`。
        """
        rendered_task = agent_task.rendered_task.strip()
        if not rendered_task:
            raise ValueError("Task text cannot be empty.")

        agent_input = self.build_agent_task_input(agent_task).strip()
        if not agent_input:
            raise ValueError("Task input cannot be empty.")

        return self._execute(
            task_text=rendered_task,
            agent_input=agent_input,
        )

    def _handle_task(self, agent_input: str) -> tuple[str, dict[str, Any]]:
        """处理单次任务。

        返回值拆成两部分：
        - output: 给用户展示的文本
        - metadata: usage、model_name、finish_reason 等辅助信息
        """
        cleaned = agent_input.strip()
        if not cleaned:
            raise ValueError("Task text cannot be empty.")

        # 这里先用最简单的 user message，不引入复杂上下文。
        response = self.agent.invoke(
            {"messages": [{"role": "user", "content": cleaned}]}
        )
        return self._extract_text(response), self._extract_metadata(response)

    # 普通文本 输入给agent
    def build_task_input(self, task_text: str) -> str:
        """构建普通文本任务的模型输入。

        当前实现为直传，子类可覆盖做统一包装。
        """
        return task_text

    def build_agent_task_input(self, agent_task: AgentTask) -> str:
        """构建结构化任务的模型输入。

        默认使用 `AgentTask.rendered_task`，子类可覆写加入角色化提示。
        """
        return self.build_task_input(agent_task.rendered_task)

    def _build_agent(self):
        """构建 LangChain Agent 实例。"""
        if create_agent is None or ChatOpenAI is None:
            raise RuntimeError(
                "Missing LangChain dependencies. Install them with "
                "`pip install -r requirements.txt`."
            )

        # temperature=0 让输出尽量稳定，适合学习阶段观察行为。
        # stream_usage=True 让响应里尽可能带上 token 使用信息。
        model_kwargs = build_chat_model_kwargs(
            self.provider_config,
            thinking_mode=self.thinking_mode,
        )
        model = ChatOpenAI(**model_kwargs)
        return create_agent(
            model=model,
            # 阶段一不接工具，只保留“纯模型 + system prompt”最小闭环。
            tools=[],
            system_prompt=self.system_prompt,
        )

    def _extract_text(self, response: dict[str, Any]) -> str:
        """从 LangChain 返回结构里提取最终文本。"""
        messages = response.get("messages", [])
        if not messages:
            # 如果返回结构和预期不符，退化为直接转字符串，方便调试。
            return str(response)

        # 一般最后一条消息就是模型回复。
        last_message = messages[-1]
        content = getattr(last_message, "content", "")
        return self._normalize_content(content)

    def _extract_metadata(self, response: dict[str, Any]) -> dict[str, Any]:
        """提取与调试、评估相关的元数据。"""
        messages = response.get("messages", [])
        if not messages:
            return {}

        last_message = messages[-1]
        usage_metadata = getattr(last_message, "usage_metadata", None)
        response_metadata = getattr(last_message, "response_metadata", None)

        metadata: dict[str, Any] = {}
        if isinstance(usage_metadata, dict):
            # usage 里通常能看到 input/output token 等统计。
            metadata["usage"] = usage_metadata
        if isinstance(response_metadata, dict):
            model_name = response_metadata.get("model_name")
            finish_reason = response_metadata.get("finish_reason")
            if model_name:
                metadata["response_model"] = model_name
            if finish_reason:
                metadata["finish_reason"] = finish_reason

        return metadata

    def _normalize_content(self, content: Any) -> str:
        """把不同格式的 content 统一转成字符串。

        不同模型/SDK 版本下，content 可能是：
        - str
        - list[str]
        - list[dict]
        所以这里做一次兼容层，减少上层代码复杂度。
        """
        if isinstance(content, str):
            return content

        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                    continue

                if isinstance(item, dict):
                    # 某些内容块会把真正的文本放在 text 字段里。
                    text = item.get("text")
                    if isinstance(text, str) and text.strip():
                        parts.append(text)
                        continue

                    # 这里再兼容一层，防止不同格式下字段名不是 text。
                    content_text = item.get("content")
                    if isinstance(content_text, str) and content_text.strip():
                        parts.append(content_text)

            if parts:
                return "\n".join(parts)

        return str(content)
