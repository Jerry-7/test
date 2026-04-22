from __future__ import annotations

from abc import ABC, abstractmethod

from models.agent_task import AgentTask
from models.task import TaskExecution


class BaseAgent(ABC):
    """所有 Agent 的抽象基类。

    作用：
    - 统一对外执行接口（`run` / `run_agent_task`）
    - 约束子类遵守相同调用契约，便于调度层解耦
    """

    def __init__(self, name: str):
        """初始化 Agent 公共属性。

        参数：
        - name: Agent 名称，用于执行记录与调试输出。
        """
        self.name = name

    @abstractmethod
    def run(self, task_text: str) -> TaskExecution:
        """执行普通文本任务。

        参数：
        - task_text: 直接给 Agent 的任务文本。

        返回：
        - TaskExecution: 单次执行结果与元数据。
        """
        raise NotImplementedError

    @abstractmethod
    def run_agent_task(self, agent_task: AgentTask) -> TaskExecution:
        """执行结构化任务。

        参数：
        - agent_task: 已结构化并可直接执行的任务对象。

        返回：
        - TaskExecution: 单次执行结果与元数据。
        """
        raise NotImplementedError
