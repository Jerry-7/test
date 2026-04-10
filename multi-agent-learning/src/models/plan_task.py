from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PlanTask:
    """结构化计划任务。
    """

    # id 用于标识一次计划。
    id: str
    # title 是计划标题。
    title: str
    # type Dispatcher分配Agent
    type: str
    # depends_on DAG调度顺序判断
    depends_on: list[str] = field(default_factory=list)
    # 计划当前状态
    status: str = "pending"
    
