from __future__ import annotations

from pydantic import BaseModel, Field


class CreateModelProfileRequest(BaseModel):
    name: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    base_url: str | None = None
    thinking_mode: str = Field(default="default")
    api_key: str = Field(min_length=1)


class UpdateModelProfileRequest(CreateModelProfileRequest):
    pass


class CreatePlanRequest(BaseModel):
    task: str = Field(min_length=1)
    profile_id: str = Field(min_length=1)


class StartRunRequest(BaseModel):
    plan_id: str = Field(min_length=1)
    profile_id: str = Field(min_length=1)
    max_workers: int = Field(default=1, ge=1)


class RetryRunRequest(BaseModel):
    profile_id: str | None = None
