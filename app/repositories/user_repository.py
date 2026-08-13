from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    def __init__(self, db: Session) -> None:
        super().__init__(User, db)

    def get_by_login(self, login: str) -> User | None:
        stmt = select(User).where(User.login == login)
        return self.db.execute(stmt).scalar_one_or_none()
