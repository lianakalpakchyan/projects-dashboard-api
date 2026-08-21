import io
from collections.abc import Callable

from fastapi.testclient import TestClient
from types_boto3_s3.client import S3Client


def _create_project(client: TestClient, headers: dict[str, str], name: str = "Docs Project") -> str:
    resp = client.post("/projects", json={"name": name}, headers=headers)
    return resp.json()["id"]


def test_upload_list_download_delete_document(
    client: TestClient, auth_headers: Callable[[str], dict[str, str]], s3_bucket: S3Client
) -> None:
    headers = auth_headers("docowner")
    project_id = _create_project(client, headers)

    file_content = b"%PDF-1.4 fake pdf content"
    resp = client.post(
        f"/projects/{project_id}/documents",
        headers=headers,
        files={"files": ("report.pdf", io.BytesIO(file_content), "application/pdf")},
    )
    assert resp.status_code == 201
    document_id = resp.json()[0]["id"]

    resp = client.get(f"/projects/{project_id}/documents", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    resp = client.get(f"/documents/{document_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.content == file_content

    # Validate physical update endpoint (PUT /documents/)
    replacement_content = b"%PDF-1.4 replacement pdf payload"
    resp = client.put(
        f"/documents/{document_id}",
        headers=headers,
        files={"file": ("updated_report.pdf", io.BytesIO(replacement_content), "application/pdf")},
    )
    assert resp.status_code == 200
    assert resp.json()["filename"] == "updated_report.pdf"

    resp = client.get(f"/documents/{document_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.content == replacement_content

    resp = client.delete(f"/documents/{document_id}", headers=headers)
    assert resp.status_code == 204

    resp = client.get(f"/projects/{project_id}/documents", headers=headers)
    assert resp.json() == []


def test_upload_accepts_supported_images(
    client: TestClient, auth_headers: Callable[[str], dict[str, str]], s3_bucket: S3Client
) -> None:
    headers = auth_headers("imageowner")
    project_id = _create_project(client, headers)

    # Verify that PNG images are successfully uploaded
    image_content = b"\x89PNG\r\n\x1a\nfake-png-headers"
    resp = client.post(
        f"/projects/{project_id}/documents",
        headers=headers,
        files={"files": ("avatar.png", io.BytesIO(image_content), "image/png")},
    )
    assert resp.status_code == 201
    assert resp.json()[0]["filename"] == "avatar.png"


def test_upload_rejects_unsupported_type(
    client: TestClient, auth_headers: Callable[[str], dict[str, str]], s3_bucket: S3Client
) -> None:
    headers = auth_headers("docowner2")
    project_id = _create_project(client, headers)

    # Verify that genuinely unsupported types like plain text are rejected
    resp = client.post(
        f"/projects/{project_id}/documents",
        headers=headers,
        files={"files": ("notes.txt", io.BytesIO(b"fake text file"), "text/plain")},
    )
    assert resp.status_code == 415
