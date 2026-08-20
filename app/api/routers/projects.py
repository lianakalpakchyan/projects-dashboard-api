import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_current_user, get_project_service
from app.core import resolve_user_id
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
    user_id = resolve_user_id(current_user)
    return ProjectInfo.model_validate(service.create(user_id, payload))


@router.get("/projects", response_model=list[ProjectFullInfo])
def list_projects(
    current_user: CurrentUserDep, service: ProjectServiceDep
) -> list[ProjectFullInfo]:
    user_id = resolve_user_id(current_user)
    projects = service.list_for_user(user_id)
    return [ProjectFullInfo.model_validate(p) for p in projects]


@router.get("/project/{project_id}/info", response_model=ProjectInfo)
def get_project_info(
    project_id: uuid.UUID, current_user: CurrentUserDep, service: ProjectServiceDep
) -> ProjectInfo:
    user_id = resolve_user_id(current_user)
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
    user_id = resolve_user_id(current_user)
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
    user_id = resolve_user_id(current_user)
    try:
        service.delete(user_id, project_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.post("/project/{project_id}/invite", status_code=status.HTTP_204_NO_CONTENT)
def invite_user(
    project_id: uuid.UUID,
    user: str,
    current_user: CurrentUserDep,
    service: ProjectServiceDep,
) -> None:
    owner_id = resolve_user_id(current_user)
    try:
        service.invite(owner_id, project_id, user)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.get("/project/{project_id}/share", status_code=status.HTTP_200_OK)
def share_project(
    project_id: uuid.UUID,
    email: Annotated[str, Query(alias="with", description="Target invitee email address")],
    current_user: CurrentUserDep,
    service: ProjectServiceDep,
) -> dict[str, str]:
    owner_id = resolve_user_id(current_user)
    try:
        token = service.create_share_token(owner_id, project_id, email)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return {
        "detail": "Invitation token created.",
        "join_link": f"https://app.example.com/projects/join?token={token}",
    }


@router.post("/projects/join", response_model=ProjectInfo, status_code=status.HTTP_200_OK)
def join_project(
    token: str, current_user: CurrentUserDep, service: ProjectServiceDep
) -> ProjectInfo:
    user_id = resolve_user_id(current_user)
    try:
        project = service.consume_share_token(token, user_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return ProjectInfo.model_validate(project)
