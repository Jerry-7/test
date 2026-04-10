from __future__ import annotations

from abc import ABC, abstractmethod

from models.task import TaskExecution


class BaseAgent(ABC):
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def run(self, task_text: str) -> TaskExecution:
        raise NotImplementedError

