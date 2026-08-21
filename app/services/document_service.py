import logging
import uuid

from fastapi import UploadFile

from app.core import ALLOWED_CONTENT_TYPES, get_s3_client, settings
from app.exceptions import (
    NotFoundError,
    StorageLimitExceededError,
    UnsupportedFileTypeError,
)
from app.models import Document
from app.repositories import DocumentRepository
from app.services.project_service import ProjectService

logger = logging.getLogger(__name__)


class DocumentService:
    def __init__(self, doc_repo: DocumentRepository, project_service: ProjectService) -> None:
        self.documents = doc_repo
        self.projects = project_service
        self.s3 = get_s3_client()

    def list_for_project(self, user_id: uuid.UUID, project_id: uuid.UUID) -> list[Document]:
        self.projects.get_if_authorized(user_id, project_id)
        return self.documents.list_for_project(project_id)

    def upload(
        self, user_id: uuid.UUID, project_id: uuid.UUID, files: list[UploadFile]
    ) -> list[Document]:
        self.projects.get_if_authorized(user_id, project_id)

        staged = self._stage_files(files)
        total_new_size = sum(len(body) for _, _, body in staged)  # fixed unpacking order
        self._check_storage_limit(project_id, total_new_size)

        return self._write_batch(project_id, staged)

    def update(self, user_id: uuid.UUID, document_id: uuid.UUID, file: UploadFile) -> Document:
        doc = self._get_doc_or_404(document_id)
        project_id, size_bytes, s3_key = self._extract_doc_fields(doc)

        self.projects.get_if_authorized(user_id, project_id)

        filename, content_type, body = self._validate_and_read(file)
        size = len(body)

        self._check_storage_limit(project_id, size, existing_size=size_bytes)

        self._delete_original_and_resized(s3_key)
        new_key = f"projects/{project_id}/{uuid.uuid4()}-{filename}"
        self.s3.put_object(
            Bucket=settings.S3_BUCKET_NAME, Key=new_key, Body=body, ContentType=content_type
        )

        return self._persist_update(doc, filename, content_type, new_key, size)

    def get_download_stream(
        self, user_id: uuid.UUID, document_id: uuid.UUID
    ) -> tuple[Document, bytes]:
        doc = self._get_doc_or_404(document_id)
        project_id, _, s3_key = self._extract_doc_fields(doc)

        self.projects.get_if_authorized(user_id, project_id)
        obj = self.s3.get_object(Bucket=settings.S3_BUCKET_NAME, Key=s3_key)
        return doc, obj["Body"].read()

    def delete(self, user_id: uuid.UUID, document_id: uuid.UUID) -> None:
        doc = self._get_doc_or_404(document_id)
        project_id, _, s3_key = self._extract_doc_fields(doc)

        self.projects.get_if_authorized(user_id, project_id)
        self._delete_original_and_resized(s3_key)
        self.documents.delete(doc)

    def _get_doc_or_404(self, document_id: uuid.UUID) -> Document:
        doc = self.documents.get(document_id)
        if doc is None:
            raise NotFoundError("document not found")
        return doc

    @staticmethod
    def _extract_doc_fields(doc: Document) -> tuple[uuid.UUID, int, str]:
        return doc.project_id, doc.size_bytes, doc.s3_key

    @staticmethod
    def _validate_and_read(file: UploadFile) -> tuple[str, str, bytes]:
        content_type = file.content_type or "application/octet-stream"
        filename = file.filename or "unnamed"

        if content_type not in ALLOWED_CONTENT_TYPES:
            raise UnsupportedFileTypeError(f"unsupported content type: {content_type}")

        body = file.file.read()
        return filename, content_type, body

    def _check_storage_limit(
        self, project_id: uuid.UUID, incoming_size: int, existing_size: int = 0
    ) -> None:
        current_total = self.documents.total_size_for_project(project_id)
        limit_bytes = settings.MAX_PROJECT_STORAGE_MB * 1024 * 1024
        if current_total - existing_size + incoming_size > limit_bytes:
            raise StorageLimitExceededError("project storage limit exceeded.")

    def _stage_files(self, files: list[UploadFile]) -> list[tuple[str, str, bytes]]:
        return [self._validate_and_read(file) for file in files]

    def _write_batch(
        self, project_id: uuid.UUID, staged: list[tuple[str, str, bytes]]
    ) -> list[Document]:
        written_keys: list[str] = []
        results: list[Document] = []
        try:
            for filename, content_type, body in staged:
                key = f"projects/{project_id}/{uuid.uuid4()}-{filename}"
                self.s3.put_object(
                    Bucket=settings.S3_BUCKET_NAME,
                    Key=key,
                    Body=body,
                    ContentType=content_type,
                )
                written_keys.append(key)
                results.append(
                    self.documents.add(project_id, filename, content_type, key, len(body))
                )
        except Exception:
            logger.exception(
                "Batch upload failed mid-write for project %s; rolling back %d S3 object(s)",
                project_id,
                len(written_keys),
            )
            self._rollback_s3_objects(written_keys)
            raise

        return results

    def _rollback_s3_objects(self, keys: list[str]) -> None:
        for key in keys:
            try:
                self.s3.delete_object(Bucket=settings.S3_BUCKET_NAME, Key=key)
            except Exception:
                logger.exception("Failed to roll back S3 object %s", key)

    @staticmethod
    def _resized_key(original_key: str) -> str:
        prefix = "projects/"
        if not original_key.startswith(prefix):
            return original_key

        return "projects-resized/" + original_key[len(prefix) :]

    def _delete_original_and_resized(self, s3_key: str) -> None:
        self.s3.delete_object(Bucket=settings.S3_BUCKET_NAME, Key=s3_key)

        resized_key = self._resized_key(s3_key)
        if resized_key != s3_key:
            try:
                self.s3.delete_object(Bucket=settings.S3_BUCKET_NAME, Key=resized_key)
            except Exception:
                logger.exception("Failed to delete resized S3 object %s", resized_key)

    def _persist_update(
        self,
        doc: Document,
        filename: str,
        content_type: str,
        new_key: str,
        size: int,
    ) -> Document:
        doc.filename = filename
        doc.content_type = content_type
        doc.s3_key = new_key
        doc.size_bytes = size
        self.documents.db.commit()
        return doc
