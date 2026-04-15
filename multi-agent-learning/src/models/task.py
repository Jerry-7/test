from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, TypedDict, cast
from uuid import uuid4

from models.plan_constants import TASK_STATUS_PENDING, TaskState


class TaskExecutionRecord(TypedDict):
    task_id: str
    task_text: str
    agent_name: str
    status: TaskState
    output: str
    error: str
    traceback: str
    started_at: str
    ended_at: str
    metadata: dict[str, Any]


@dataclass
class TaskExecution:
    """单次任务执行记录。

    你可以把它理解成一次 Agent 运行的快照：
    - task_text 是输入
    - output / error 是输出
    - started_at / ended_at 是时间信息
    - metadata 是扩展信息
    """

    # task_id 用于标识一次唯一执行。
    task_id: str
    # task_text 是用户输入的原始任务。
    task_text: str
    # agent_name 用于追踪“是谁执行了这个任务”。
    agent_name: str
    # status 反映执行生命周期，后续多 Agent 调度会更依赖它。
    status: TaskState = TASK_STATUS_PENDING
    # output 保存模型的正常输出。
    output: str = ""
    # error 保存简短错误信息，适合直接展示。
    error: str = ""
    # traceback 保存详细堆栈，适合调试。
    traceback: str = ""
    # started_at / ended_at 用于计算耗时。
    started_at: str = ""
    ended_at: str = ""
    # metadata 存储额外信息，例如模型名、token 使用量、finish_reason。
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(cls, task_text: str, agent_name: str) -> "TaskExecution":
        """创建一条默认状态为 pending 的执行记录。"""
        return cls(
            task_id=f"task-{uuid4().hex[:8]}",
            task_text=task_text,
            agent_name=agent_name,
        )

    def to_dict(self) -> TaskExecutionRecord:
        """转成可序列化字典，便于写入 JSON。"""
        return cast(TaskExecutionRecord, asdict(self))
