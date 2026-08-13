from collections.abc import Callable

from fastapi.testclient import TestClient


def test_create_project_grants_owner_access(
    client: TestClient,
    auth_headers: Callable[[str], dict[str, str]],
) -> None:
    headers = auth_headers("owner1")
    resp = client.post(
        "/projects", json={"name": "Alpha", "description": "first project"}, headers=headers
    )
    assert resp.status_code == 201
    project_id = resp.json()["id"]

    resp = client.get("/projects", headers=headers)
    assert resp.status_code == 200
    assert any(p["id"] == project_id for p in resp.json())


def test_non_member_cannot_read_project(
    client: TestClient,
    auth_headers: Callable[[str], dict[str, str]],
) -> None:
    owner_headers = auth_headers("owner2")
    other_headers = auth_headers("stranger")
    resp = client.post("/projects", json={"name": "Beta"}, headers=owner_headers)
    project_id = resp.json()["id"]

    resp = client.get(f"/project/{project_id}/info", headers=other_headers)
    assert resp.status_code == 403


def test_only_owner_can_delete(
    client: TestClient,
    auth_headers: Callable[[str], dict[str, str]],
) -> None:
    owner_headers = auth_headers("owner3")
    resp = client.post("/projects", json={"name": "Gamma"}, headers=owner_headers)
    project_id = resp.json()["id"]

    resp = client.delete(f"/project/{project_id}", headers=owner_headers)
    assert resp.status_code == 204

    resp = client.get(f"/project/{project_id}/info", headers=owner_headers)
    assert resp.status_code == 404


def test_update_project_info(
    client: TestClient,
    auth_headers: Callable[[str], dict[str, str]],
) -> None:
    headers = auth_headers("owner4")
    resp = client.post("/projects", json={"name": "Delta"}, headers=headers)
    project_id = resp.json()["id"]

    resp = client.put(
        f"/project/{project_id}/info", json={"description": "updated"}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["description"] == "updated"
