import logging
import uuid
from typing import Any, cast

from fastapi import UploadFile

from app.core import ALLOWED_CONTENT_TYPES, get_s3_client, settings
from app.exceptions import (
    NotFoundError,
    StorageLimitExceededError,
    UnsupportedFileTypeError,
)
from app.repositories import DocumentRepositoryInterface
from app.services.project_service import ProjectService

logger = logging.getLogger(__name__)


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

    def upload(
        self, user_id: uuid.UUID, project_id: uuid.UUID, files: list[UploadFile]
    ) -> list[Any]:
        """
        All-or-nothing batch upload.

        We read every file and validate content-type + total size *before*
        writing anything to S3 or the DB. That way a batch either fully
        succeeds or fails cleanly with nothing persisted.

        If something still goes wrong mid-write (S3 error, DB error), we
        best-effort roll back any S3 objects already written in this batch
        before re-raising.
        """
        self.projects.get_if_authorized(user_id, project_id)

        # --- Phase 1: read + validate everything up front, write nothing yet ---
        staged: list[tuple[str, bytes, str]] = []  # (filename, body, content_type)
        total_new_size = 0

        for file in files:
            content_type = file.content_type or "application/octet-stream"
            filename = file.filename or "unnamed"

            if content_type not in ALLOWED_CONTENT_TYPES:
                raise UnsupportedFileTypeError(
                    f"Unsupported content type: {content_type} for file '{filename}'"
                )

            body = file.file.read()
            staged.append((filename, body, content_type))
            total_new_size += len(body)

        current_total = self.documents.total_size_for_project(project_id)
        limit_bytes = settings.MAX_PROJECT_STORAGE_MB * 1024 * 1024
        if current_total + total_new_size > limit_bytes:
            raise StorageLimitExceededError("Project storage limit exceeded.")

        # --- Phase 2: everything validated, now actually write it ---
        written_keys: list[str] = []
        results: list[Any] = []
        try:
            for filename, body, content_type in staged:
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
            for key in written_keys:
                try:
                    self.s3.delete_object(Bucket=settings.S3_BUCKET_NAME, Key=key)
                except Exception:
                    logger.exception("Failed to roll back S3 object %s", key)
            raise

        return results

    def update(self, user_id: uuid.UUID, document_id: uuid.UUID, file: UploadFile) -> Any:
        doc = self.documents.get(document_id)
        if doc is None:
            raise NotFoundError("document not found")

        if isinstance(doc, dict):
            project_id = doc["project_id"]
            size_bytes = doc["size_bytes"]
            s3_key = doc["s3_key"]
        else:
            project_id = doc.project_id
            size_bytes = doc.size_bytes
            s3_key = doc.s3_key

        self.projects.get_if_authorized(user_id, project_id)

        content_type = file.content_type or "application/octet-stream"
        filename = file.filename or "unnamed"

        if content_type not in ALLOWED_CONTENT_TYPES:
            raise UnsupportedFileTypeError(f"Unsupported content type: {content_type}")

        body = file.file.read()
        size = len(body)

        current_total = self.documents.total_size_for_project(project_id)
        limit_bytes = settings.MAX_PROJECT_STORAGE_MB * 1024 * 1024
        if current_total - size_bytes + size > limit_bytes:
            raise StorageLimitExceededError("Project storage limit exceeded.")

        self.s3.delete_object(Bucket=settings.S3_BUCKET_NAME, Key=s3_key)
        new_key = f"projects/{project_id}/{uuid.uuid4()}-{filename}"
        self.s3.put_object(
            Bucket=settings.S3_BUCKET_NAME, Key=new_key, Body=body, ContentType=content_type
        )

        if not isinstance(doc, dict):
            doc.filename = filename
            doc.content_type = content_type
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
                        filename,
                        content_type,
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

        if isinstance(doc, dict):
            project_id = doc["project_id"]
            s3_key = doc["s3_key"]
        else:
            project_id = doc.project_id
            s3_key = doc.s3_key

        self.projects.get_if_authorized(user_id, project_id)
        obj = self.s3.get_object(Bucket=settings.S3_BUCKET_NAME, Key=s3_key)
        return doc, obj["Body"].read()

    def delete(self, user_id: uuid.UUID, document_id: uuid.UUID) -> None:
        doc = self.documents.get(document_id)
        if doc is None:
            raise NotFoundError("document not found")

        if isinstance(doc, dict):
            project_id = doc["project_id"]
            s3_key = doc["s3_key"]
        else:
            project_id = doc.project_id
            s3_key = doc.s3_key

        self.projects.get_if_authorized(user_id, project_id)
        self.s3.delete_object(Bucket=settings.S3_BUCKET_NAME, Key=s3_key)
        self.documents.delete(doc)
