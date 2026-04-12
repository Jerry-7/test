from __future__ import annotations

import json
import re
from dataclasses import asdict
from pathlib import Path
from typing import Any, Literal

from agents.base_agent import BaseAgent
from config import ModelProviderConfig
from models.plan_task import PlanTask
from storage.execution_store import ExecutionStore

try:
    from langchain_openai import ChatOpenAI

    LANGCHAIN_OPENAI_IMPORT_ERROR = None
except ImportError as exc:
    # 这里不立即抛错，而是把错误延后到 _build_agent()。
    # 这样可以给用户更明确的安装提示。
    ChatOpenAI = None
    LANGCHAIN_OPENAI_IMPORT_ERROR = exc


class PlannerAgent(BaseAgent):
    def __init__(
        self,
        store: ExecutionStore,
        backend: Literal["rule", "llm"] = "rule",
        provider_config: ModelProviderConfig | None = None,
    ):
        super().__init__(name="PlannerAgent", store=store)
        self.backend = backend
        self.provider_config = provider_config
        self.last_planner_debug: dict[str, Any] = {}
        if self.backend == "llm" and self.provider_config is None:
            raise RuntimeError("LLM planner backend requires provider_config.")

        self.system_prompt = (
            "你是一个规划者，负责把用户目标拆解为可执行子任务，并给出明确的依赖顺序。"
        )
        self.agent = self._build_agent()

    def _handle_task(self, task_text: str) -> tuple[str, dict[str, Any]]:
        goal = task_text.strip()
        if not goal:
            raise ValueError("Goal cannot be empty.")

        self.last_planner_debug = {
            "backend": self.backend,
            "fallback": False,
            "reason": "",
            "raw_output": "",
        }
        plan = self._handle_goal_llm(goal) if self.backend == "llm" else self._handle_goal_rule(goal)
        self.save_plan(plan)
        output = json.dumps(plan, ensure_ascii=False, indent=2)
        return output, {
            "planner_backend": self.backend,
            "plan": plan,
            "plan_tasks": len(plan),
            "planner_debug": self.last_planner_debug,
        }

    def _handle_goal_rule(self, goal: str) -> list[dict]:
        plan_list = [
            PlanTask(
                id="task-1",
                title=f"理解目标：{goal}",
                type="analysis",
            ),
            PlanTask(
                id="task-2",
                title="将目标分解为执行节点",
                type="planning",
                depends_on=["task-1"],
            ),
            PlanTask(
                id="task-3",
                title="按照节点执行,并根据实际情况进行调整",
                type="design",
                depends_on=["task-2"],
            ),
        ]
        return [asdict(task) for task in plan_list]

    def _handle_goal_llm(self, goal: str) -> list[dict]:
        if self.agent is None:
            raise RuntimeError("LLM planner agent is not initialized.")
        try:
            prompt = f"""
            你是任务规划器。请把目标拆成 1~6 个子任务，并只输出 JSON 数组。
            每个元素字段必须包含：
            - id: string (如 task-1)
            - title: string
            - type: string (analysis/planning/design/research/writing/review)
            - depends_on: string[]
            - status: "pending"

            目标：{goal}
            只输出 JSON，不要 markdown，不要解释。
            """.strip()
            response = self.agent.invoke(prompt)
            text = self._normalize_content(getattr(response, "content", response))
        except Exception as exc:
            self.last_planner_debug.update(
                {
                    "fallback": True,
                    "reason": f"llm invoke failed: {type(exc).__name__}: {exc}",
                    "raw_output": "",
                }
            )
            return self._handle_goal_rule(goal)
        try:
            plan_list = self._extract_plan_json(text)
            self.last_planner_debug["raw_output"] = text
            return self._validate_plan(plan_list)
        except Exception as exc:
            self.last_planner_debug.update(
                {
                    "fallback": True,
                    "reason": f"llm output invalid: {type(exc).__name__}: {exc}",
                    "raw_output": text,
                }
            )
            return self._handle_goal_rule(goal)

    def _extract_plan_json(self, text: str) -> list[dict]:
        # 兼容 ```json ... ``` 包裹
        m = re.search(r"```json\s*(.*?)\s*```", text, re.S | re.I)
        raw = m.group(1) if m else text
        data = json.loads(raw)
        if not isinstance(data, list):
            raise ValueError("Plan must be a JSON array.")
        return data

    def _validate_plan(self, plan: list[dict]) -> list[dict]:
        if not (1 <= len(plan) <= 6):
            raise ValueError("Plan task count must be between 1 and 6.")

        normalized: list[dict] = []
        ids: list[str] = []
        seen_ids = set()
        for i, item in enumerate(plan, start=1):
            if not isinstance(item, dict):
                raise ValueError("Each plan item must be an object.")
            task_id = str(item.get("id") or f"task-{i}")
            if task_id in ids:
                raise ValueError(f"Duplicate task id: {task_id}")
            title = str(item.get("title") or "").strip()

            task_type = str(item.get("type") or "analysis").strip()
            valid_type = [
                "analysis",
                "planning",
                "design",
                "research",
                "writing",
                "review",
            ]
            if task_type not in valid_type:
                raise ValueError("task_type is not a valid type.")

            status = str(item.get("status") or "pending")
            depends_on = item.get("depends_on") or []
            if not isinstance(depends_on, list):
                depends_on = []
            depends_on = [str(x) for x in depends_on]
            if i == 1:
                if depends_on:
                    raise ValueError("first task can't depend on other task")
            else:
                for depend_task in depends_on:
                    if not depend_task or depend_task not in seen_ids:
                        raise ValueError(
                            f"Task {task_id} depends on future or unknown task: {depend_task}"
                        )
            if not title:
                raise ValueError("title is required.")

            seen_ids.add(task_id)
            normalized.append(
                {
                    "id": task_id,
                    "title": title,
                    "type": task_type,
                    "depends_on": depends_on,
                    "status": status,
                }
            )
            ids.append(task_id)

        id_set = set(ids)
        for item in normalized:
            item["depends_on"] = [
                d for d in item["depends_on"] if d in id_set and d != item["id"]
            ]

        return normalized

    def _build_agent(self):
        if self.backend == "rule":
            return None

        if ChatOpenAI is None:
            raise RuntimeError(
                "Missing langchain-openai dependency. Install it with "
                f"`pip install -r requirements.txt`. Original import error: "
                f"{LANGCHAIN_OPENAI_IMPORT_ERROR}"
            )
        if not self.provider_config:
            raise RuntimeError("Missing LLM provider config.")

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

        return ChatOpenAI(**model_kwargs)

    def _normalize_content(self, content: Any) -> str:
        if isinstance(content, str):
            return content.strip()

        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                    continue

                if isinstance(item, dict):
                    text = item.get("text") or item.get("content")
                    if isinstance(text, str) and text.strip():
                        parts.append(text)

            return "\n".join(parts).strip()

        return str(content).strip()

    @staticmethod
    def save_plan(plan: list[dict], path: str = "data/plans/plan.json") -> None:
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(
            json.dumps(plan, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
