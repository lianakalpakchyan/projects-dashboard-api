from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.exceptions import InvalidCredentialsError, UserAlreadyExistsError
from app.models import User
from app.repositories import UserRepository
from app.schemas import UserCreate, UserLogin


class AuthService:
    def __init__(self, db: Session) -> None:
        self.users = UserRepository(db)

    def register(self, payload: UserCreate) -> User:
        if self.users.get_by_login(payload.login):
            raise UserAlreadyExistsError(f"login '{payload.login}' is already taken")
        user = User(login=payload.login, hashed_password=hash_password(payload.password))
        return self.users.add(user)

    def login(self, payload: UserLogin) -> str:
        user = self.users.get_by_login(payload.login)
        if not user or not verify_password(payload.password, user.hashed_password):
            raise InvalidCredentialsError("invalid login or password")
        return create_access_token(user.id)
