import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import Role
from app.models import ProjectAccess


class AccessRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_for_user_and_project(
        self, user_id: uuid.UUID, project_id: uuid.UUID
    ) -> ProjectAccess | None:
        stmt = select(ProjectAccess).where(
            ProjectAccess.user_id == user_id, ProjectAccess.project_id == project_id
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def grant(self, user_id: uuid.UUID, project_id: uuid.UUID, role: Role) -> ProjectAccess:
        access = ProjectAccess(user_id=user_id, project_id=project_id, role=role)
        self.db.add(access)
        self.db.commit()
        self.db.refresh(access)
        return access
