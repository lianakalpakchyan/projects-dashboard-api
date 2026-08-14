import uuid
from typing import Any

from app.core import create_access_token, hash_password, verify_password
from app.exceptions import InvalidCredentialsError, UserAlreadyExistsError
from app.models import User
from app.repositories import RawSQLUserRepository, UserRepositoryInterface
from app.schemas import UserCreate, UserLogin


class AuthService:
    def __init__(self, user_repo: UserRepositoryInterface) -> None:
        self.users = user_repo

    def register(self, payload: UserCreate) -> Any:
        if self.users.get_by_login(payload.login):
            raise UserAlreadyExistsError(f"login '{payload.login}' is already taken")

        hashed = hash_password(payload.password)

        user_data: dict[str, Any] | User
        if isinstance(self.users, RawSQLUserRepository):
            user_data = {"id": uuid.uuid4(), "login": payload.login, "hashed_password": hashed}
        else:
            user_data = User(login=payload.login, hashed_password=hashed)

        return self.users.add(user_data)

    def login(self, payload: UserLogin) -> str:
        user = self.users.get_by_login(payload.login)

        if user is None:
            raise InvalidCredentialsError("invalid login or password")

        if isinstance(user, dict):
            hashed_password = user["hashed_password"]
            user_id = user["id"]
        else:
            hashed_password = user.hashed_password
            user_id = user.id

        if not verify_password(payload.password, hashed_password):
            raise InvalidCredentialsError("invalid login or password")

        return create_access_token(user_id)
