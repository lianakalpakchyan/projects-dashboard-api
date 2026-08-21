import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Document


class DocumentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(
        self, project_id: uuid.UUID, filename: str, content_type: str, s3_key: str, size_bytes: int
    ) -> Document:
        doc = Document(
            project_id=project_id,
            filename=filename,
            content_type=content_type,
            s3_key=s3_key,
            size_bytes=size_bytes,
        )
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)
        return doc

    def get(self, id_: uuid.UUID) -> Document | None:
        return self.db.execute(select(Document).where(Document.id == id_)).scalar_one_or_none()

    def delete(self, instance: Document) -> None:
        self.db.delete(instance)
        self.db.commit()

    def list_for_project(self, project_id: uuid.UUID) -> list[Document]:
        return list(
            self.db.execute(select(Document).where(Document.project_id == project_id))
            .scalars()
            .all()
        )

    def total_size_for_project(self, project_id: uuid.UUID) -> int:
        stmt = select(func.coalesce(func.sum(Document.size_bytes), 0)).where(
            Document.project_id == project_id
        )
        return int(self.db.execute(stmt).scalar_one())
