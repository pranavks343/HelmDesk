"""JWT access/refresh tokens, password hashing, and role-based Depends() guards."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from core.config import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

Role = Literal["customer", "agent", "admin"]

# passlib's CryptContext is unmaintained and incompatible with bcrypt>=4.1 (it probes
# `bcrypt.__about__`, removed upstream) - call the `bcrypt` library directly instead. bcrypt's
# own 72-byte secret limit is real (it silently ignores anything past byte 72), so truncate
# explicitly rather than letting a long password fail or be silently weakened.
_MAX_BCRYPT_BYTES = 72


def hash_password(password: str) -> str:
    truncated = password.encode("utf-8")[:_MAX_BCRYPT_BYTES]
    return bcrypt.hashpw(truncated, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    truncated = plain.encode("utf-8")[:_MAX_BCRYPT_BYTES]
    return bcrypt.checkpw(truncated, hashed.encode("utf-8"))


def _create_token(subject: str, role: str, expires_delta: timedelta, token_type: str) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": subject,
        "role": role,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: str, role: str) -> str:
    return _create_token(
        user_id, role, timedelta(minutes=settings.access_token_expire_minutes), "access"
    )


def create_refresh_token(user_id: str, role: str) -> str:
    return _create_token(
        user_id, role, timedelta(days=settings.refresh_token_expire_days), "refresh"
    )


class TokenData:
    def __init__(self, user_id: str, role: Role) -> None:
        self.user_id = user_id
        self.role = role


def decode_token(token: str, expected_type: str = "access") -> TokenData:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise credentials_exception from exc
    if payload.get("type") != expected_type:
        raise credentials_exception
    user_id = payload.get("sub")
    role = payload.get("role")
    if user_id is None or role is None:
        raise credentials_exception
    return TokenData(user_id=user_id, role=role)


def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> TokenData:
    return decode_token(token, expected_type="access")


CurrentUser = Annotated[TokenData, Depends(get_current_user)]


def require_role(*roles: Role):
    """Dependency factory: `Depends(require_role("agent", "admin"))`."""

    def _checker(user: CurrentUser) -> TokenData:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"requires role in {roles}, got {user.role!r}",
            )
        return user

    return _checker
