import logging
import uuid

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core import get_s3_client, get_settings
from app.exceptions import (
    NotFoundError,
    StorageLimitExceededError,
    UnsupportedFileTypeError,
)
from app.models import Document
from app.repositories import DocumentRepository
from app.services.project_service import ProjectService

settings = get_settings()
logger = logging.getLogger(__name__)

ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
}


class DocumentService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.documents = DocumentRepository(db)
        self.projects = ProjectService(db)
        self.s3 = get_s3_client()

    def list_for_project(self, user_id: uuid.UUID, project_id: uuid.UUID) -> list[Document]:
        self.projects.get_if_authorized(user_id, project_id)
        return self.documents.list_for_project(project_id)

    def upload(self, user_id: uuid.UUID, project_id: uuid.UUID, file: UploadFile) -> Document:
        self.projects.get_if_authorized(user_id, project_id)
        if file.content_type not in ALLOWED_CONTENT_TYPES:
            logger.warning(
                f"File upload rejected: {file.content_type} is not an allowed document type."
            )
            raise UnsupportedFileTypeError(f"Unsupported content type: {file.content_type}")

        body = file.file.read()
        size = len(body)

        current_total = self.documents.total_size_for_project(project_id)
        limit_bytes = settings.MAX_PROJECT_STORAGE_MB * 1024 * 1024
        if current_total + size > limit_bytes:
            logger.warning(
                f"Project {project_id} storage limit of "
                f"{settings.MAX_PROJECT_STORAGE_MB}MB exceeded."
            )
            raise StorageLimitExceededError("Project storage limit exceeded.")

        key = f"projects/{project_id}/{uuid.uuid4()}-{file.filename}"
        self.s3.put_object(
            Bucket=settings.S3_BUCKET_NAME, Key=key, Body=body, ContentType=file.content_type
        )
        logger.info(f"Uploaded physical document successfully to S3 under key: {key}")

        doc = Document(
            project_id=project_id,
            filename=file.filename or "unnamed",
            content_type=file.content_type,
            s3_key=key,
            size_bytes=size,
        )
        return self.documents.add(doc)

    def get_download_stream(
        self, user_id: uuid.UUID, document_id: uuid.UUID
    ) -> tuple[Document, bytes]:
        doc = self.documents.get(document_id)
        if doc is None:
            raise NotFoundError("Document not found.")
        self.projects.get_if_authorized(user_id, doc.project_id)
        obj = self.s3.get_object(Bucket=settings.S3_BUCKET_NAME, Key=doc.s3_key)
        return doc, obj["Body"].read()

    def delete(self, user_id: uuid.UUID, document_id: uuid.UUID) -> None:
        doc = self.documents.get(document_id)
        if doc is None:
            raise NotFoundError("Document not found.")
        self.projects.get_if_authorized(user_id, doc.project_id)

        self.s3.delete_object(Bucket=settings.S3_BUCKET_NAME, Key=doc.s3_key)
        self.documents.delete(doc)
        logger.info(f"Document {document_id} removed from S3 storage and local database schema.")

    def delete_all_for_project(self, project_id: uuid.UUID) -> None:
        for doc in self.documents.list_for_project(project_id):
            self.s3.delete_object(Bucket=settings.S3_BUCKET_NAME, Key=doc.s3_key)
            self.documents.delete(doc)
        logger.info(f"Flushed all physical documents associated with project ID: {project_id}")
