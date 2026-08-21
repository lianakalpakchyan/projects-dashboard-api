import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, id_: uuid.UUID) -> User | None:
        return self.db.execute(select(User).where(User.id == id_)).scalar_one_or_none()

    def get_by_login(self, login: str) -> User | None:
        return self.db.execute(select(User).where(User.login == login)).scalar_one_or_none()

    def add(self, user: User) -> User:
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user
