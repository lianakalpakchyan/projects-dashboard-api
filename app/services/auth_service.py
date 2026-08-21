from app.core import create_access_token, hash_password, verify_password
from app.exceptions import InvalidCredentialsError, UserAlreadyExistsError
from app.models import User
from app.repositories import UserRepository
from app.schemas import UserCreate, UserLogin


class AuthService:
    def __init__(self, user_repo: UserRepository) -> None:
        self.users = user_repo

    def register(self, payload: UserCreate) -> User:
        if self.users.get_by_login(payload.login):
            raise UserAlreadyExistsError(f"login '{payload.login}' is already taken")

        hashed = hash_password(payload.password)
        user_data = User(login=payload.login, hashed_password=hashed)

        return self.users.add(user_data)

    def login(self, payload: UserLogin) -> str:
        user = self.users.get_by_login(payload.login)

        if user is None:
            raise InvalidCredentialsError("invalid login or password")

        if not verify_password(payload.password, user.hashed_password):
            raise InvalidCredentialsError("invalid login or password")

        return create_access_token(user.id)
