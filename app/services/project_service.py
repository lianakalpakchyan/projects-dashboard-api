import logging
import uuid
from typing import Any

from app.exceptions import NotFoundError, PermissionDeniedError
from app.models import Role
from app.repositories.interfaces import AccessRepositoryInterface, ProjectRepositoryInterface
from app.schemas import ProjectCreate, ProjectUpdate

logger = logging.getLogger(__name__)


class ProjectService:
    def __init__(
        self, projects: ProjectRepositoryInterface, access: AccessRepositoryInterface
    ) -> None:
        self.projects = projects
        self.access = access

    def create(self, owner_id: uuid.UUID, payload: ProjectCreate) -> Any:
        project = self.projects.add(payload.name, payload.description)
        project_id = project.id if hasattr(project, "id") else project["id"]

        self.access.grant(owner_id, project_id, Role.OWNER)
        logger.info(f"Project {project_id} successfully created by owner: {owner_id}")
        return project

    def list_for_user(self, user_id: uuid.UUID) -> list[Any]:
        return self.projects.list_for_user(user_id)

    def get_if_authorized(self, user_id: uuid.UUID, project_id: uuid.UUID) -> Any:
        project = self.projects.get(project_id)
        if project is None:
            raise NotFoundError("project not found")

        if self.access.get_for_user_and_project(user_id, project_id) is None:
            raise PermissionDeniedError("no access to this project")
        return project

    def update(self, user_id: uuid.UUID, project_id: uuid.UUID, payload: ProjectUpdate) -> Any:
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

        role = access.role if hasattr(access, "role") else access["role"]
        if role != Role.OWNER:
            raise PermissionDeniedError("only the owner can delete this project")

        self.projects.delete(project)
