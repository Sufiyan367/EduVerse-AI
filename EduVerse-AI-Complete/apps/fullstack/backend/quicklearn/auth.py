"""Authentication, password hashing, and token verification for EduVerse AI.

Provides cryptographically secure PBKDF2-HMAC-SHA256 password hashing
and signed bearer tokens with expiration verification using the Python standard library.
"""

from __future__ import annotations

import base64
import datetime as dt
import hashlib
import hmac
import json
import logging
import math
import threading
import os
import secrets
from typing import Any

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_config
from .crypto import _restrict_permissions
from .db.models import User
from .db.session import session_scope

log = logging.getLogger(__name__)

TOKEN_EXPIRE_HOURS = 72
_MIN_SECRET_LENGTH = 32
_secret_lock = threading.Lock()
_INSECURE_SECRETS = {
    "eduverse-ai-secret-key-salt-2026-secure-token",
    "secret",
    "password",
    "changeme",
    "12345678",
}


def get_jwt_secret() -> str:
    """Resolve the cryptographically secure JWT signing secret.
    
    1. If EDUVERSE_JWT_SECRET is set in environment, validate minimum entropy.
       In production mode, require explicit high-entropy configuration.
    2. In development/local-demo mode without environment variable, generate or load
       a persisted 64-character secret from data_dir/.jwt_secret.
    """
    env_secret = os.environ.get("EDUVERSE_JWT_SECRET")
    is_production = os.environ.get("EDUVERSE_ENV") == "production" or os.environ.get("ENVIRONMENT") == "production"

    if env_secret:
        clean_secret = env_secret.strip()
        if len(clean_secret) < _MIN_SECRET_LENGTH or clean_secret.lower() in _INSECURE_SECRETS:
            raise ValueError(
                f"EDUVERSE_JWT_SECRET must be at least {_MIN_SECRET_LENGTH} characters and cryptographically strong."
            )
        return clean_secret

    if is_production:
        raise RuntimeError(
            "Production mode requires a high-entropy EDUVERSE_JWT_SECRET environment variable "
            f"of at least {_MIN_SECRET_LENGTH} characters."
        )

    # Local development / demo fallback: persist a strong random secret per data directory
    try:
        secret_file = get_config().data_dir / ".jwt_secret"
        if secret_file.exists():
            data = secret_file.read_text(encoding="utf-8").strip()
            if len(data) >= _MIN_SECRET_LENGTH and data.lower() not in _INSECURE_SECRETS:
                return data
        
        secret_file.parent.mkdir(parents=True, exist_ok=True)
        fresh_secret = secrets.token_urlsafe(64)
        # Exclusive creation prevents concurrent first requests replacing a signing key.
        try:
            with secret_file.open('x', encoding='utf-8') as handle:
                handle.write(fresh_secret)
        except FileExistsError:
            existing = secret_file.read_text(encoding='utf-8').strip()
            if len(existing) < _MIN_SECRET_LENGTH or existing.lower() in _INSECURE_SECRETS:
                raise RuntimeError('Invalid persisted signing key; configure EDUVERSE_JWT_SECRET.')
            return existing
        _restrict_permissions(secret_file)
        return fresh_secret
    except Exception as exc:
        raise RuntimeError('Unable to load a secure persistent signing key.') from exc


def hash_password(password: str) -> str:
    """Hash password using PBKDF2-HMAC-SHA256 with a unique 16-byte cryptographic salt."""
    salt = secrets.token_bytes(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    return f"{salt.hex()}${key.hex()}"


def verify_password(password: str, hashed_password: str) -> bool:
    """Verify cleartext password against stored salt$hash."""
    try:
        salt_hex, key_hex = hashed_password.split("$", 1)
        salt = bytes.fromhex(salt_hex)
        expected_key = bytes.fromhex(key_hex)
        actual_key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
        return hmac.compare_digest(actual_key, expected_key)
    except Exception:
        return False


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64url_decode(s: str) -> bytes:
    padding = 4 - (len(s) % 4)
    if padding != 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s.encode("utf-8"))


