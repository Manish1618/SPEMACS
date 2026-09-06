"""Set the SMTP app password in backend/.env without it being echoed anywhere.

    cd backend
    python set_smtp_password.py

The password is read with getpass, so it never appears on screen, in your shell
history, or in a chat transcript. It is verified against the mail server before
anything is written, so a bad paste fails here rather than silently degrading
every access alert into a FAILED row.
"""

import getpass
import re
import smtplib
import sys
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parent / ".env"
EXPECTED_LENGTH = 16  # Google issues app passwords as four groups of four.


def _read_env() -> str:
    if not ENV_PATH.exists():
        print(f"{ENV_PATH} does not exist. Copy env.example to .env first.")
        sys.exit(1)
    return ENV_PATH.read_text(encoding="utf-8")


def _setting(content: str, key: str, default: str = "") -> str:
    match = re.search(rf"^{key}=(.*)$", content, re.MULTILINE)
    return match.group(1).strip() if match else default


def _write_password(content: str, password: str) -> None:
    if re.search(r"^SMTP_PASSWORD=", content, re.MULTILINE):
        content = re.sub(
            r"^SMTP_PASSWORD=.*$", f"SMTP_PASSWORD={password}", content, flags=re.MULTILINE
        )
    else:
        content = content.rstrip("\n") + f"\nSMTP_PASSWORD={password}\n"
    ENV_PATH.write_text(content, encoding="utf-8")


def main() -> int:
    content = _read_env()
    host = _setting(content, "SMTP_HOST")
    port = int(_setting(content, "SMTP_PORT", "587"))
    user = _setting(content, "SMTP_USER")

    if not host or not user:
        print("Set SMTP_HOST and SMTP_USER in backend/.env first.")
        return 1

    print(f"Mail server : {host}:{port}")
    print(f"Account     : {user}")
    print()
    print("Paste the app password. Spaces are stripped, and nothing is displayed.")
    print("Generate one at https://myaccount.google.com/apppasswords")
    print()

    for attempt in range(3):
        password = getpass.getpass("App password: ").replace(" ", "").strip()

        if not password:
            print("  Nothing entered.\n")
            continue

        if len(password) != EXPECTED_LENGTH:
            print(
                f"  That is {len(password)} characters; Google app passwords are "
                f"{EXPECTED_LENGTH}. Check for a missing or extra character.\n"
            )
            continue

        print("  Checking against the mail server...")
        try:
            with smtplib.SMTP(host, port, timeout=20) as smtp:
                smtp.starttls()
                smtp.login(user, password)
        except smtplib.SMTPAuthenticationError as exc:
            detail = exc.smtp_error.decode(errors="replace").splitlines()[0]
            print(f"  Rejected by {host}: {exc.smtp_code} {detail}")
            print("  Nothing was written.\n")
            continue
        except Exception as exc:  # noqa: BLE001
            print(f"  Could not reach {host}: {type(exc).__name__}: {exc}")
            print("  Nothing was written.")
            return 1

        _write_password(content, password)
        print()
        print(f"  Accepted. Written to {ENV_PATH.name}.")
        print("  Restart the API, then use 'Test alert' in the Access Record tab.")
        return 0

    print("\nGave up after 3 attempts. Nothing was written.")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nCancelled. Nothing was written.")
        sys.exit(1)
