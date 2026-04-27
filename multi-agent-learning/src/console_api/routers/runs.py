from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Request, status
from fastapi.responses import JSONResponse

from console_api.schemas import RetryRunRequest, StartRunRequest

router = APIRouter(prefix="/api/runs", tags=["runs"])


def get_run_service(request: Request):
    return request.app.state.run_service


@router.post("", status_code=status.HTTP_201_CREATED)
def start_run(payload: StartRunRequest, service=Depends(get_run_service)):
    return service.start_run(
        plan_id=payload.plan_id,
        profile_id=payload.profile_id,
        max_workers=payload.max_workers,
    )


@router.get("")
def list_runs(service=Depends(get_run_service)):
    return service.list_runs()


@router.get("/{run_id}")
def get_run_detail(run_id: str, service=Depends(get_run_service)):
    return service.get_run_detail(run_id)


@router.post("/{run_id}/retry", status_code=status.HTTP_201_CREATED)
def retry_run(
    run_id: str,
    payload: RetryRunRequest = Body(default=RetryRunRequest()),
    service=Depends(get_run_service),
):
    return service.retry_run(run_id, profile_id=payload.profile_id)


@router.post("/{run_id}/pause")
def pause_run(run_id: str, service=Depends(get_run_service)):
    payload = service.unsupported_control(run_id, "pause")
    return JSONResponse(status_code=status.HTTP_409_CONFLICT, content=payload)


@router.post("/{run_id}/cancel")
def cancel_run(run_id: str, service=Depends(get_run_service)):
    payload = service.unsupported_control(run_id, "cancel")
    return JSONResponse(status_code=status.HTTP_409_CONFLICT, content=payload)
