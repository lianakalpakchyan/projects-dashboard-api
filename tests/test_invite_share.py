from collections.abc import Callable

from fastapi.testclient import TestClient


def test_owner_can_invite_existing_user(
    client: TestClient, auth_headers: Callable[[str], dict[str, str]]
) -> None:
    owner_headers = auth_headers("inv_owner")
    participant_headers = auth_headers("inv_participant")

    resp = client.post("/projects", json={"name": "Shared"}, headers=owner_headers)
    project_id = resp.json()["id"]

    # Invite user
    resp = client.post(f"/project/{project_id}/invite?user=inv_participant", headers=owner_headers)
    assert resp.status_code == 204

    # Verify participant can access project
    resp = client.get(f"/project/{project_id}/info", headers=participant_headers)
    assert resp.status_code == 200


def test_share_token_flow(
    client: TestClient, auth_headers: Callable[[str], dict[str, str]]
) -> None:
    owner_headers = auth_headers("share_owner")
    joiner_headers = auth_headers("share_joiner")

    resp = client.post("/projects", json={"name": "Share Token"}, headers=owner_headers)
    project_id = resp.json()["id"]

    # Create share link via aliased GET query
    resp = client.get(f"/project/{project_id}/share?with=joiner@example.com", headers=owner_headers)
    assert resp.status_code == 200
    join_link = resp.json()["join_link"]
    token = join_link.split("token=")[1]

    # Join project
    resp = client.post(f"/projects/join?token={token}", headers=joiner_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == project_id

    # Verify joined user has access
    resp = client.get(f"/project/{project_id}/info", headers=joiner_headers)
    assert resp.status_code == 200
