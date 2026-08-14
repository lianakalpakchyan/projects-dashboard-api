from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_auth_service
from app.exceptions import InvalidCredentialsError, UserAlreadyExistsError
from app.schemas import Token, UserCreate, UserLogin, UserOut
from app.services.auth_service import AuthService

router = APIRouter(tags=["auth"])

AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


@router.post("/auth", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, service: AuthServiceDep) -> UserOut:
    try:
        user = service.register(payload)
    except UserAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return UserOut.model_validate(user)


@router.post("/login", response_model=Token)
def login(payload: UserLogin, service: AuthServiceDep) -> Token:
    try:
        token = service.login(payload)
    except InvalidCredentialsError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    return Token(access_token=token)
