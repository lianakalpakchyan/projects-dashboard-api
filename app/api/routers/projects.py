import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user, get_project_service
from app.exceptions import NotFoundError, PermissionDeniedError
from app.schemas.project import ProjectCreate, ProjectFullInfo, ProjectInfo, ProjectUpdate
from app.services.project_service import ProjectService

router = APIRouter(tags=["projects"])

ProjectServiceDep = Annotated[ProjectService, Depends(get_project_service)]
CurrentUserDep = Annotated[Any, Depends(get_current_user)]


@router.post("/projects", response_model=ProjectInfo, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate, current_user: CurrentUserDep, service: ProjectServiceDep
) -> ProjectInfo:
    user_id = current_user.id if hasattr(current_user, "id") else current_user["id"]
    return ProjectInfo.model_validate(service.create(user_id, payload))


@router.get("/projects", response_model=list[ProjectFullInfo])
def list_projects(
    current_user: CurrentUserDep, service: ProjectServiceDep
) -> list[ProjectFullInfo]:
    user_id = current_user.id if hasattr(current_user, "id") else current_user["id"]
    projects = service.list_for_user(user_id)
    return [ProjectFullInfo.model_validate(p) for p in projects]


@router.get("/project/{project_id}/info", response_model=ProjectInfo)
def get_project_info(
    project_id: uuid.UUID, current_user: CurrentUserDep, service: ProjectServiceDep
) -> ProjectInfo:
    user_id = current_user.id if hasattr(current_user, "id") else current_user["id"]
    try:
        project = service.get_if_authorized(user_id, project_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return ProjectInfo.model_validate(project)


@router.put("/project/{project_id}/info", response_model=ProjectInfo)
def update_project_info(
    project_id: uuid.UUID,
    payload: ProjectUpdate,
    current_user: CurrentUserDep,
    service: ProjectServiceDep,
) -> ProjectInfo:
    user_id = current_user.id if hasattr(current_user, "id") else current_user["id"]
    try:
        project = service.update(user_id, project_id, payload)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return ProjectInfo.model_validate(project)


@router.delete("/project/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: uuid.UUID, current_user: CurrentUserDep, service: ProjectServiceDep
) -> None:
    user_id = current_user.id if hasattr(current_user, "id") else current_user["id"]
    try:
        service.delete(user_id, project_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
