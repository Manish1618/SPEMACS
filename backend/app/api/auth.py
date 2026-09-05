from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.security import (
    accessible_cases,
    create_access_token,
    get_current_user,
    get_password_hash,
    needs_rehash,
    verify_password,
)
from app.models.database import get_db
from app.models.entities import AuditLog, User
from app.schemas.schemas import LoginRequest, Token

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


@router.post("/login", response_model=Token)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == payload.username).first()

    if user is None or not verify_password(payload.password, user.hashed_password):
        # Same message either way, so the response does not reveal which usernames exist.
        _audit(db, payload.username, "LOGIN_FAILED", request, reason="bad credentials")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        _audit(db, user.username, "LOGIN_REJECTED", request, reason="inactive account")
        raise HTTPException(status_code=400, detail="This account is not active.")

    # Upgrade legacy digests on the first successful login after the change.
    if needs_rehash(user.hashed_password):
        user.hashed_password = get_password_hash(payload.password)
        db.commit()

    _audit(db, user.username, "LOGIN_SUCCEEDED", request, role=user.role)

    return {
        "access_token": create_access_token(user.username, role=user.role),
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "badge_number": user.badge_number,
            "accessible_cases": accessible_cases(db, user),
        },
    }


@router.get("/me")
def read_profile(user=Depends(get_current_user), db: Session = Depends(get_db)):
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "badge_number": user.badge_number,
        "accessible_cases": accessible_cases(db, user),
    }
