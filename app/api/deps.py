from typing import Annotated, Any

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from starlette import status

from app.core.config import get_settings
from app.core.security import decode_access_token
from app.db.session import get_db, get_raw_db_conn
from app.repositories import RawSQLUserRepository, SQLAlchemyUserRepository
from app.repositories.interfaces import (
    AccessRepositoryInterface,
    DocumentRepositoryInterface,
    ProjectRepositoryInterface,
    UserRepositoryInterface,
)
from app.repositories.orm_repos import (
    SQLAlchemyAccessRepository,
    SQLAlchemyDocumentRepository,
    SQLAlchemyProjectRepository,
)
from app.repositories.raw_repos import (
    RawSQLAccessRepository,
    RawSQLDocumentRepository,
    RawSQLProjectRepository,
)
from app.services.auth_service import AuthService
from app.services.document_service import DocumentService
from app.services.project_service import ProjectService

settings = get_settings()


def get_user_repository(
    db: Annotated[Session, Depends(get_db)], conn: Annotated[Any, Depends(get_raw_db_conn)]
) -> UserRepositoryInterface:
    if settings.DATABASE_MODE == "raw":
        return RawSQLUserRepository(conn)
    return SQLAlchemyUserRepository(db)


def get_auth_service(
    user_repo: Annotated[UserRepositoryInterface, Depends(get_user_repository)],
) -> AuthService:
    return AuthService(user_repo)


security_scheme = HTTPBearer()


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security_scheme)],
    user_repo: Annotated[UserRepositoryInterface, Depends(get_user_repository)],
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


def get_project_repository(
    db: Annotated[Session, Depends(get_db)], conn: Annotated[Any, Depends(get_raw_db_conn)]
) -> ProjectRepositoryInterface:
    if settings.DATABASE_MODE == "raw":
        return RawSQLProjectRepository(conn)
    return SQLAlchemyProjectRepository(db)


def get_access_repository(
    db: Annotated[Session, Depends(get_db)], conn: Annotated[Any, Depends(get_raw_db_conn)]
) -> AccessRepositoryInterface:
    if settings.DATABASE_MODE == "raw":
        return RawSQLAccessRepository(conn)
    return SQLAlchemyAccessRepository(db)


def get_project_service(
    project_repo: Annotated[ProjectRepositoryInterface, Depends(get_project_repository)],
    access_repo: Annotated[AccessRepositoryInterface, Depends(get_access_repository)],
) -> ProjectService:
    return ProjectService(project_repo, access_repo)


def get_document_repository(
    db: Annotated[Session, Depends(get_db)], conn: Annotated[Any, Depends(get_raw_db_conn)]
) -> DocumentRepositoryInterface:
    if settings.DATABASE_MODE == "raw":
        return RawSQLDocumentRepository(conn)
    return SQLAlchemyDocumentRepository(db)


def get_document_service(
    document_repo: Annotated[DocumentRepositoryInterface, Depends(get_document_repository)],
    project_service: Annotated[ProjectService, Depends(get_project_service)],
) -> DocumentService:
    return DocumentService(document_repo, project_service)
