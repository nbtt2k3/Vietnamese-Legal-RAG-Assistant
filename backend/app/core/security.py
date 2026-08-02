from datetime import datetime, timedelta, timezone
from typing import Optional
import warnings

import bcrypt
from jose import jwt

from app.core.config import settings


def validate_password_policy(password: str) -> None:
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters")
    if len(password.encode("utf-8")) > 72:
        raise ValueError("Password must not exceed 72 bytes")
    if password.strip() != password:
        raise ValueError("Password must not start or end with whitespace")
    if password.lower() in {"password", "password123", "12345678", "phase0-password"}:
        raise ValueError("Password is too common")
    if password.isdigit() or password.isalpha():
        raise ValueError("Password must contain a mix of letters and non-letters")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    password_bytes = plain_password.encode("utf-8")[:72]
    return bcrypt.checkpw(password_bytes, hashed_password.encode("utf-8"))


def get_password_hash(password: str) -> str:
    password_bytes = password.encode("utf-8")[:72]
    return bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("utf-8")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> dict:
    """Decode a token while isolating python-jose's legacy datetime warning."""
    # python-jose 3.3.0 still calls datetime.utcnow() internally during decode.
    # Keep this narrowly scoped so unrelated deprecation warnings remain visible.
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=DeprecationWarning, module=r"jose\.jwt")
        return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
