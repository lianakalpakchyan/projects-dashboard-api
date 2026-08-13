import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

bcrypt_any: Any = bcrypt

if not hasattr(bcrypt_any, "__about__"):
    bcrypt_version = getattr(bcrypt, "__version__", "4.0.0")
    bcrypt_any.__about__ = type("__about__", (), {"__version__": bcrypt_version})()

_original_hashpw = bcrypt_any.hashpw


def _compat_hashpw(password: bytes, salt: bytes) -> bytes:
    if isinstance(password, bytes) and len(password) > 72:
        password = password[:72]
    return _original_hashpw(password, salt)


bcrypt_any.hashpw = _compat_hashpw


settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(user_id: uuid.UUID) -> str:
    expire = datetime.now(UTC) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> uuid.UUID | None:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return uuid.UUID(payload["sub"])
    except (JWTError, KeyError, ValueError):
        return None
