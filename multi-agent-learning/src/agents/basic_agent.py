from __future__ import annotations

from typing import Any

from agents.base_agent import BaseAgent
from config import ModelProviderConfig
from storage.execution_store import ExecutionStore

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

    def __init__(self, store: ExecutionStore, provider_config: ModelProviderConfig):
        super().__init__(name="BasicAgent", store=store)
        self.provider_config = provider_config
        # system_prompt 用来固定 Agent 的角色与回答风格。
        # 后续你做多 Agent 时，不同角色最先分化的通常就是这里。
        self.system_prompt = (
            "你是一个帮助用户学习多 Agent 调度的 Python 学习助手。"
            "请用清晰、结构化、适合初学者的方式回答。"
            "优先解释任务目标、关键组成、执行流程和下一步建议。"
        )
        # Agent 在初始化时构建，这样 run() 内部逻辑更聚焦于执行过程。
        self.agent = self._build_agent()

    def _build_execution_metadata(self) -> dict[str, Any]:
        metadata = {
            "provider": self.provider_config.provider,
            "requested_model": self.provider_config.model_name,
        }
        if self.provider_config.base_url:
            metadata["base_url"] = self.provider_config.base_url
        return metadata

    def _handle_task(self, task_text: str) -> tuple[str, dict[str, Any]]:
        """处理单次任务。

        返回值拆成两部分：
        - output: 给用户展示的文本
        - metadata: usage、model_name、finish_reason 等辅助信息
        """
        cleaned = task_text.strip()
        if not cleaned:
            raise ValueError("Task text cannot be empty.")

        # LangChain v1 常见调用方式之一：传入 messages。
        # 这里先用最简单的 user message，不引入复杂上下文。
        response = self.agent.invoke(
            {"messages": [{"role": "user", "content": cleaned}]}
        )
        return self._extract_text(response), self._extract_metadata(response)

    def _build_agent(self):
        """构建 LangChain Agent 实例。"""
        if create_agent is None or ChatOpenAI is None:
            raise RuntimeError(
                "Missing LangChain dependencies. Install them with "
                "`pip install -r requirements.txt`."
            )

        # temperature=0 让输出尽量稳定，适合学习阶段观察行为。
        # stream_usage=True 让响应里尽可能带上 token 使用信息。
        model_kwargs: dict[str, Any] = {
            "model": self.provider_config.model_name,
            "api_key": self.provider_config.api_key,
            "temperature": 0,
            "stream_usage": True,
        }
        if self.provider_config.base_url:
            model_kwargs["base_url"] = self.provider_config.base_url
        if self.provider_config.default_headers:
            model_kwargs["default_headers"] = self.provider_config.default_headers

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
