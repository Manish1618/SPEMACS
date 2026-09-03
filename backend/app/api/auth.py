from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.models.database import get_db
from app.models.entities import User, AuditLog
from app.schemas.schemas import LoginRequest, Token
from app.core.security import verify_password, create_access_token

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/login", response_model=Token)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == request.username).first()
    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"}
        )
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user account")
        
    access_token = create_access_token(subject=user.username)
    
    # Audit log login
    audit = AuditLog(
        username=user.username,
        action="USER_LOGIN",
        resource_type="AUTH",
        resource_id=user.id,
        details={"role": user.role}
    )
    db.add(audit)
    db.commit()
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "badge_number": user.badge_number
        }
    }

@router.get("/me")
def get_current_user_profile(db: Session = Depends(get_db)):
    user = db.query(User).first() # Demo default
    return {
        "id": user.id if user else "u-demo",
        "username": user.username if user else "rajiv_sen",
        "full_name": user.full_name if user else "Inspector Rajiv Sen",
        "role": user.role if user else "LEAD_INVESTIGATOR",
        "badge_number": user.badge_number if user else "IND-EOW-884"
    }
