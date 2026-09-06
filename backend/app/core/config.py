"""Application settings.

Security-relevant invariants live here rather than at the call sites:

  * SECRET_KEY has no usable checked-in default. In DEMO_MODE an ephemeral key is
    generated per process (sessions drop on restart, which is fine locally); with
    DEMO_MODE off the app refuses to start without a real one, so a deployment
    can never sign tokens with a key that is public in the repository.
  * CORS is an explicit origin list, because allow_credentials with a wildcard
    origin is both invalid and unsafe.
"""

import logging
import secrets
from pathlib import Path
from typing import List, Optional

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

_BASE_DIR = Path(__file__).resolve().parent.parent.parent

# The placeholder that used to ship as the default. Anyone with the repository can
# mint valid tokens against it, so it is rejected outright outside demo mode.
_COMPROMISED_SECRET = "spemass-super-secure-jwt-secret-key-2026-audit-investigation"


class Settings(BaseSettings):
    PROJECT_NAME: str = "SPEMASS API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    # Demo mode seeds the synthetic investigator accounts and lets the login screen
    # advertise them. It must be off anywhere real.
    DEMO_MODE: bool = True

    SECRET_KEY: Optional[str] = None
    ALGORITHM: str = "HS256"

    # Short-lived: the browser holds this in memory only and silently renews it
    # from the refresh cookie.
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    REFRESH_COOKIE_NAME: str = "spemass_refresh"
    CSRF_COOKIE_NAME: str = "spemass_csrf"
    CSRF_HEADER_NAME: str = "X-CSRF-Token"
    COOKIE_SECURE: bool = False  # must be True behind HTTPS
    COOKIE_SAMESITE: str = "strict"

    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # Brute-force controls.
    LOGIN_MAX_FAILURES: int = 5
    LOGIN_LOCKOUT_MINUTES: int = 15
    LOGIN_IP_MAX_ATTEMPTS: int = 20
    LOGIN_IP_WINDOW_SECONDS: int = 300

    MIN_PASSWORD_LENGTH: int = 12

    # --- Access alerting -----------------------------------------------------
    # Every access event is recorded in the audit log regardless of these.
    # These only control what is pushed out to the Crime Branch head.
    ALERTS_ENABLED: bool = True

    # Email covers the full record; SMS is reserved for events worth interrupting
    # someone for. Widen ALERT_SMS_EVENTS to "*" to text on everything.
    ALERT_EMAIL_EVENTS: str = "*"
    ALERT_SMS_EVENTS: str = (
        "LOGIN_LOCKED,LOGIN_THROTTLED,PRIVILEGED_LOGIN,CREATE_USER,UPDATE_USER,"
        "RESET_USER_PASSWORD,REVOKE_USER_SESSIONS,UPDATE_CASE_TEAM"
    )
    # Roles whose sign-in counts as privileged, and so escalates to SMS.
    ALERT_PRIVILEGED_ROLES: str = "ADMIN,LEAD_INVESTIGATOR"

    # Used when no active user holds the CRIME_BRANCH_HEAD role, so an alert is
    # never silently dropped. Optional.
    ALERT_FALLBACK_EMAIL: str = ""
    ALERT_FALLBACK_PHONE: str = ""

    # Email transport. With SMTP_HOST unset the adapter writes the message to the
    # log and records it as SKIPPED, so the feature works end to end with no
    # account to sign up for.
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "SPEMASS Access Control <no-reply@spemass.example>"
    SMTP_USE_TLS: bool = True
    SMTP_TIMEOUT_SECONDS: int = 10

    # SMS transport: console (default, logs only), twilio, or msg91.
    SMS_PROVIDER: str = "console"
    SMS_FROM: str = ""
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    MSG91_AUTH_KEY: str = ""
    MSG91_TEMPLATE_ID: str = ""
    SMS_TIMEOUT_SECONDS: int = 10

    BASE_DIR: Path = _BASE_DIR
    DATA_DIR: Path = _BASE_DIR / "data"
    STORAGE_DIR: Path = _BASE_DIR / "storage"

    DATABASE_URL: str = f"sqlite:///{_BASE_DIR}/spemass.db"
    GEMINI_API_KEY: str = ""

    model_config = SettingsConfigDict(
        # Absolute, so the settings resolve the same however the process was started.
        env_file=str(_BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_origins(cls, value):
        """Accept CORS_ORIGINS as a comma-separated string in .env."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @model_validator(mode="after")
    def _enforce_secret_key(self) -> "Settings":
        key = (self.SECRET_KEY or "").strip()

        if not key or key == _COMPROMISED_SECRET:
            if not self.DEMO_MODE:
                raise RuntimeError(
                    "SECRET_KEY is required when DEMO_MODE is false, and must not be the "
                    "placeholder that ships in this repository. Generate one with:\n"
                    '  python -c "import secrets; print(secrets.token_urlsafe(48))"\n'
                    "and set it in backend/.env before starting the API."
                )
            self.SECRET_KEY = secrets.token_urlsafe(48)
            logger.warning(
                "DEMO_MODE: no SECRET_KEY configured, using an ephemeral key. "
                "Every session is invalidated when this process restarts. "
                "Set SECRET_KEY in backend/.env to keep sessions across restarts."
            )

        if self.SMS_PROVIDER.lower() not in ("console", "twilio", "msg91"):
            raise RuntimeError("SMS_PROVIDER must be one of: console, twilio, msg91")
        self.SMS_PROVIDER = self.SMS_PROVIDER.lower()

        if self.COOKIE_SAMESITE.lower() not in ("strict", "lax", "none"):
            raise RuntimeError("COOKIE_SAMESITE must be one of: strict, lax, none")
        self.COOKIE_SAMESITE = self.COOKIE_SAMESITE.lower()

        return self


settings = Settings()
settings.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
