from collections.abc import Callable, Generator, Iterator

import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from types_boto3_s3.client import S3Client

import app.models  # noqa: F401
from app.api.deps import get_db
from app.core.config import get_settings
from app.db import Base
from app.main import app as fastapi_app


@pytest.fixture(name="db_session")
def db_session_fixture() -> Generator[Session]:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(name="client")
def client_fixture(db_session: Session) -> Generator[TestClient]:
    def _override_get_db() -> Generator[Session]:
        yield db_session

    fastapi_app.dependency_overrides[get_db] = _override_get_db
    with TestClient(fastapi_app) as c:
        yield c
    fastapi_app.dependency_overrides.clear()


@pytest.fixture(name="auth_headers")
def auth_headers_fixture(client: TestClient) -> Callable[[str], dict[str, str]]:
    def _make(login: str = "user") -> dict[str, str]:
        client.post(
            "/auth",
            json={"login": login, "password": "supersecret", "repeat_password": "supersecret"},
        )
        resp = client.post("/login", json={"login": login, "password": "supersecret"})
        token = resp.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    return _make


@pytest.fixture()
def s3_bucket() -> Iterator[S3Client]:
    with mock_aws():
        settings = get_settings()
        client = boto3.client("s3", region_name=settings.AWS_REGION)

        if settings.AWS_REGION == "us-east-1":
            client.create_bucket(Bucket=settings.S3_BUCKET_NAME)
        else:
            client.create_bucket(
                Bucket=settings.S3_BUCKET_NAME,
                CreateBucketConfiguration={"LocationConstraint": settings.AWS_REGION},
            )

        yield client
