"""Authentication, password hashing and case-level authorisation.

Session model
-------------
Login issues two credentials:

  * a short-lived access token (JWT, HS256) that the browser keeps in memory only
    and sends as a Bearer header, and
  * a long-lived opaque refresh token delivered in an httpOnly, SameSite cookie.

Only the SHA-256 of a refresh token is stored, refreshing always rotates it, and
replaying a rotated token revokes the whole chain - so a stolen refresh token is
usable at most once before the theft becomes visible and the session dies.

Access tokens carry the user's token_version. Raising that version (password
change, logout-everywhere, deactivation) invalidates every token already issued
without maintaining a blacklist.

Passwords are bcrypt with a per-password salt. bcrypt is used directly because
the installed passlib does not work with bcrypt 5.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import bcrypt
from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.database import get_db

# bcrypt hashes at most 72 bytes of input and errors on more.
_MAX_PASSWORD_BYTES = 72

_LEGACY_SALT = "spemass_secure_salt_2026"

# Verified against when the submitted username does not exist, so a missing
# account costs the same wall-clock time as a wrong password.
_DUMMY_HASH = bcrypt.hashpw(b"timing-equaliser", bcrypt.gensalt(rounds=12)).decode("utf-8")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: Optional[datetime]) -> Optional[datetime]:
    """SQLite hands back naive datetimes; compare them as UTC."""
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


# --- Passwords ---------------------------------------------------------------

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
    legacy = hashlib.sha256(
        f"{_LEGACY_SALT}_{plain_password}".encode("utf-8")
    ).hexdigest()
    return hmac.compare_digest(legacy, hashed_password)


def needs_rehash(hashed_password: str) -> bool:
    return not hashed_password.startswith(("$2a$", "$2b$", "$2y$"))


def burn_password_time() -> None:
    """Spend one bcrypt verification against a dummy hash.

    Called when the username does not exist so that /auth/login does not answer
    faster for accounts that are absent than for accounts with a wrong password.
    """
    bcrypt.checkpw(b"timing-equaliser-miss", _DUMMY_HASH.encode("utf-8"))


_COMMON_PASSWORDS = {
    "password", "password1", "password123", "123456", "12345678", "123456789",
    "qwerty", "qwerty123", "letmein", "welcome", "admin", "admin123",
    "iloveyou", "abc123", "monkey", "dragon", "football", "changeme",
    "passw0rd", "investigator123", "analyst123", "auditor123", "spemass",
}


def validate_password_strength(password: str, username: str = "") -> None:
    """Raise 422 with a specific reason when a password is too weak to accept."""
    problems: List[str] = []
    minimum = settings.MIN_PASSWORD_LENGTH

    if len(password) < minimum:
        problems.append(f"be at least {minimum} characters long")
    if len(password.encode("utf-8")) > _MAX_PASSWORD_BYTES:
        problems.append(f"be at most {_MAX_PASSWORD_BYTES} bytes long")
    if not any(c.islower() for c in password):
        problems.append("include a lowercase letter")
    if not any(c.isupper() for c in password):
        problems.append("include an uppercase letter")
    if not any(c.isdigit() for c in password):
        problems.append("include a digit")
    if password.lower() in _COMMON_PASSWORDS:
        problems.append("not be a commonly used password")
    if username and username.lower() in password.lower():
        problems.append("not contain the username")

    if problems:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The password must " + ", ".join(problems) + ".",
        )


# --- Account lockout ---------------------------------------------------------

def lockout_remaining(user) -> Optional[timedelta]:
    """How long this account stays locked, or None when it is not locked."""
    locked_until = _aware(user.locked_until)
    if locked_until is None:
        return None
    remaining = locked_until - _now()
    return remaining if remaining.total_seconds() > 0 else None


def register_failed_login(db: Session, user) -> Optional[timedelta]:
    """Count a failed attempt and lock the account once it hits the threshold."""
    user.failed_login_count = (user.failed_login_count or 0) + 1
    locked_for = None
    if user.failed_login_count >= settings.LOGIN_MAX_FAILURES:
        locked_for = timedelta(minutes=settings.LOGIN_LOCKOUT_MINUTES)
        user.locked_until = _now() + locked_for
    db.commit()
    return locked_for


def clear_failed_logins(db: Session, user) -> None:
    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = _now()
    db.commit()


# --- Access tokens -----------------------------------------------------------

def create_access_token(
    subject: str | Any,
    role: str = "INVESTIGATOR",
    token_version: int = 0,
    expires_delta: Optional[timedelta] = None,
) -> str:
    issued = _now()
    expire = issued + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {
        "sub": str(subject),
        "role": role,
        "typ": "access",
        "ver": token_version,
        "jti": str(uuid.uuid4()),
        "iat": issued,
        "nbf": issued,
        "exp": expire,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> Dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired credentials: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    # A refresh credential must never be accepted as an access token.
    if payload.get("typ") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="That credential is not an access token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    """Resolve the bearer token to an active user.

    There is no anonymous path. A request without a usable token is rejected,
    which is what keeps every case route behind an authenticated identity.
    """
    from app.models.entities import User

    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Sign in to obtain an access token.",
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

    # Tokens minted before a password change, deactivation or logout-everywhere
    # carry a stale version and stop working immediately.
    if int(payload.get("ver", 0)) != int(user.token_version or 0):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This session has been ended. Sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if lockout_remaining(user) is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This account is temporarily locked.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def revoke_tokens(db: Session, user, reason: str) -> None:
    """Invalidate every access token and refresh session this user holds."""
    user.token_version = int(user.token_version or 0) + 1
    db.commit()
    revoke_all_sessions(db, user, reason=reason)


# --- Refresh sessions --------------------------------------------------------

def _hash_refresh_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def issue_refresh_session(
    db: Session, user, request: Request, rotated_from: Optional[str] = None
) -> str:
    """Create a session row and return the raw token (never stored)."""
    from app.models.entities import RefreshSession

    raw_token = secrets.token_urlsafe(48)
    session = RefreshSession(
        user_id=user.id,
        token_hash=_hash_refresh_token(raw_token),
        issued_at=_now(),
        expires_at=_now() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        rotated_from=rotated_from,
        ip_address=request.client.host if request.client else "unknown",
        user_agent=(request.headers.get("user-agent") or "")[:255],
    )
    db.add(session)
    db.commit()
    return raw_token


def _revoke(db: Session, session, reason: str) -> None:
    if session.revoked_at is None:
        session.revoked_at = _now()
        session.revoked_reason = reason


def _revoke_chain(db: Session, session, reason: str) -> None:
    """Revoke a session and everything rotated out of it, in both directions."""
    from app.models.entities import RefreshSession

    seen = {session.id}
    _revoke(db, session, reason)

    # Forward: sessions this one was rotated into.
    frontier = [session.id]
    while frontier:
        children = (
            db.query(RefreshSession).filter(RefreshSession.rotated_from.in_(frontier)).all()
        )
        frontier = []
        for child in children:
            if child.id in seen:
                continue
            seen.add(child.id)
            _revoke(db, child, reason)
            frontier.append(child.id)

    # Backward: the ancestors it came from.
    cursor = session
    while cursor.rotated_from:
        parent = (
            db.query(RefreshSession).filter(RefreshSession.id == cursor.rotated_from).first()
        )
        if parent is None or parent.id in seen:
            break
        seen.add(parent.id)
        _revoke(db, parent, reason)
        cursor = parent

    db.commit()


def resolve_refresh_session(db: Session, raw_token: str) -> Tuple[Any, Any]:
    """Validate a refresh token and return (session, user).

    Presenting a token that was already rotated away means the token leaked, so
    the entire chain is revoked rather than just refused.
    """
    from app.models.entities import RefreshSession, User

    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Your session has expired. Sign in again.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not raw_token:
        raise unauthorized

    session = (
        db.query(RefreshSession)
        .filter(RefreshSession.token_hash == _hash_refresh_token(raw_token))
        .first()
    )
    if session is None:
        raise unauthorized

    if session.revoked_at is not None:
        # Reuse of a revoked/rotated token: assume compromise, kill the family.
        _revoke_chain(db, session, "reuse_detected")
        raise unauthorized

    if _aware(session.expires_at) <= _now():
        _revoke(db, session, "expired")
        db.commit()
        raise unauthorized

    user = db.query(User).filter(User.id == session.user_id).first()
    if user is None or not user.is_active:
        _revoke(db, session, "inactive_user")
        db.commit()
        raise unauthorized

    return session, user


def rotate_refresh_session(db: Session, session, user, request: Request) -> str:
    """Retire the presented session and issue its successor."""
    _revoke(db, session, "rotated")
    db.commit()
    return issue_refresh_session(db, user, request, rotated_from=session.id)


def revoke_refresh_session(db: Session, session, reason: str = "logout") -> None:
    _revoke(db, session, reason)
    db.commit()


def revoke_all_sessions(db: Session, user, reason: str = "logout_all") -> int:
    from app.models.entities import RefreshSession

    sessions = (
        db.query(RefreshSession)
        .filter(RefreshSession.user_id == user.id, RefreshSession.revoked_at.is_(None))
        .all()
    )
    for session in sessions:
        _revoke(db, session, reason)
    db.commit()
    return len(sessions)


# --- Cookies and CSRF --------------------------------------------------------

def set_session_cookies(response: Response, refresh_token: str) -> str:
    """Attach the refresh and CSRF cookies. Returns the CSRF token."""
    csrf_token = secrets.token_urlsafe(32)
    max_age = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60

    response.set_cookie(
        settings.REFRESH_COOKIE_NAME,
        refresh_token,
        max_age=max_age,
        httponly=True,  # unreadable from JavaScript, so XSS cannot exfiltrate it
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        path="/",
    )
    # Readable by the SPA on purpose: it is echoed back in a header so the server
    # can tell a same-origin request apart from a cross-site one.
    response.set_cookie(
        settings.CSRF_COOKIE_NAME,
        csrf_token,
        max_age=max_age,
        httponly=False,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        path="/",
    )
    return csrf_token


def clear_session_cookies(response: Response) -> None:
    for name in (settings.REFRESH_COOKIE_NAME, settings.CSRF_COOKIE_NAME):
        response.delete_cookie(
            name,
            path="/",
            secure=settings.COOKIE_SECURE,
            samesite=settings.COOKIE_SAMESITE,
        )


def require_csrf(request: Request) -> None:
    """Double-submit check for the two cookie-authenticated routes.

    Every other route authenticates from the Authorization header, which a
    cross-site page cannot set, so they need no CSRF token.
    """
    cookie_token = request.cookies.get(settings.CSRF_COOKIE_NAME) or ""
    header_token = request.headers.get(settings.CSRF_HEADER_NAME) or ""

    if not cookie_token or not hmac.compare_digest(cookie_token, header_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing or invalid CSRF token.",
        )


# --- Case-level authorisation ------------------------------------------------

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


require_admin = require_role("ADMIN")
