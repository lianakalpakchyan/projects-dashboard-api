import uuid
from typing import TypeVar

from sqlalchemy.orm import Session

from app.db import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository[ModelType: Base]:
    """Generic CRUD operations, reused by every concrete repository."""

    def __init__(self, model: type[ModelType], db: Session) -> None:
        self.model = model
        self.db = db

    def get(self, id_: uuid.UUID) -> ModelType | None:
        return self.db.get(self.model, id_)

    def add(self, instance: ModelType) -> ModelType:
        self.db.add(instance)
        self.db.commit()
        self.db.refresh(instance)
        return instance

    def delete(self, instance: ModelType) -> None:
        self.db.delete(instance)
        self.db.commit()
