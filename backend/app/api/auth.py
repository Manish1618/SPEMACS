"""Sign-in, session lifecycle and the caller's own profile.

/login and /refresh are the only routes that mint an access token. /refresh and
/logout authenticate from the httpOnly refresh cookie and therefore carry a CSRF
check; everything else in the API authenticates from the Authorization header.
"""

from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.core import ratelimit
from app.core.config import settings
from app.core.security import (
    accessible_cases,
    burn_password_time,
    clear_failed_logins,
    clear_session_cookies,
    create_access_token,
    get_current_user,
    get_password_hash,
    issue_refresh_session,
    lockout_remaining,
    needs_rehash,
    register_failed_login,
    require_csrf,
    resolve_refresh_session,
    revoke_all_sessions,
    revoke_refresh_session,
    rotate_refresh_session,
    set_session_cookies,
    validate_password_strength,
    verify_password,
)
from app.models.database import SessionLocal, get_db
from app.models.entities import AuditLog, User, get_utc_now
from app.schemas.schemas import AuthConfig, LoginRequest, PasswordChangeRequest, Token
from app.services.notifications import (
    SEVERITY_HIGH,
    SEVERITY_INFO,
    AccessEvent,
    notify_in_background,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _audit(db: Session, username: str, action: str, request: Request, **details) -> None:
    db.add(
        AuditLog(
            username=username,
            action=action,
            resource_type="AUTH",
            ip_address=request.client.host if request.client else "unknown",
            details=details,
        )
    )
    db.commit()


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _record_access(
    db: Session,
    background_tasks: Optional[BackgroundTasks],
    username: str,
    action: str,
    request: Request,
    summary: str,
    severity: str = SEVERITY_INFO,
    alert_as: Optional[str] = None,
    **details,
) -> None:
    """Audit the event, then alert the Crime Branch head about it.

    The audit write is synchronous because it is the record of what happened.
    The alert is queued on a background task so SMTP or an SMS API can never sit
    in the caller's response, and never fail their request.
    """
    _audit(db, username, action, request, **details)

    if background_tasks is None:
        return

    notify_in_background(
        background_tasks,
        SessionLocal,
        AccessEvent(
            event_type=alert_as or action,
            actor_username=username,
            summary=summary,
            severity=severity,
            ip_address=_client_ip(request),
            user_agent=request.headers.get("user-agent", "")[:200],
            details=details,
        ),
    )


def _is_privileged(role: str) -> bool:
    privileged = {
        r.strip().upper()
        for r in settings.ALERT_PRIVILEGED_ROLES.split(",")
        if r.strip()
    }
    return (role or "").upper() in privileged


def _profile(db: Session, user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "badge_number": user.badge_number,
        "accessible_cases": accessible_cases(db, user),
    }


def _issue_session(db: Session, user: User, request: Request, response: Response) -> dict:
    """Mint an access token and attach a fresh refresh + CSRF cookie pair."""
    refresh_token = issue_refresh_session(db, user, request)
    set_session_cookies(response, refresh_token)
    return {
        "access_token": create_access_token(
            user.username, role=user.role, token_version=user.token_version or 0
        ),
        "token_type": "bearer",
        "expires_in_minutes": settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        "user": _profile(db, user),
    }


@router.get("/config", response_model=AuthConfig)
def auth_config():
    """What the login screen needs before anyone has signed in.

    Demo credentials are advertised only while DEMO_MODE is on, so a production
    build never renders them.
    """
    hints = []
    if settings.DEMO_MODE:
        from app.services.ingestion import DEFAULT_USERS

        hints = [
            {"username": spec["username"], "password": spec["password"], "role": spec["role"]}
            for spec in DEFAULT_USERS
        ]

    return {
        "demo_mode": settings.DEMO_MODE,
        "demo_credentials": hints,
        "min_password_length": settings.MIN_PASSWORD_LENGTH,
        "access_token_expire_minutes": settings.ACCESS_TOKEN_EXPIRE_MINUTES,
    }


@router.post("/login", response_model=Token)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    ip = _client_ip(request)
    allowed, retry_after = ratelimit.check(
        f"login:{ip}", settings.LOGIN_IP_MAX_ATTEMPTS, settings.LOGIN_IP_WINDOW_SECONDS
    )
    if not allowed:
        _record_access(
            db, background_tasks, payload.username, "LOGIN_THROTTLED", request,
            summary=f"Sign-in attempts throttled from {ip}",
            severity=SEVERITY_HIGH, ip=ip,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many sign-in attempts from this address. Try again shortly.",
            headers={"Retry-After": str(retry_after)},
        )

    user = db.query(User).filter(User.username == payload.username).first()

    # Same message either way, so the response does not reveal which usernames exist.
    invalid = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect username or password.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if user is None:
        # Cost the same bcrypt work as a real account, so timing does not leak
        # which usernames exist.
        burn_password_time()
        _record_access(
            db, background_tasks, payload.username, "LOGIN_FAILED", request,
            summary=f"Failed sign-in for unknown username '{payload.username}'",
            reason="unknown user",
        )
        raise invalid

    remaining = lockout_remaining(user)
    if remaining is not None:
        _record_access(
            db, background_tasks, user.username, "LOGIN_REJECTED", request,
            summary=f"Sign-in attempted on locked account '{user.username}'",
            severity=SEVERITY_HIGH, alert_as="LOGIN_LOCKED", reason="account locked",
        )
        minutes = max(1, int(remaining.total_seconds() // 60) + 1)
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=(
                f"This account is locked after {settings.LOGIN_MAX_FAILURES} failed "
                f"sign-in attempts. Try again in {minutes} minute(s), or ask an "
                "administrator to reset it."
            ),
        )

    if not verify_password(payload.password, user.hashed_password):
        locked_for = register_failed_login(db, user)
        _record_access(
            db, background_tasks, user.username, "LOGIN_FAILED", request,
            summary=(
                f"Account '{user.username}' locked after "
                f"{user.failed_login_count} failed sign-ins"
                if locked_for is not None
                else f"Failed sign-in for '{user.username}' "
                     f"(attempt {user.failed_login_count})"
            ),
            severity=SEVERITY_HIGH if locked_for is not None else SEVERITY_INFO,
            alert_as="LOGIN_LOCKED" if locked_for is not None else "LOGIN_FAILED",
            reason="bad credentials",
            failed_count=user.failed_login_count,
            locked=locked_for is not None,
        )
        if locked_for is not None:
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail=(
                    f"This account is now locked for {settings.LOGIN_LOCKOUT_MINUTES} "
                    f"minutes after {settings.LOGIN_MAX_FAILURES} failed sign-in attempts."
                ),
            )
        raise invalid

    if not user.is_active:
        _record_access(
            db, background_tasks, user.username, "LOGIN_REJECTED", request,
            summary=f"Sign-in attempted on deactivated account '{user.username}'",
            severity=SEVERITY_HIGH, reason="inactive account",
        )
        raise HTTPException(status_code=400, detail="This account is not active.")

    # Upgrade legacy digests on the first successful login after the change.
    if needs_rehash(user.hashed_password):
        user.hashed_password = get_password_hash(payload.password)
        user.password_changed_at = get_utc_now()
        db.commit()

    clear_failed_logins(db, user)
    ratelimit.reset(f"login:{ip}")
    privileged = _is_privileged(user.role)
    _record_access(
        db, background_tasks, user.username, "LOGIN_SUCCEEDED", request,
        summary=f"{user.full_name} ({user.role}) signed in",
        severity=SEVERITY_HIGH if privileged else SEVERITY_INFO,
        alert_as="PRIVILEGED_LOGIN" if privileged else "LOGIN_SUCCEEDED",
        role=user.role,
    )

    return _issue_session(db, user, request, response)


@router.post("/refresh", response_model=Token)
def refresh(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    _csrf: None = Depends(require_csrf),
):
    """Exchange the refresh cookie for a new access token, rotating the cookie."""
    raw_token = request.cookies.get(settings.REFRESH_COOKIE_NAME) or ""
    session, user = resolve_refresh_session(db, raw_token)

    rotated = rotate_refresh_session(db, session, user, request)
    set_session_cookies(response, rotated)

    return {
        "access_token": create_access_token(
            user.username, role=user.role, token_version=user.token_version or 0
        ),
        "token_type": "bearer",
        "expires_in_minutes": settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        "user": _profile(db, user),
    }


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _csrf: None = Depends(require_csrf),
):
    """End this browser session. Safe to call with an already-dead cookie."""
    raw_token = request.cookies.get(settings.REFRESH_COOKIE_NAME) or ""
    if raw_token:
        try:
            session, user = resolve_refresh_session(db, raw_token)
            revoke_refresh_session(db, session, reason="logout")
            _record_access(
                db, background_tasks, user.username, "LOGOUT", request,
                summary=f"{user.username} signed out",
            )
        except HTTPException:
            # Already expired, revoked or unknown: clearing the cookies is enough.
            pass

    clear_session_cookies(response)
    return {"detail": "Signed out."}


