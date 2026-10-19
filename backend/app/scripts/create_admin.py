import os
import re
import sys
from pathlib import Path

from app.auth import hash_password
from app.db.database import SessionLocal
from app.models.user import User
from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parents[3] / ".env")


def main() -> int:
    email = os.getenv("BOOTSTRAP_ADMIN_EMAIL", "").strip().lower()
    password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "")
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        print("Set BOOTSTRAP_ADMIN_EMAIL to a valid email address.", file=sys.stderr)
        return 1
    if len(password) < 12:
        print("Set BOOTSTRAP_ADMIN_PASSWORD to at least 12 characters.", file=sys.stderr)
        return 1

    db = SessionLocal()
    try:
        if db.query(User).filter(User.email == email).first():
            print(f"An account already exists for {email}.", file=sys.stderr)
            return 1
        db.add(User(email=email, password_hash=hash_password(password), role="admin"))
        db.commit()
        print(f"Created administrator account for {email}.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
