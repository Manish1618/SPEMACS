"""Create the first administrator account.

A deployment with DEMO_MODE off seeds no users at all, so this is how it gets its
first sign-in. Every account after this one is created through the /users API by
an administrator.

    cd backend
    python create_admin.py

The password is read with getpass, so it never appears in the shell history or
the process list.
"""

import getpass
import sys

from fastapi import HTTPException

from app.core.security import get_password_hash, validate_password_strength
from app.models.database import SessionLocal, run_migrations
from app.models.entities import User, get_utc_now


def _prompt(label: str, *, required: bool = True) -> str:
    while True:
        value = input(f"{label}: ").strip()
        if value or not required:
            return value
        print("  This field is required.")


def main() -> int:
    run_migrations()

    db = SessionLocal()
    try:
        print("Create a SPEMASS administrator account.\n")

        username = _prompt("Username")
        if db.query(User).filter(User.username == username).first():
            print(f"\nA user named {username!r} already exists.")
            return 1

        email = _prompt("Email")
        if db.query(User).filter(User.email == email).first():
            print(f"\n{email!r} is already registered.")
            return 1

        full_name = _prompt("Full name")
        badge_number = _prompt("Badge number (optional)", required=False) or None

        while True:
            password = getpass.getpass("Password: ")
            confirm = getpass.getpass("Confirm password: ")
            if password != confirm:
                print("  The passwords do not match.\n")
                continue
            try:
                validate_password_strength(password, username=username)
            except HTTPException as exc:
                print(f"  {exc.detail}\n")
                continue
            break

        db.add(
            User(
                username=username,
                email=email,
                full_name=full_name,
                hashed_password=get_password_hash(password),
                role="ADMIN",
                badge_number=badge_number,
                is_active=True,
                password_changed_at=get_utc_now(),
            )
        )
        db.commit()

        print(f"\nAdministrator {username!r} created. Sign in at the SPEMASS login screen.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nCancelled.")
        sys.exit(1)
