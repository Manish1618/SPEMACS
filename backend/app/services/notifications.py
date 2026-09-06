"""Access alerting: tells the Crime Branch head who is getting into the platform.

Two separate obligations, kept separate in the code:

  * **The record.** Every access event is written to AuditLog by the caller, and
    every alert this module attempts is written to NotificationLog. That record
    exists whether or not any transport is configured.
  * **The alert.** Email carries the full stream; SMS is reserved for events
    worth interrupting someone for (lockouts, privileged sign-ins, changes to
    accounts). Both lists are configurable in .env.

Transports are adapters behind a small interface. With no credentials set, the
console adapters log the message and record it as SKIPPED, so the whole path is
exercisable on a laptop; setting SMTP_HOST or SMS_PROVIDER makes it send for
real without touching a call site.

Nothing here is allowed to break a sign-in. Every send runs through
`dispatch_access_event`, which swallows transport errors into NotificationLog,
and callers schedule it on a BackgroundTask so SMTP latency never sits in the
login response.
"""

from __future__ import annotations

import logging
import smtplib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.message import EmailMessage
from typing import Any, Dict, List, Optional, Tuple

import requests
from sqlalchemy.orm import Session

from app.core.config import settings

logger = logging.getLogger(__name__)

# Severity drives whether an event is allowed to reach SMS.
SEVERITY_INFO = "INFO"
SEVERITY_HIGH = "HIGH"


@dataclass
class AccessEvent:
    """One thing that happened, described well enough to alert on."""

    event_type: str
    actor_username: str
    summary: str
    severity: str = SEVERITY_INFO
    ip_address: str = "unknown"
    user_agent: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# --- Recipients --------------------------------------------------------------

def _recipients(db: Session) -> List[Tuple[Optional[str], Optional[str], Optional[str]]]:
    """(username, email, phone) for everyone who should hear about access events.

    Whoever holds CRIME_BRANCH_HEAD receives them, so changing the recipient is a
    normal admin action rather than a redeploy. The .env fallback exists only so
    an alert is never dropped when nobody holds the role.
    """
    from app.models.entities import User

    heads = (
        db.query(User)
        .filter(User.role == "CRIME_BRANCH_HEAD", User.is_active.is_(True))
        .all()
    )
    if heads:
        return [(u.username, u.email, u.phone_number) for u in heads]

    if settings.ALERT_FALLBACK_EMAIL or settings.ALERT_FALLBACK_PHONE:
        logger.warning(
            "No active CRIME_BRANCH_HEAD; falling back to ALERT_FALLBACK_EMAIL/PHONE."
        )
        return [(None, settings.ALERT_FALLBACK_EMAIL or None, settings.ALERT_FALLBACK_PHONE or None)]

    logger.warning(
        "Access alert for %s has no recipient: assign the CRIME_BRANCH_HEAD role "
        "to someone, or set ALERT_FALLBACK_EMAIL in backend/.env.",
        "an access event",
    )
    return []


def _event_selected(event_type: str, configured: str) -> bool:
    """Whether this event type is in a comma-separated list, or '*' for all."""
    rule = (configured or "").strip()
    if rule == "*":
        return True
    wanted = {part.strip().upper() for part in rule.split(",") if part.strip()}
    return event_type.upper() in wanted


# --- Message rendering -------------------------------------------------------

def _render(event: AccessEvent) -> Tuple[str, str, str]:
    """Returns (subject, email body, sms text)."""
    stamp = event.occurred_at.strftime("%Y-%m-%d %H:%M:%S UTC")
    flag = "[ALERT] " if event.severity == SEVERITY_HIGH else ""
    subject = f"{flag}SPEMASS access: {event.summary}"

    lines = [
        "SPEMASS Access Control notification",
        "",
        f"Event      : {event.event_type}",
        f"Summary    : {event.summary}",
        f"User       : {event.actor_username}",
        f"When       : {stamp}",
        f"IP address : {event.ip_address}",
    ]
    if event.user_agent:
        lines.append(f"Client     : {event.user_agent[:120]}")
    if event.details:
        lines.append("")
        lines.append("Details:")
        lines.extend(f"  {k}: {v}" for k, v in event.details.items())
    lines += [
        "",
        "This is an automated notification. The full access record is in the",
        "Access Log tab of the SPEMASS console.",
    ]

    # SMS is charged per segment, so keep it to the facts that matter.
    sms = (
        f"SPEMASS {event.severity}: {event.summary} "
        f"(user {event.actor_username}, IP {event.ip_address}, {stamp})"
    )[:320]

    return subject, "\n".join(lines), sms


# --- Transports --------------------------------------------------------------

