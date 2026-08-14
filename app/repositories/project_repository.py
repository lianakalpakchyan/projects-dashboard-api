import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Project, ProjectAccess
from app.repositories.base import BaseRepository


class ProjectRepository(BaseRepository[Project]):
    def __init__(self, db: Session) -> None:
        super().__init__(Project, db)

    def list_for_user(self, user_id: uuid.UUID) -> list[Project]:
        stmt = (
            select(Project)
            .join(ProjectAccess, ProjectAccess.project_id == Project.id)
            .where(ProjectAccess.user_id == user_id)
            .options(selectinload(Project.documents))
        )
        return list(self.db.execute(stmt).scalars().all())
