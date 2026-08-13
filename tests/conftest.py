from collections.abc import Callable, Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.api.deps import get_db
from app.db import Base
from app.main import app as fastapi_app


@pytest.fixture()
def db_session() -> Generator[Session]:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(bind=engine)
    session = testing_session()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def client(db_session: Session) -> Generator[TestClient]:
    def _override_get_db() -> Generator[Session]:
        yield db_session

    fastapi_app.dependency_overrides[get_db] = _override_get_db
    with TestClient(fastapi_app) as c:
        yield c
    fastapi_app.dependency_overrides.clear()


@pytest.fixture()
def auth_headers(
    client: TestClient,
) -> Callable[[str], dict[str, str]]:
    def _make(login: str = "owner") -> dict[str, str]:
        client.post(
            "/auth",
            json={"login": login, "password": "supersecret", "repeat_password": "supersecret"},
        )
        resp = client.post("/login", json={"login": login, "password": "supersecret"})
        token = resp.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    return _make
