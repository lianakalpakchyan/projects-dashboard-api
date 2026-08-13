import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.exceptions import NotFoundError, PermissionDeniedError
from app.models import User
from app.schemas import ProjectCreate, ProjectInfo, ProjectUpdate
from app.services import ProjectService

router = APIRouter(tags=["projects"])


@router.post("/projects", response_model=ProjectInfo, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ProjectInfo:
    return ProjectInfo.model_validate(ProjectService(db).create(current_user.id, payload))


@router.get("/projects", response_model=list[ProjectInfo])
def list_projects(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[ProjectInfo]:
    projects = ProjectService(db).list_for_user(current_user.id)
    return [ProjectInfo.model_validate(p) for p in projects]


@router.get("/project/{project_id}/info", response_model=ProjectInfo)
def get_project_info(
    project_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ProjectInfo:
    try:
        project = ProjectService(db).get_if_authorized(current_user.id, project_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return ProjectInfo.model_validate(project)


@router.put("/project/{project_id}/info", response_model=ProjectInfo)
def update_project_info(
    project_id: uuid.UUID,
    payload: ProjectUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ProjectInfo:
    try:
        project = ProjectService(db).update(current_user.id, project_id, payload)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return ProjectInfo.model_validate(project)


@router.delete("/project/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    try:
        ProjectService(db).delete(current_user.id, project_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
