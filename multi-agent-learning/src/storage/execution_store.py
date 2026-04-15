from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from models.task import TaskExecution, TaskExecutionRecord


class ExecutionStore:
    """最简单的执行记录存储层。

    阶段一先不用数据库，直接写 JSON，原因是：
    - 文件内容肉眼可读，适合学习
    - 不会引入额外依赖
    - 后续迁移到 SQLite / 向量库时也更容易理解变化点
    """

    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        # 确保存储目录存在，避免首次运行时因为目录不存在而报错。
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, execution: TaskExecution) -> None:
        """追加一条执行记录。"""
        # 当前实现是“读全量 -> 追加 -> 写全量”。
        # 数据量小时足够简单直观，适合作为第一阶段实现。
        records = self.load_all()
        records.append(execution.to_dict())
        self.file_path.write_text(
            json.dumps(records, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def load_all(self) -> list[TaskExecutionRecord]:
        """读取全部执行记录。"""
        if not self.file_path.exists():
            return []

        # 空文件也按“暂无记录”处理，避免 json.loads("") 报错。
        content = self.file_path.read_text(encoding="utf-8").strip()
        if not content:
            return []

        return cast(list[TaskExecutionRecord], json.loads(content))
