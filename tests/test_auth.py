from fastapi.testclient import TestClient


def test_register_and_login_success(client: TestClient) -> None:
    resp = client.post(
        "/auth",
        json={"login": "alice", "password": "supersecret", "repeat_password": "supersecret"},
    )
    assert resp.status_code == 201
    assert resp.json()["login"] == "alice"

    resp = client.post("/login", json={"login": "alice", "password": "supersecret"})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_register_duplicate_login_returns_409(client: TestClient) -> None:
    payload = {"login": "bob", "password": "supersecret", "repeat_password": "supersecret"}
    client.post("/auth", json=payload)
    resp = client.post("/auth", json=payload)
    assert resp.status_code == 409


def test_login_wrong_password_returns_401(client: TestClient) -> None:
    client.post(
        "/auth",
        json={"login": "carol", "password": "supersecret", "repeat_password": "supersecret"},
    )
    resp = client.post("/login", json={"login": "carol", "password": "wrong"})
    assert resp.status_code == 401


def test_password_mismatch_returns_422(client: TestClient) -> None:
    resp = client.post(
        "/auth", json={"login": "dave", "password": "abcdefgh", "repeat_password": "different"}
    )
    assert resp.status_code == 422
