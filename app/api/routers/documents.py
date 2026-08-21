import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, UploadFile, status
from fastapi.responses import Response

from app.api.deps import get_current_user, get_document_service
from app.core import resolve_user_id
from app.schemas.document import DocumentOut
from app.services.document_service import DocumentService

router = APIRouter(tags=["documents"])

DocServiceDep = Annotated[DocumentService, Depends(get_document_service)]
CurrentUserDep = Annotated[Any, Depends(get_current_user)]


@router.get(
    "/projects/{project_id}/documents",
    response_model=list[DocumentOut],
)
def list_documents(
    project_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: DocServiceDep,
) -> list[DocumentOut]:
    user_id = resolve_user_id(current_user)

    docs = service.list_for_project(user_id, project_id)

    return [DocumentOut.model_validate(d) for d in docs]


@router.post(
    "/projects/{project_id}/documents",
    response_model=list[DocumentOut],
    status_code=status.HTTP_201_CREATED,
)
def upload_documents(
    project_id: uuid.UUID,
    files: Annotated[list[UploadFile], File(...)],
    current_user: CurrentUserDep,
    service: DocServiceDep,
) -> list[DocumentOut]:
    user_id = resolve_user_id(current_user)

    results = service.upload(user_id, project_id, files)

    return [DocumentOut.model_validate(d) for d in results]


@router.put(
    "/documents/{document_id}",
    response_model=DocumentOut,
)
def update_document(
    document_id: uuid.UUID,
    file: Annotated[UploadFile, File(...)],
    current_user: CurrentUserDep,
    service: DocServiceDep,
) -> DocumentOut:
    user_id = resolve_user_id(current_user)

    updated = service.update(user_id, document_id, file)

    return DocumentOut.model_validate(updated)


@router.get("/documents/{document_id}")
def download_document(
    document_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: DocServiceDep,
) -> Response:
    user_id = resolve_user_id(current_user)

    doc, content = service.get_download_stream(user_id, document_id)

    if isinstance(doc, dict):
        filename = doc["filename"]
        content_type = doc["content_type"]
    else:
        filename = doc.filename
        content_type = doc.content_type

    return Response(
        content=content,
        media_type=content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.delete(
    "/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_document(
    document_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: DocServiceDep,
) -> None:
    user_id = resolve_user_id(current_user)

    service.delete(user_id, document_id)
