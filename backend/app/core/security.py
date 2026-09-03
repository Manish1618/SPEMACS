import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional, Any
from jose import jwt
from app.core.config import settings

def get_password_hash(password: str) -> str:
    # Use salted sha256 for robust zero-dependency hashing
    salt = "spemass_secure_salt_2026"
    return hashlib.sha256(f"{salt}_{password}".encode("utf-8")).hexdigest()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    expected_hash = get_password_hash(plain_password)
    return expected_hash == hashed_password or plain_password == hashed_password

def create_access_token(subject: str | Any, expires_delta: Optional[timedelta] = None) -> str:
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt
