import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Project, ProjectAccess


class ProjectRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, id_: uuid.UUID) -> Project | None:
        return self.db.execute(select(Project).where(Project.id == id_)).scalar_one_or_none()

    def list_for_user(self, user_id: uuid.UUID) -> list[Project]:
        stmt = (
            select(Project)
            .join(ProjectAccess, ProjectAccess.project_id == Project.id)
            .where(ProjectAccess.user_id == user_id)
            .options(selectinload(Project.documents))
        )
        return list(self.db.execute(stmt).scalars().all())

    def add(self, name: str, description: str) -> Project:
        project = Project(name=name, description=description)
        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)
        return project

    def update(self, id_: uuid.UUID, name: str | None, description: str | None) -> Project | None:
        project = self.db.execute(select(Project).where(Project.id == id_)).scalar_one_or_none()
        if project:
            if name is not None:
                project.name = name
            if description is not None:
                project.description = description
            self.db.commit()
            self.db.refresh(project)
        return project

    def delete(self, instance: Project) -> None:
        self.db.delete(instance)
        self.db.commit()