@router.post("/logout-all")
def logout_everywhere(
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Drop every session this user holds, on every device."""
    user.token_version = int(user.token_version or 0) + 1
    db.commit()
    revoked = revoke_all_sessions(db, user, reason="logout_all")
    _record_access(
        db, background_tasks, user.username, "LOGOUT_ALL", request,
        summary=f"{user.username} signed out of all {revoked} session(s)",
        sessions_revoked=revoked,
    )

    clear_session_cookies(response)
    return {"detail": f"Signed out of {revoked} session(s).", "sessions_revoked": revoked}


@router.post("/change-password")
def change_password(
    payload: PasswordChangeRequest,
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Change your own password. Every existing session is dropped afterwards."""
    if not verify_password(payload.current_password, user.hashed_password):
        _record_access(
            db, background_tasks, user.username, "PASSWORD_CHANGE_FAILED", request,
            summary=f"Failed password change for '{user.username}' (wrong current password)",
            severity=SEVERITY_HIGH, reason="bad current password",
        )
        raise HTTPException(status_code=400, detail="Your current password is incorrect.")

    if payload.current_password == payload.new_password:
        raise HTTPException(
            status_code=400, detail="The new password must differ from the current one."
        )

    validate_password_strength(payload.new_password, username=user.username)

    user.hashed_password = get_password_hash(payload.new_password)
    user.password_changed_at = get_utc_now()
    user.token_version = int(user.token_version or 0) + 1
    db.commit()

    revoke_all_sessions(db, user, reason="password_changed")
    _record_access(
        db, background_tasks, user.username, "PASSWORD_CHANGED", request,
        summary=f"{user.username} changed their own password",
        severity=SEVERITY_HIGH,
    )

    clear_session_cookies(response)
    return {"detail": "Password changed. Sign in again with the new password."}


@router.get("/me")
def read_profile(user=Depends(get_current_user), db: Session = Depends(get_db)):
    return _profile(db, user)
