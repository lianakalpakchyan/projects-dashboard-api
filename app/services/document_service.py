import logging
import uuid
from typing import Any, cast

from fastapi import UploadFile

from app.core import get_s3_client, get_settings
from app.exceptions import (
    NotFoundError,
    StorageLimitExceededError,
    UnsupportedFileTypeError,
)
from app.repositories.interfaces import DocumentRepositoryInterface
from app.services.project_service import ProjectService

settings = get_settings()
logger = logging.getLogger(__name__)

ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


class DocumentService:
    def __init__(
        self, doc_repo: DocumentRepositoryInterface, project_service: ProjectService
    ) -> None:
        self.documents = doc_repo
        self.projects = project_service
        self.s3 = get_s3_client()

    def list_for_project(self, user_id: uuid.UUID, project_id: uuid.UUID) -> list[Any]:
        self.projects.get_if_authorized(user_id, project_id)
        return self.documents.list_for_project(project_id)

    def upload(self, user_id: uuid.UUID, project_id: uuid.UUID, file: UploadFile) -> Any:
        self.projects.get_if_authorized(user_id, project_id)
        if file.content_type not in ALLOWED_CONTENT_TYPES:
            raise UnsupportedFileTypeError(f"Unsupported content type: {file.content_type}")

        body = file.file.read()
        size = len(body)

        current_total = self.documents.total_size_for_project(project_id)
        limit_bytes = settings.MAX_PROJECT_STORAGE_MB * 1024 * 1024
        if current_total + size > limit_bytes:
            raise StorageLimitExceededError("Project storage limit exceeded.")

        key = f"projects/{project_id}/{uuid.uuid4()}-{file.filename}"
        self.s3.put_object(
            Bucket=settings.S3_BUCKET_NAME, Key=key, Body=body, ContentType=file.content_type
        )

        return self.documents.add(
            project_id, file.filename or "unnamed", file.content_type, key, size
        )

    def update(self, user_id: uuid.UUID, document_id: uuid.UUID, file: UploadFile) -> Any:
        doc = self.documents.get(document_id)
        if doc is None:
            raise NotFoundError("document not found")

        project_id = doc.project_id if hasattr(doc, "project_id") else doc["project_id"]
        size_bytes = doc.size_bytes if hasattr(doc, "size_bytes") else doc["size_bytes"]
        s3_key = doc.s3_key if hasattr(doc, "s3_key") else doc["s3_key"]

        self.projects.get_if_authorized(user_id, project_id)
        if file.content_type not in ALLOWED_CONTENT_TYPES:
            raise UnsupportedFileTypeError(f"Unsupported content type: {file.content_type}")

        body = file.file.read()
        size = len(body)

        current_total = self.documents.total_size_for_project(project_id)
        limit_bytes = settings.MAX_PROJECT_STORAGE_MB * 1024 * 1024
        if current_total - size_bytes + size > limit_bytes:
            raise StorageLimitExceededError("Project storage limit exceeded.")

        self.s3.delete_object(Bucket=settings.S3_BUCKET_NAME, Key=s3_key)
        new_key = f"projects/{project_id}/{uuid.uuid4()}-{file.filename}"
        self.s3.put_object(
            Bucket=settings.S3_BUCKET_NAME, Key=new_key, Body=body, ContentType=file.content_type
        )

        if hasattr(doc, "id"):
            doc.filename = file.filename or "unnamed"
            doc.content_type = file.content_type
            doc.s3_key = new_key
            doc.size_bytes = size
            orm_repo = cast(Any, self.documents)
            orm_repo.db.commit()
            return doc
        else:
            raw_repo = cast(Any, self.documents)
            with raw_repo.conn.cursor() as cur:
                cur.execute(
                    "UPDATE documents SET filename = %s, content_type = %s, "
                    "s3_key = %s, size_bytes = %s "
                    "WHERE id = %s RETURNING id, filename, content_type, "
                    "size_bytes, uploaded_at",
                    (
                        file.filename or "unnamed",
                        file.content_type,
                        new_key,
                        size,
                        str(document_id),
                    ),
                )
                row = cur.fetchone()
                raw_repo.conn.commit()
                return {
                    "id": uuid.UUID(row[0]),
                    "filename": row[1],
                    "content_type": row[2],
                    "size_bytes": row[3],
                    "uploaded_at": row[4],
                }

    def get_download_stream(self, user_id: uuid.UUID, document_id: uuid.UUID) -> tuple[Any, bytes]:
        doc = self.documents.get(document_id)
        if doc is None:
            raise NotFoundError("document not found")
        project_id = doc.project_id if hasattr(doc, "project_id") else doc["project_id"]
        s3_key = doc.s3_key if hasattr(doc, "s3_key") else doc["s3_key"]

        self.projects.get_if_authorized(user_id, project_id)
        obj = self.s3.get_object(Bucket=settings.S3_BUCKET_NAME, Key=s3_key)
        return doc, obj["Body"].read()

    def delete(self, user_id: uuid.UUID, document_id: uuid.UUID) -> None:
        doc = self.documents.get(document_id)
        if doc is None:
            raise NotFoundError("document not found")
        project_id = doc.project_id if hasattr(doc, "project_id") else doc["project_id"]
        s3_key = doc.s3_key if hasattr(doc, "s3_key") else doc["s3_key"]

        self.projects.get_if_authorized(user_id, project_id)
        self.s3.delete_object(Bucket=settings.S3_BUCKET_NAME, Key=s3_key)
        self.documents.delete(doc)
