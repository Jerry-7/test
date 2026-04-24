from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status

from console_api.schemas import CreatePlanRequest

router = APIRouter(prefix="/api/plans", tags=["plans"])


def get_plan_service(request: Request):
    return request.app.state.plan_service


@router.post("", status_code=status.HTTP_201_CREATED)
def create_plan(payload: CreatePlanRequest, service=Depends(get_plan_service)):
    return service.create_plan(task=payload.task, profile_id=payload.profile_id)


@router.get("")
def list_plans(service=Depends(get_plan_service)):
    return service.list_plans()


@router.get("/{plan_id}")
def get_plan(plan_id: str, service=Depends(get_plan_service)):
    return service.get_plan(plan_id)
