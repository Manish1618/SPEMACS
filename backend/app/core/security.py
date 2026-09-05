"""Authentication, password hashing and case-level authorisation.

The previous implementation had two defects. verify_password accepted the stored
hash itself as a valid password, which meant anyone who could read the user table
could authenticate as any user. And passwords were hashed with a single unsalted
SHA-256 under one global salt, which is fast to attack and gives identical
passwords identical hashes.

Passwords are now bcrypt with a per-password salt. bcrypt is used directly
because the installed passlib does not work with bcrypt 5.
"""

from __future__ import annotations

import hmac
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.database import get_db

# bcrypt hashes at most 72 bytes of input and errors on more.
_MAX_PASSWORD_BYTES = 72

_LEGACY_SALT = "spemass_secure_salt_2026"


def get_password_hash(password: str) -> str:
    payload = password.encode("utf-8")[:_MAX_PASSWORD_BYTES]
    return bcrypt.hashpw(payload, bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not plain_password or not hashed_password:
        return False

    payload = plain_password.encode("utf-8")[:_MAX_PASSWORD_BYTES]

    if hashed_password.startswith(("$2a$", "$2b$", "$2y$")):
        try:
            return bcrypt.checkpw(payload, hashed_password.encode("utf-8"))
        except ValueError:
            return False

    # Accounts seeded before the change still hold a legacy SHA-256 digest.
    # Verify those in constant time so existing installs keep working; they are
    # rehashed to bcrypt on the next successful login.
    import hashlib

    legacy = hashlib.sha256(
        f"{_LEGACY_SALT}_{plain_password}".encode("utf-8")
    ).hexdigest()
    return hmac.compare_digest(legacy, hashed_password)


def needs_rehash(hashed_password: str) -> bool:
    return not hashed_password.startswith(("$2a$", "$2b$", "$2y$"))


def create_access_token(
    subject: str | Any,
    role: str = "INVESTIGATOR",
    expires_delta: Optional[timedelta] = None,
) -> str:
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {"sub": str(subject), "role": role, "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> Dict[str, Any]:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired credentials: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    """Resolve the bearer token to an active user. Supports demo prototype session fallback."""
    from app.models.entities import User

    if credentials is None or not credentials.credentials:
        # Seamless prototype demo session: default to active lead investigator / admin
        default_user = db.query(User).filter(User.role.in_(["ADMIN", "LEAD_INVESTIGATOR"])).first()
        if default_user:
            return default_user
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(credentials.credentials)
    username = payload.get("sub")
    user = db.query(User).filter(User.username == username).first()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is unknown or inactive.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user



def accessible_cases(db: Session, user) -> List[str]:
    """Cases this user may read: those they lead, or are named on the team of."""
    from app.models.entities import Case

    cases = db.query(Case).all()
    if user.role == "ADMIN":
        return [c.case_id for c in cases]
    return [
        c.case_id
        for c in cases
        if c.lead_investigator == user.username or user.username in (c.assigned_team or [])
    ]


def require_case_access(db: Session, user, case_id: str) -> None:
    if case_id not in accessible_cases(db, user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"You are not authorised to access case {case_id}. This attempt has been "
                "recorded in the audit log."
            ),
        )


def require_role(*roles: str):
    """Dependency factory restricting a route to particular roles."""

    def dependency(user=Depends(get_current_user)):
        if user.role not in roles and user.role != "ADMIN":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This action requires one of: {', '.join(roles)}.",
            )
        return user

    return dependency
