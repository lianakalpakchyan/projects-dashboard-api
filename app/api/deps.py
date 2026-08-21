from typing import Annotated, Any

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from starlette import status

from app.core import decode_access_token
from app.db import get_db
from app.repositories import (
    AccessRepository,
    DocumentRepository,
    ProjectRepository,
    UserRepository,
)
from app.services import AuthService, DocumentService, ProjectService

security_scheme = HTTPBearer()


def get_user_repository(db: Annotated[Session, Depends(get_db)]) -> UserRepository:
    return UserRepository(db)


def get_project_repository(db: Annotated[Session, Depends(get_db)]) -> ProjectRepository:
    return ProjectRepository(db)


def get_access_repository(db: Annotated[Session, Depends(get_db)]) -> AccessRepository:
    return AccessRepository(db)


def get_document_repository(db: Annotated[Session, Depends(get_db)]) -> DocumentRepository:
    return DocumentRepository(db)


def get_auth_service(
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
) -> AuthService:
    return AuthService(user_repo)


def get_project_service(
    project_repo: Annotated[ProjectRepository, Depends(get_project_repository)],
    access_repo: Annotated[AccessRepository, Depends(get_access_repository)],
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
) -> ProjectService:
    return ProjectService(project_repo, access_repo, user_repo)


def get_document_service(
    document_repo: Annotated[DocumentRepository, Depends(get_document_repository)],
    project_service: Annotated[ProjectService, Depends(get_project_service)],
) -> DocumentService:
    return DocumentService(document_repo, project_service)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security_scheme)],
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
) -> Any:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    token = credentials.credentials
    user_id = decode_access_token(token)
    if user_id is None:
        raise credentials_error

    user = user_repo.get(user_id)
    if user is None:
        raise credentials_error
    return user
