import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.document import DocumentOut


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str = ""


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None


class ProjectInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    description: str
    created_at: datetime
    updated_at: datetime


class ProjectFullInfo(ProjectInfo):
    documents: list[DocumentOut] = []