def create_access_token(
    user_id: int,
    username: str,
    email: str,
    expires_in_hours: int = TOKEN_EXPIRE_HOURS,
) -> str:
    """Generate a tamper-proof HMAC-SHA256 signed access token."""
    now = dt.datetime.now(dt.timezone.utc)
    exp = now + dt.timedelta(hours=expires_in_hours)
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": str(user_id),
        "username": username,
        "email": email,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    encoded_header = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    encoded_payload = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{encoded_header}.{encoded_payload}".encode("utf-8")
    secret = get_jwt_secret()
    signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    encoded_signature = _b64url_encode(signature)
    return f"{encoded_header}.{encoded_payload}.{encoded_signature}"


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Validate token signature and expiration, returning decoded payload or None.
    
    Enforces strict standard claims:
    - Header must specify HS256 algorithm and JWT type.
    - Expiration claim `exp` is strictly mandatory and validated.
    - Subject `sub` must be a valid non-empty numeric user identifier.
    """
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        encoded_header, encoded_payload, encoded_sig = parts
        signing_input = f"{encoded_header}.{encoded_payload}".encode("utf-8")
        secret = get_jwt_secret()
        expected_sig = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
        actual_sig = _b64url_decode(encoded_sig)
        if not hmac.compare_digest(actual_sig, expected_sig):
            return None

        # Validate header
        header_data = json.loads(_b64url_decode(encoded_header).decode("utf-8"))
        if header_data.get("alg") != "HS256" or header_data.get("typ") != "JWT":
            return None

        # Validate payload
        payload_data = json.loads(_b64url_decode(encoded_payload).decode("utf-8"))
        sub = payload_data.get("sub")
        if not isinstance(sub, str) or not sub.isdigit() or int(sub) <= 0:
            return None

        exp = payload_data.get("exp")
        # Strictly require expiration timestamp
        if type(exp) not in (int, float) or not math.isfinite(exp):
            return None

        now_ts = dt.datetime.now(dt.timezone.utc).timestamp()
        if now_ts >= exp:
            return None  # Token expired

        return payload_data
    except Exception:
        return None


def get_token_from_header(authorization: str | None = Header(None)) -> str | None:
    """Extract bearer token from Authorization header."""
    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return None


def get_current_user(token: str | None = Depends(get_token_from_header)) -> User:
    """Dependency that ensures valid token and returns active User."""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please log in.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_access_token(token)
    if not payload or not payload.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = int(payload["sub"])
    with session_scope() as session:
        user = session.get(User, user_id)
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account inactive or not found.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        # Detach user attributes to safely use outside session
        session.expunge(user)
        return user


def get_optional_user(token: str | None = Depends(get_token_from_header)) -> User | None:
    """Optional user dependency: returns User if valid token provided.
    
    If no Authorization header was provided, returns None (public/anonymous mode).
    If an Authorization header was provided with an invalid or expired token,
    raises 401 Unauthorized so bad credentials cannot bypass access checks.
    """
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload or not payload.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        user_id = int(payload["sub"])
        with session_scope() as session:
            user = session.get(User, user_id)
            if user and user.is_active:
                session.expunge(user)
                return user
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account inactive or not found.",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication verification failed.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def seed_default_demo_user(session: Session) -> User:
    """Seed the default demo student user if not already present."""
    demo_email = "student@eduverse.ai"
    existing = session.scalar(select(User).where(User.email == demo_email))
    if existing:
        return existing

    demo_user = User(
        email=demo_email,
        username="demo_student",
        hashed_password=hash_password("demo123"),
        full_name="EduVerse Scholar",
        avatar_color="#7C3AED",
        is_active=True,
    )
    session.add(demo_user)
    session.flush()
    log.info("Default EduVerse demo user seeded: %s", demo_email)
    return demo_user