def _send_email(to_address: str, subject: str, body: str) -> Tuple[str, str, Optional[str]]:
    """Returns (status, provider, error)."""
    if not settings.SMTP_HOST:
        logger.info("[access-alert:email->%s] %s\n%s", to_address, subject, body)
        return "SKIPPED", "console", "SMTP_HOST is not configured"

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.SMTP_FROM
    message["To"] = to_address
    message.set_content(body)

    try:
        with smtplib.SMTP(
            settings.SMTP_HOST, settings.SMTP_PORT, timeout=settings.SMTP_TIMEOUT_SECONDS
        ) as smtp:
            if settings.SMTP_USE_TLS:
                smtp.starttls()
            if settings.SMTP_USER:
                smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            smtp.send_message(message)
        return "SENT", "smtp", None
    except Exception as exc:  # noqa: BLE001 - an alert must never break a sign-in
        logger.error("Access alert email to %s failed: %s", to_address, exc)
        return "FAILED", "smtp", str(exc)[:500]


def _send_sms(to_number: str, text: str) -> Tuple[str, str, Optional[str]]:
    """Returns (status, provider, error)."""
    provider = settings.SMS_PROVIDER

    if provider == "console":
        logger.info("[access-alert:sms->%s] %s", to_number, text)
        return "SKIPPED", "console", "SMS_PROVIDER is 'console'"

    try:
        if provider == "twilio":
            if not (settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN):
                return "SKIPPED", provider, "Twilio credentials are not configured"
            response = requests.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{settings.TWILIO_ACCOUNT_SID}/Messages.json",
                auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN),
                data={"To": to_number, "From": settings.SMS_FROM, "Body": text},
                timeout=settings.SMS_TIMEOUT_SECONDS,
            )
        elif provider == "msg91":
            if not settings.MSG91_AUTH_KEY:
                return "SKIPPED", provider, "MSG91_AUTH_KEY is not configured"
            response = requests.post(
                "https://control.msg91.com/api/v5/flow/",
                headers={"authkey": settings.MSG91_AUTH_KEY, "Content-Type": "application/json"},
                json={
                    "template_id": settings.MSG91_TEMPLATE_ID,
                    "sender": settings.SMS_FROM,
                    "recipients": [{"mobiles": to_number.lstrip("+"), "message": text}],
                },
                timeout=settings.SMS_TIMEOUT_SECONDS,
            )
        else:
            return "FAILED", provider, f"Unknown SMS provider {provider!r}"

        if response.status_code >= 400:
            return "FAILED", provider, f"HTTP {response.status_code}: {response.text[:300]}"
        return "SENT", provider, None
    except Exception as exc:  # noqa: BLE001
        logger.error("Access alert SMS to %s failed: %s", to_number, exc)
        return "FAILED", provider, str(exc)[:500]


# --- Entry point -------------------------------------------------------------

def dispatch_access_event(db: Session, event: AccessEvent) -> List[Dict[str, str]]:
    """Alert the Crime Branch head about one access event.

    Safe to call from a BackgroundTask: it never raises, and every attempt lands
    in NotificationLog with its outcome. Returns a summary for tests and the API.
    """
    from app.models.entities import NotificationLog

    if not settings.ALERTS_ENABLED:
        return []

    subject, body, sms_text = _render(event)
    wants_email = _event_selected(event.event_type, settings.ALERT_EMAIL_EVENTS)
    wants_sms = (
        event.severity == SEVERITY_HIGH
        and _event_selected(event.event_type, settings.ALERT_SMS_EVENTS)
    )

    outcomes: List[Dict[str, str]] = []

    try:
        for username, email, phone in _recipients(db):
            if wants_email and email:
                status, provider, error = _send_email(email, subject, body)
                _record(
                    db, event, "EMAIL", email, username, subject, body,
                    status, provider, error,
                )
                outcomes.append({"channel": "EMAIL", "recipient": email, "status": status})

            if wants_sms and phone:
                status, provider, error = _send_sms(phone, sms_text)
                _record(
                    db, event, "SMS", phone, username, subject, sms_text,
                    status, provider, error,
                )
                outcomes.append({"channel": "SMS", "recipient": phone, "status": status})
            elif wants_sms and not phone:
                _record(
                    db, event, "SMS", "(none)", username, subject, sms_text,
                    "SKIPPED", settings.SMS_PROVIDER,
                    "The recipient has no phone_number set",
                )

        db.commit()
    except Exception as exc:  # noqa: BLE001 - alerting must never break the request
        logger.error("Access alert dispatch failed for %s: %s", event.event_type, exc)
        db.rollback()

    return outcomes


def _record(
    db: Session,
    event: AccessEvent,
    channel: str,
    recipient: str,
    recipient_username: Optional[str],
    subject: str,
    body: str,
    status: str,
    provider: str,
    error: Optional[str],
) -> None:
    from app.models.entities import NotificationLog

    db.add(
        NotificationLog(
            event_type=event.event_type,
            severity=event.severity,
            channel=channel,
            recipient=recipient,
            recipient_username=recipient_username,
            subject=subject[:255],
            body=body,
            status=status,
            error=error,
            provider=provider,
            actor_username=event.actor_username,
            ip_address=event.ip_address,
        )
    )


def notify_in_background(background_tasks, db_factory, event: AccessEvent) -> None:
    """Queue an alert on its own session, after the response has been sent.

    A fresh session is used because the request's session is closed by the time
    background tasks run.
    """

    def _run() -> None:
        db = db_factory()
        try:
            dispatch_access_event(db, event)
        finally:
            db.close()

    background_tasks.add_task(_run)
