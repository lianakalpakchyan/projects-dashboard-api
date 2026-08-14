import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response

from app.api.deps import get_current_user, get_document_service
from app.exceptions import (
    NotFoundError,
    PermissionDeniedError,
    StorageLimitExceededError,
    UnsupportedFileTypeError,
)
from app.schemas.document import DocumentOut
from app.services.document_service import DocumentService

router = APIRouter(tags=["documents"])

DocServiceDep = Annotated[DocumentService, Depends(get_document_service)]
CurrentUserDep = Annotated[Any, Depends(get_current_user)]


@router.get("/project/{project_id}/documents", response_model=list[DocumentOut])
def list_documents(
    project_id: uuid.UUID, current_user: CurrentUserDep, service: DocServiceDep
) -> list[DocumentOut]:
    user_id = current_user.id if hasattr(current_user, "id") else current_user["id"]
    try:
        docs = service.list_for_project(user_id, project_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return [DocumentOut.model_validate(d) for d in docs]


@router.post(
    "/project/{project_id}/documents",
    response_model=list[DocumentOut],
    status_code=status.HTTP_201_CREATED,
)
def upload_documents(
    project_id: uuid.UUID,
    files: Annotated[list[UploadFile], File(...)],
    current_user: CurrentUserDep,
    service: DocServiceDep,
) -> list[DocumentOut]:
    user_id = current_user.id if hasattr(current_user, "id") else current_user["id"]
    results = []
    try:
        for f in files:
            results.append(service.upload(user_id, project_id, f))
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except UnsupportedFileTypeError as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(exc)
        ) from exc
    except StorageLimitExceededError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc)
        ) from exc
    return [DocumentOut.model_validate(d) for d in results]


@router.put("/document/{document_id}", response_model=DocumentOut)
def update_document(
    document_id: uuid.UUID,
    file: Annotated[UploadFile, File(...)],
    current_user: CurrentUserDep,
    service: DocServiceDep,
) -> DocumentOut:
    user_id = current_user.id if hasattr(current_user, "id") else current_user["id"]
    try:
        updated = service.update(user_id, document_id, file)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except UnsupportedFileTypeError as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(exc)
        ) from exc
    except StorageLimitExceededError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc)
        ) from exc
    return DocumentOut.model_validate(updated)


@router.get("/document/{document_id}")
def download_document(
    document_id: uuid.UUID, current_user: CurrentUserDep, service: DocServiceDep
) -> Response:
    user_id = current_user.id if hasattr(current_user, "id") else current_user["id"]
    try:
        doc, content = service.get_download_stream(user_id, document_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    filename = doc.filename if hasattr(doc, "filename") else doc["filename"]
    content_type = doc.content_type if hasattr(doc, "content_type") else doc["content_type"]
    return Response(
        content=content,
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete("/document/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: uuid.UUID, current_user: CurrentUserDep, service: DocServiceDep
) -> None:
    user_id = current_user.id if hasattr(current_user, "id") else current_user["id"]
    try:
        service.delete(user_id, document_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
