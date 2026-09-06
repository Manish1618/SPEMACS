"""The access record, and the alerts raised from it.

Two views of the same story: `/access-log` is what happened, `/notifications` is
who was told. Both are restricted to administrators and the Crime Branch head —
`require_role` already treats ADMIN as a universal override, so naming
CRIME_BRANCH_HEAD here covers both.
"""

from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import require_role
from app.models.database import get_db
from app.models.entities import AuditLog, NotificationLog, User
from app.schemas.schemas import AccessLogEntry, NotificationLogEntry
from app.services.notifications import SEVERITY_HIGH, AccessEvent, dispatch_access_event

router = APIRouter(prefix="/audit", tags=["Access Record"])

oversight_only = require_role("CRIME_BRANCH_HEAD")

# The actions that constitute "who is accessing the platform", as opposed to
# ordinary case activity.
ACCESS_ACTIONS = [
    "LOGIN_SUCCEEDED",
    "LOGIN_FAILED",
    "LOGIN_REJECTED",
    "LOGIN_THROTTLED",
    "LOGOUT",
    "LOGOUT_ALL",
    "PASSWORD_CHANGED",
    "PASSWORD_CHANGE_FAILED",
    "CREATE_USER",
    "UPDATE_USER",
    "RESET_USER_PASSWORD",
    "REVOKE_USER_SESSIONS",
    "UPDATE_CASE_TEAM",
]


@router.get("/access-log", response_model=List[AccessLogEntry])
def access_log(
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    username: Optional[str] = None,
    action: Optional[str] = None,
    since_hours: Optional[int] = Query(None, ge=1, le=24 * 90),
    db: Session = Depends(get_db),
    _viewer: User = Depends(oversight_only),
):
    """Every sign-in, sign-out and account change, newest first."""
    query = db.query(AuditLog).filter(AuditLog.action.in_(ACCESS_ACTIONS))

    if username:
        query = query.filter(AuditLog.username == username)
    if action:
        query = query.filter(AuditLog.action == action)
    if since_hours:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=since_hours)
        query = query.filter(AuditLog.timestamp >= cutoff)

    return (
        query.order_by(AuditLog.timestamp.desc()).offset(offset).limit(limit).all()
    )


@router.get("/access-log/summary")
def access_summary(
    since_hours: int = Query(24, ge=1, le=24 * 90),
    db: Session = Depends(get_db),
    _viewer: User = Depends(oversight_only),
):
    """Headline counts for the oversight dashboard."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=since_hours)
    rows = (
        db.query(AuditLog)
        .filter(AuditLog.action.in_(ACCESS_ACTIONS), AuditLog.timestamp >= cutoff)
        .all()
    )

    by_action: dict = {}
    for row in rows:
        by_action[row.action] = by_action.get(row.action, 0) + 1

    return {
        "window_hours": since_hours,
        "total_events": len(rows),
        "successful_logins": by_action.get("LOGIN_SUCCEEDED", 0),
        "failed_logins": by_action.get("LOGIN_FAILED", 0),
        "rejected_logins": by_action.get("LOGIN_REJECTED", 0),
        "account_changes": sum(
            by_action.get(a, 0)
            for a in ("CREATE_USER", "UPDATE_USER", "RESET_USER_PASSWORD", "REVOKE_USER_SESSIONS")
        ),
        "distinct_users": len({r.username for r in rows}),
        "distinct_ips": len({r.ip_address for r in rows if r.ip_address}),
        "by_action": by_action,
    }


@router.get("/notifications", response_model=List[NotificationLogEntry])
def notification_log(
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    _viewer: User = Depends(oversight_only),
):
    """What the platform tried to send, and whether it landed."""
    query = db.query(NotificationLog)
    if status_filter:
        query = query.filter(NotificationLog.status == status_filter.upper())
    return (
        query.order_by(NotificationLog.created_at.desc()).offset(offset).limit(limit).all()
    )


@router.get("/alert-config")
def alert_config(
    db: Session = Depends(get_db),
    _viewer: User = Depends(oversight_only),
):
    """Where alerts are going and whether the transports are actually live.

    Deliberately reports only whether each credential is present, never its value.
    """
    heads = (
        db.query(User)
        .filter(User.role == "CRIME_BRANCH_HEAD", User.is_active.is_(True))
        .all()
    )

    sms_ready = {
        "console": False,
        "twilio": bool(settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN),
        "msg91": bool(settings.MSG91_AUTH_KEY),
    }.get(settings.SMS_PROVIDER, False)

    return {
        "alerts_enabled": settings.ALERTS_ENABLED,
        "recipients": [
            {
                "username": u.username,
                "full_name": u.full_name,
                "email": u.email,
                "phone_number": u.phone_number,
                "sms_reachable": bool(u.phone_number),
            }
            for u in heads
        ],
        "fallback_email": settings.ALERT_FALLBACK_EMAIL or None,
        "fallback_phone": settings.ALERT_FALLBACK_PHONE or None,
        "email": {
            "configured": bool(settings.SMTP_HOST),
            "host": settings.SMTP_HOST or None,
            "port": settings.SMTP_PORT,
            "from": settings.SMTP_FROM,
            "events": settings.ALERT_EMAIL_EVENTS,
        },
        "sms": {
            "provider": settings.SMS_PROVIDER,
            "configured": sms_ready,
            "from": settings.SMS_FROM or None,
            "events": settings.ALERT_SMS_EVENTS,
        },
        "privileged_roles": settings.ALERT_PRIVILEGED_ROLES,
    }


@router.post("/test-alert")
def send_test_alert(
    request: Request,
    channel: str = Query("both", pattern="^(both|email|sms)$"),
    db: Session = Depends(get_db),
    admin: User = Depends(oversight_only),
):
    """Fire a test alert at the configured recipient, synchronously.

    Runs inline rather than in the background so the response can report exactly
    what each transport did — this is the endpoint to hit when checking that real
    delivery works.
    """
    event = AccessEvent(
        event_type="TEST_ALERT",
        actor_username=admin.username,
        summary=f"Test alert requested by {admin.username}",
        severity=SEVERITY_HIGH,
        ip_address=request.client.host if request.client else "unknown",
        user_agent=request.headers.get("user-agent", "")[:200],
        details={"channel": channel, "note": "Delivery check, not a real access event."},
    )

    # Temporarily widen the routing rules so a test always attempts the channel
    # asked for, whatever the configured event filters happen to be.
    original_email, original_sms = settings.ALERT_EMAIL_EVENTS, settings.ALERT_SMS_EVENTS
    settings.ALERT_EMAIL_EVENTS = "*" if channel in ("both", "email") else ""
    settings.ALERT_SMS_EVENTS = "*" if channel in ("both", "sms") else ""
    try:
        outcomes = dispatch_access_event(db, event)
    finally:
        settings.ALERT_EMAIL_EVENTS, settings.ALERT_SMS_EVENTS = original_email, original_sms

    if not outcomes:
        return {
            "sent": False,
            "outcomes": [],
            "hint": (
                "No recipient resolved. Give someone the CRIME_BRANCH_HEAD role "
                "(with an email, and a phone_number for SMS), or set "
                "ALERT_FALLBACK_EMAIL in backend/.env."
            ),
        }

    skipped = [o for o in outcomes if o["status"] == "SKIPPED"]
    return {
        "sent": any(o["status"] == "SENT" for o in outcomes),
        "outcomes": outcomes,
        "hint": (
            "SKIPPED means that transport has no credentials yet: set SMTP_HOST for "
            "email, or SMS_PROVIDER plus its keys for SMS, in backend/.env."
            if skipped
            else None
        ),
    }
