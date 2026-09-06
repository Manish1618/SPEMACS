"""Administrator-only account provisioning.

There is no self-registration anywhere in this API: an investigator exists only
because an administrator created them. Accounts are never deleted, only
deactivated, because the audit log and chain-of-custody records reference users
by username and must stay resolvable.
"""

from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.security import (
    accessible_cases,
    get_password_hash,
    require_role,
    revoke_tokens,
    validate_password_strength,
)
from app.models.database import SessionLocal, get_db
from app.models.entities import AuditLog, RefreshSession, User, get_utc_now
from app.schemas.schemas import PasswordResetRequest, UserCreate, UserOut, UserUpdate
from app.services.notifications import SEVERITY_HIGH, AccessEvent, notify_in_background

router = APIRouter(prefix="/users", tags=["User Administration"])

# Every route here is administrator-only.
admin_only = require_role("ADMIN")


def _audit(
    db: Session,
    actor: User,
    action: str,
    target: User,
    request: Request,
    background_tasks: Optional[BackgroundTasks] = None,
    summary: str = "",
    **details,
):
    """Record the change, then alert the Crime Branch head about it.

    Account provisioning is itself an access-control event, so it goes down the
    same alerting path as sign-ins rather than only into the audit table.
    """
    db.add(
        AuditLog(
            username=actor.username,
            action=action,
            resource_type="USER",
            resource_id=target.id,
            ip_address=request.client.host if request.client else "unknown",
            details={"target_username": target.username, **details},
        )
    )
    db.commit()

    if background_tasks is None:
        return

    notify_in_background(
        background_tasks,
        SessionLocal,
        AccessEvent(
            event_type=action,
            actor_username=actor.username,
            summary=summary or f"{actor.username} performed {action} on {target.username}",
            severity=SEVERITY_HIGH,
            ip_address=request.client.host if request.client else "unknown",
            user_agent=request.headers.get("user-agent", "")[:200],
            details={"target_username": target.username, **details},
        ),
    )


def _serialise(db: Session, user: User) -> UserOut:
    from app.core.security import lockout_remaining

    return UserOut(
        id=user.id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        badge_number=user.badge_number,
        phone_number=user.phone_number,
        is_active=bool(user.is_active),
        created_at=user.created_at,
        last_login_at=user.last_login_at,
        is_locked=lockout_remaining(user) is not None,
        accessible_cases=accessible_cases(db, user),
    )


def _get_target(db: Session, user_id: str) -> User:
    target = db.query(User).filter(User.id == user_id).first()
    if target is None:
        raise HTTPException(status_code=404, detail="No such user.")
    return target


