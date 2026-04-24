from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status

from console_api.schemas import CreateModelProfileRequest, UpdateModelProfileRequest

router = APIRouter(prefix="/api/model-profiles", tags=["model-profiles"])


def get_model_profile_service(request: Request):
    return request.app.state.model_profile_service


@router.get("")
def list_model_profiles(service=Depends(get_model_profile_service)):
    return service.list_profiles()


@router.post("", status_code=status.HTTP_201_CREATED)
def create_model_profile(
    payload: CreateModelProfileRequest,
    service=Depends(get_model_profile_service),
):
    return service.create_profile(**payload.model_dump())


@router.get("/{profile_id}")
def get_model_profile(profile_id: str, service=Depends(get_model_profile_service)):
    return service.get_profile(profile_id)


@router.put("/{profile_id}")
def update_model_profile(
    profile_id: str,
    payload: UpdateModelProfileRequest,
    service=Depends(get_model_profile_service),
):
    return service.update_profile(profile_id, **payload.model_dump())


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_model_profile(profile_id: str, service=Depends(get_model_profile_service)):
    service.delete_profile(profile_id)


@router.post("/{profile_id}/duplicate", status_code=status.HTTP_201_CREATED)
def duplicate_model_profile(profile_id: str, service=Depends(get_model_profile_service)):
    return service.duplicate_profile(profile_id)
