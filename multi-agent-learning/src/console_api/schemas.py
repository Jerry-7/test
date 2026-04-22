from __future__ import annotations

from pydantic import BaseModel, Field


class CreatePlanRequest(BaseModel):
    task: str = Field(min_length=1)
    provider: str
    model: str | None = None
    thinking: str | None = "default"


class StartRunRequest(BaseModel):
    plan_id: str
    max_workers: int = Field(default=1, ge=1)