@router.get("", response_model=List[UserOut])
def list_users(db: Session = Depends(get_db), _admin: User = Depends(admin_only)):
    users = db.query(User).order_by(User.username).all()
    return [_serialise(db, u) for u in users]


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    admin: User = Depends(admin_only),
):
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(status_code=409, detail="That username is already taken.")
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=409, detail="That email address is already registered.")

    validate_password_strength(payload.password, username=payload.username)

    user = User(
        username=payload.username,
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=get_password_hash(payload.password),
        role=payload.role,
        badge_number=payload.badge_number,
        phone_number=payload.phone_number,
        is_active=True,
        password_changed_at=get_utc_now(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    _audit(
        db, admin, "CREATE_USER", user, request, background_tasks,
        summary=f"{admin.username} created account '{user.username}' as {user.role}",
        role=user.role,
    )
    return _serialise(db, user)


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: str,
    payload: UserUpdate,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    admin: User = Depends(admin_only),
):
    target = _get_target(db, user_id)
    changes = {}

    if payload.email is not None and payload.email != target.email:
        clash = db.query(User).filter(User.email == payload.email, User.id != target.id).first()
        if clash:
            raise HTTPException(status_code=409, detail="That email address is already registered.")
        changes["email"] = payload.email
        target.email = payload.email

    if payload.full_name is not None:
        changes["full_name"] = payload.full_name
        target.full_name = payload.full_name

    if payload.badge_number is not None:
        changes["badge_number"] = payload.badge_number
        target.badge_number = payload.badge_number

    if payload.phone_number is not None:
        changes["phone_number"] = payload.phone_number
        target.phone_number = payload.phone_number

    if payload.role is not None and payload.role != target.role:
        # An administrator must not remove the last administrator, or the system
        # would be left with no one able to provision accounts.
        if target.role == "ADMIN" and payload.role != "ADMIN":
            _guard_last_admin(db, target)
        changes["role"] = payload.role
        target.role = payload.role

    deactivating = payload.is_active is False and target.is_active
    if payload.is_active is not None and payload.is_active != bool(target.is_active):
        if deactivating:
            if target.id == admin.id:
                raise HTTPException(
                    status_code=400, detail="You cannot deactivate your own account."
                )
            if target.role == "ADMIN":
                _guard_last_admin(db, target)
        changes["is_active"] = payload.is_active
        target.is_active = payload.is_active

    if payload.unlock:
        changes["unlocked"] = True
        target.failed_login_count = 0
        target.locked_until = None

    if not changes:
        return _serialise(db, target)

    db.commit()

    # A demoted or deactivated user must lose the access they already hold, not
    # merely fail their next sign-in.
    if deactivating or "role" in changes:
        revoke_tokens(db, target, reason="account_changed")

    _audit(
        db, admin, "UPDATE_USER", target, request, background_tasks,
        summary=f"{admin.username} changed account '{target.username}': "
                f"{', '.join(sorted(changes))}",
        changes=changes,
    )
    db.refresh(target)
    return _serialise(db, target)


@router.post("/{user_id}/reset-password")
def reset_password(
    user_id: str,
    payload: PasswordResetRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    admin: User = Depends(admin_only),
):
    target = _get_target(db, user_id)
    validate_password_strength(payload.new_password, username=target.username)

    target.hashed_password = get_password_hash(payload.new_password)
    target.password_changed_at = get_utc_now()
    target.failed_login_count = 0
    target.locked_until = None
    db.commit()

    revoke_tokens(db, target, reason="password_reset")
    _audit(
        db, admin, "RESET_USER_PASSWORD", target, request, background_tasks,
        summary=f"{admin.username} reset the password for '{target.username}'",
    )

    return {"detail": f"Password reset for {target.username}. Their sessions were ended."}


@router.get("/{user_id}/sessions")
def list_sessions(
    user_id: str, db: Session = Depends(get_db), _admin: User = Depends(admin_only)
):
    """Live sessions for one account, so an admin can see where it is signed in."""
    target = _get_target(db, user_id)
    sessions = (
        db.query(RefreshSession)
        .filter(RefreshSession.user_id == target.id, RefreshSession.revoked_at.is_(None))
        .order_by(RefreshSession.issued_at.desc())
        .all()
    )
    return [
        {
            "id": s.id,
            "issued_at": s.issued_at,
            "expires_at": s.expires_at,
            "ip_address": s.ip_address,
            "user_agent": s.user_agent,
        }
        for s in sessions
    ]


@router.post("/{user_id}/revoke-sessions")
def revoke_sessions(
    user_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    admin: User = Depends(admin_only),
):
    target = _get_target(db, user_id)
    revoke_tokens(db, target, reason="admin_revoked")
    _audit(
        db, admin, "REVOKE_USER_SESSIONS", target, request, background_tasks,
        summary=f"{admin.username} ended all sessions for '{target.username}'",
    )
    return {"detail": f"All sessions for {target.username} have been ended."}


def _guard_last_admin(db: Session, target: User) -> None:
    remaining = (
        db.query(User)
        .filter(User.role == "ADMIN", User.is_active.is_(True), User.id != target.id)
        .count()
    )
    if remaining == 0:
        raise HTTPException(
            status_code=400,
            detail="This is the last active administrator; promote another one first.",
        )
