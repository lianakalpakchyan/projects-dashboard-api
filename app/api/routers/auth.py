from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.exceptions import InvalidCredentialsError, UserAlreadyExistsError
from app.schemas import Token, UserCreate, UserLogin, UserOut
from app.services import AuthService

router = APIRouter(tags=["auth"])


@router.post("/auth", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, db: Annotated[Session, Depends(get_db)]) -> UserOut:
    service = AuthService(db)
    try:
        user = service.register(payload)
    except UserAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return UserOut.model_validate(user)


@router.post("/login", response_model=Token)
def login(payload: UserLogin, db: Annotated[Session, Depends(get_db)]) -> Token:
    service = AuthService(db)
    try:
        token = service.login(payload)
    except InvalidCredentialsError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    return Token(access_token=token)
