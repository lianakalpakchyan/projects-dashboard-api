import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Document
from app.repositories import BaseRepository


class DocumentRepository(BaseRepository[Document]):
    def __init__(self, db: Session) -> None:
        super().__init__(Document, db)

    def list_for_project(self, project_id: uuid.UUID) -> list[Document]:
        stmt = select(Document).where(Document.project_id == project_id)
        return list(self.db.execute(stmt).scalars().all())

    def total_size_for_project(self, project_id: uuid.UUID) -> int:
        stmt = select(func.coalesce(func.sum(Document.size_bytes), 0)).where(
            Document.project_id == project_id
        )
        return int(self.db.execute(stmt).scalar_one())
