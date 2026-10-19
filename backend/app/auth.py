import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from types import SimpleNamespace

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.user import User


bearer_auth = HTTPBearer(auto_error=False)
PASSWORD_ITERATIONS = 310_000
SESSION_LIFETIME_SECONDS = 12 * 60 * 60


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS
    )
    return "$".join(
        (
            "pbkdf2_sha256",
            str(PASSWORD_ITERATIONS),
            base64.urlsafe_b64encode(salt).decode("ascii").rstrip("="),
            base64.urlsafe_b64encode(digest).decode("ascii").rstrip("="),
        )
    )


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, rounds, salt_text, digest_text = stored.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = base64.urlsafe_b64decode(salt_text + "=" * (-len(salt_text) % 4))
        expected = base64.urlsafe_b64decode(digest_text + "=" * (-len(digest_text) % 4))
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(rounds))
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def _session_secret() -> bytes:
    secret = os.getenv("SESSION_SECRET", "")
    if len(secret) < 32:
        raise HTTPException(status_code=503, detail="Set SESSION_SECRET to a random value of at least 32 characters.")
    return secret.encode("utf-8")


def _encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _decode(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def create_session_token(user_id: int) -> str:
    payload = _encode(json.dumps({"sub": user_id, "exp": int(time.time()) + SESSION_LIFETIME_SECONDS}, separators=(",", ":")).encode())
    signature = _encode(hmac.new(_session_secret(), payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{signature}"


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_auth),
    db: Session = Depends(get_db),
):
    if credentials is None:
        raise HTTPException(status_code=401, detail="Sign in to continue.", headers={"WWW-Authenticate": "Bearer"})

    configured_token = os.getenv("API_ACCESS_TOKEN", "")
    if (
        os.getenv("ALLOW_LEGACY_API_TOKEN", "false").lower() == "true"
        and len(configured_token) >= 32
        and secrets.compare_digest(credentials.credentials, configured_token)
    ):
        return SimpleNamespace(id=None, email="legacy-service-token", role="admin", is_active=True)

    try:
        payload, signature = credentials.credentials.split(".", 1)
        expected = _encode(hmac.new(_session_secret(), payload.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            raise ValueError("Invalid signature")
        claims = json.loads(_decode(payload))
        if int(claims["exp"]) <= int(time.time()):
            raise ValueError("Expired session")
        user = db.get(User, int(claims["sub"]))
        if user is None or not user.is_active:
            raise ValueError("Inactive account")
        return user
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=401, detail="Session is invalid or expired.", headers={"WWW-Authenticate": "Bearer"}) from error


def require_roles(*roles: str):
    def check_role(user=Depends(current_user)):
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="Your account does not have permission for this action.")
        return user

    return check_role


require_analyst = require_roles("admin", "analyst")
require_admin = require_roles("admin")
