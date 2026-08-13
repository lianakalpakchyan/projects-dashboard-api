import uuid

from sqlalchemy.orm import Session

from app.exceptions import NotFoundError, PermissionDeniedError
from app.models import Project, Role
from app.repositories import AccessRepository, ProjectRepository
from app.schemas import ProjectCreate, ProjectUpdate


class ProjectService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.projects = ProjectRepository(db)
        self.access = AccessRepository(db)

    def create(self, owner_id: uuid.UUID, payload: ProjectCreate) -> Project:
        project = self.projects.add(Project(name=payload.name, description=payload.description))
        self.access.grant(owner_id, project.id, Role.OWNER)
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

    def update(self, user_id: uuid.UUID, project_id: uuid.UUID, payload: ProjectUpdate) -> Project:
        project = self.get_if_authorized(user_id, project_id)
        if payload.name is not None:
            project.name = payload.name
        if payload.description is not None:
            project.description = payload.description
        self.db.commit()
        self.db.refresh(project)
        return project

    def delete(self, user_id: uuid.UUID, project_id: uuid.UUID) -> None:
        project = self.projects.get(project_id)
        if project is None:
            raise NotFoundError("project not found")
        access = self.access.get_for_user_and_project(user_id, project_id)
        if access is None or access.role != Role.OWNER:
            raise PermissionDeniedError("only the owner can delete this project")
        self.projects.delete(project)
