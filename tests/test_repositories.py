from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories import UserRepository


def test_base_repository_add_and_get(db_session: Session) -> None:
    repo = UserRepository(db_session)
    user = User(login="alice", hashed_password="x")
    saved = repo.add(user)

    fetched = repo.get(saved.id)
    assert fetched is not None
    assert fetched.login == "alice"
