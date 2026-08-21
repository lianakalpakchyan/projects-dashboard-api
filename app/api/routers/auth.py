from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import get_auth_service
from app.schemas import Token, UserCreate, UserLogin, UserOut
from app.services import AuthService

router = APIRouter(tags=["auth"])

AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


@router.post(
    "/auth",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
)
def create_user(
    payload: UserCreate,
    service: AuthServiceDep,
) -> UserOut:
    user = service.register(payload)
    return UserOut.model_validate(user)


@router.post(
    "/login",
    response_model=Token,
)
def login(
    payload: UserLogin,
    service: AuthServiceDep,
) -> Token:
    token = service.login(payload)
    return Token(access_token=token)
