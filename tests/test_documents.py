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
        f"/project/{project_id}/documents",
        headers=headers,
        files={"files": ("report.pdf", io.BytesIO(file_content), "application/pdf")},
    )
    assert resp.status_code == 201
    document_id = resp.json()[0]["id"]

    resp = client.get(f"/project/{project_id}/documents", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    resp = client.get(f"/document/{document_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.content == file_content

    resp = client.delete(f"/document/{document_id}", headers=headers)
    assert resp.status_code == 204

    resp = client.get(f"/project/{project_id}/documents", headers=headers)
    assert resp.json() == []


def test_upload_rejects_unsupported_type(
    client: TestClient, auth_headers: Callable[[str], dict[str, str]], s3_bucket: S3Client
) -> None:
    headers = auth_headers("docowner2")
    project_id = _create_project(client, headers)
    resp = client.post(
        f"/project/{project_id}/documents",
        headers=headers,
        files={"files": ("image.png", io.BytesIO(b"fake"), "image/png")},
    )
    assert resp.status_code == 415
