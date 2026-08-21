import logging
import uuid
from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt

from app.core import settings
from app.enums import Role
from app.exceptions import NotFoundError, PermissionDeniedError
from app.models import Project
from app.repositories import (
    AccessRepository,
    ProjectRepository,
    UserRepository,
)
from app.schemas import ProjectCreate, ProjectUpdate

logger = logging.getLogger(__name__)


class ProjectService:
    def __init__(
        self,
        project_repo: ProjectRepository,
        access: AccessRepository,
        user_repo: UserRepository,
    ) -> None:
        self.projects = project_repo
        self.access = access
        self.users = user_repo

    def create(self, owner_id: uuid.UUID, payload: ProjectCreate) -> Project:
        project = self.projects.add(payload.name, payload.description)
        project_id = project.id

        self.access.grant(owner_id, project_id, Role.OWNER)
        logger.info(f"Project {project_id} successfully created by owner: {owner_id}")
        return project

    def list_for_user(self, user_id: uuid.UUID) -> list[Project]:
        return self.projects.list_for_user(user_id)

    def get_if_authorized(self, user_id: uuid.UUID, project_id: uuid.UUID) -> Project:
        project = self.projects.get(project_id)
        if project is None:
            raise NotFoundError("project not found")

        if self.access.get_for_user_and_project(user_id, project_id) is None:
            raise PermissionDeniedError("no access to this project")
        return project

    def update(
        self, user_id: uuid.UUID, project_id: uuid.UUID, payload: ProjectUpdate
    ) -> Project | None:
        self.get_if_authorized(user_id, project_id)
        project = self.projects.update(project_id, payload.name, payload.description)
        return project

    def delete(self, user_id: uuid.UUID, project_id: uuid.UUID) -> None:
        project = self.projects.get(project_id)
        if project is None:
            raise NotFoundError("project not found")

        access = self.access.get_for_user_and_project(user_id, project_id)
        if access is None:
            raise PermissionDeniedError("only the owner can delete this project")

        role = access.role
        if role != Role.OWNER:
            raise PermissionDeniedError("only the owner can delete this project")

        self.projects.delete(project)

    def invite(self, owner_id: uuid.UUID, project_id: uuid.UUID, invitee_login: str) -> None:
        owner_access = self.access.get_for_user_and_project(owner_id, project_id)
        if owner_access is None:
            raise PermissionDeniedError("only the owner can invite users")
        role = owner_access.role
        if role != Role.OWNER:
            raise PermissionDeniedError("only the owner can invite users")

        invitee = self.users.get_by_login(invitee_login)
        if invitee is None:
            raise NotFoundError(f"user '{invitee_login}' not found")
        invitee_id = invitee.id

        if invitee_id == owner_id:
            raise PermissionDeniedError("you cannot invite yourself to a project")

        if self.access.get_for_user_and_project(invitee_id, project_id) is None:
            self.access.grant(invitee_id, project_id, Role.PARTICIPANT)

    def create_share_token(
        self, owner_id: uuid.UUID, project_id: uuid.UUID, invitee_email: str
    ) -> str:
        access = self.access.get_for_user_and_project(owner_id, project_id)
        if access is None:
            raise PermissionDeniedError("only the owner can generate share tokens")
        role = access.role
        if role != Role.OWNER:
            raise PermissionDeniedError("only the owner can generate share tokens")

        expire = datetime.now(UTC) + timedelta(minutes=1440)  # Expires in 24 hours
        payload = {
            "project_id": str(project_id),
            "email": invitee_email,
            "purpose": "join",
            "exp": expire,
        }
        return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    def consume_share_token(self, token: str, current_user_id: uuid.UUID) -> Project:
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
            if payload.get("purpose") != "join":
                raise PermissionDeniedError("invalid token purpose.")
            project_id = uuid.UUID(payload["project_id"])
        except (JWTError, KeyError, ValueError) as exc:
            raise PermissionDeniedError("the invitation token has expired or is invalid.") from exc

        project = self.projects.get(project_id)
        if project is None:
            raise NotFoundError("the project associated with this invitation has been deleted.")

        existing_access = self.access.get_for_user_and_project(current_user_id, project_id)
        if existing_access is None:
            self.access.grant(current_user_id, project_id, Role.PARTICIPANT)

        return project
