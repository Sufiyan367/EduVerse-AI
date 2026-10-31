"""Authentication, password hashing, and token verification for EduVerse AI.

Provides cryptographically secure Argon2id password hashing with backward-compatible
PBKDF2-HMAC-SHA256 verification and transparent migration, signed bearer tokens with
cryptographic session tracking, and server-side token revocation.
"""

from __future__ import annotations

import base64
import datetime as dt
import hashlib
import hmac
import json
import logging
import math
import os
import secrets
import threading
import time
import uuid
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHash, VerificationError, VerifyMismatchError
from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_config
from .crypto import _restrict_permissions
from .db.models import RevokedToken, User
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

# Standard Argon2id configuration with memory and time cost parameters
_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
)

COMMON_PASSWORDS: frozenset[str] = frozenset({
    "password",
    "12345678",
    "123456789",
    "qwerty12",
    "admin123",
    "letmein12",
    "welcome1",
    "changeme",
    "iloveyou",
    "master12",
    "sunshine",
    "football",
})


def validate_password(password: str) -> None:
    """Validate password strength: minimum 8 characters and not in common passwords list."""
    if not password or len(password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long.",
        )
    if password.lower() in COMMON_PASSWORDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password is too common and easily guessable. Please choose a stronger password.",
        )


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
        try:
            with secret_file.open("x", encoding="utf-8") as handle:
                handle.write(fresh_secret)
        except FileExistsError:
            existing = secret_file.read_text(encoding="utf-8").strip()
            if len(existing) < _MIN_SECRET_LENGTH or existing.lower() in _INSECURE_SECRETS:
                raise RuntimeError("Invalid persisted signing key; configure EDUVERSE_JWT_SECRET.")
            return existing
        _restrict_permissions(secret_file)
        return fresh_secret
    except Exception as exc:
        raise RuntimeError("Unable to load a secure persistent signing key.") from exc


def hash_password(password: str) -> str:
    """Hash password using modern Argon2id with recommended cryptographic parameters."""
    return _hasher.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """Verify password supporting modern Argon2id ($argon2id$) and legacy PBKDF2-HMAC-SHA256."""
    if not hashed_password or not password:
        return False

    # Modern Argon2id verification
    if hashed_password.startswith("$argon2"):
        try:
            return _hasher.verify(hashed_password, password)
        except (VerifyMismatchError, VerificationError, InvalidHash):
            return False
        except Exception:
            return False

    # Legacy PBKDF2-HMAC-SHA256 fallback (preserves existing accounts seamlessly)
    try:
        clean = hashed_password
        if clean.startswith("$pbkdf2-sha256$"):
            clean = clean[len("$pbkdf2-sha256$"):]
        salt_hex, key_hex = clean.split("$", 1)
        salt = bytes.fromhex(salt_hex)
        expected_key = bytes.fromhex(key_hex)
        actual_key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
        return hmac.compare_digest(actual_key, expected_key)
    except Exception:
        return False


def needs_rehash(hashed_password: str) -> bool:
    """Check whether stored hash requires transparent upgrade to Argon2id."""
    if not hashed_password or not hashed_password.startswith("$argon2id$"):
        return True
    try:
        return _hasher.check_needs_rehash(hashed_password)
    except Exception:
        return True


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
    jti: str | None = None,
    token_version: int = 1,
) -> str:
    """Generate a tamper-proof HMAC-SHA256 signed access token with unique session tracking ID (jti)."""
    now = dt.datetime.now(dt.timezone.utc)
    exp = now + dt.timedelta(hours=expires_in_hours)
    token_jti = jti or uuid.uuid4().hex
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "jti": token_jti,
        "sub": str(user_id),
        "username": username,
        "email": email,
        "ver": token_version,
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


def is_token_revoked(jti: str) -> bool:
    """Check whether a session token has been revoked in persistent storage."""
    if not jti:
        return False
    try:
        with session_scope() as session:
            return session.scalar(select(RevokedToken.id).where(RevokedToken.jti == jti)) is not None
    except Exception as exc:
        log.warning("Could not verify token revocation state: %s", exc)
        return False


def revoke_session_token(token: str, user_id: int | None = None) -> None:
    """Persist a token's unique jti in revoked_tokens to invalidate it server-side."""
    payload = decode_access_token(token, verify_revocation=False)
    if not payload:
        return
    jti = payload.get("jti")
    if not jti:
        return

    uid = user_id or int(payload.get("sub", 0))
    exp_ts = payload.get("exp", 0)
    expires_at = dt.datetime.fromtimestamp(exp_ts, dt.timezone.utc)
    try:
        with session_scope() as session:
            existing = session.scalar(select(RevokedToken).where(RevokedToken.jti == jti))
            if not existing:
                session.add(RevokedToken(jti=jti, user_id=uid, expires_at=expires_at))
                session.commit()
        log.info("SECURITY_EVENT: Token revoked jti=%s user_id=%s", jti, uid)
    except Exception as exc:
        log.error("Failed to persist token revocation: %s", exc)


def revoke_all_user_sessions(user_id: int) -> None:
    """Invalidate all active sessions for a user by incrementing their token version."""
    try:
        with session_scope() as session:
            user = session.get(User, user_id)
            if user:
                user.token_version = (user.token_version or 1) + 1
                session.commit()
                log.info("SECURITY_EVENT: All sessions revoked for user_id=%s (new version=%d)", user_id, user.token_version)
    except Exception as exc:
        log.error("Failed to revoke all user sessions: %s", exc)


def decode_access_token(token: str, verify_revocation: bool = True) -> dict[str, Any] | None:
    """Validate token signature, expiration, and server-side revocation status."""
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
        if type(exp) not in (int, float) or not math.isfinite(exp):
            return None

        now_ts = dt.datetime.now(dt.timezone.utc).timestamp()
        if now_ts >= exp:
            return None  # Token expired

        # Server-side revocation verification
        if verify_revocation:
            jti = payload_data.get("jti")
            if jti and is_token_revoked(jti):
                return None  # Token explicitly revoked

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
    """Dependency ensuring valid, unrevoked bearer token and returns active User."""
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
            detail="Invalid, expired, or revoked session token. Please log in again.",
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

        # Invalidate sessions if token version does not match current user token version
        expected_version = user.token_version or 1
        token_version = payload.get("ver", 1)
        if token_version != expected_version:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session invalidated due to password change or security update. Please log in again.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        session.expunge(user)
        return user


def get_optional_user(token: str | None = Depends(get_token_from_header)) -> User | None:
    """Optional user dependency: returns User if valid unrevoked token provided."""
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload or not payload.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid, expired, or revoked session token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        user_id = int(payload["sub"])
        with session_scope() as session:
            user = session.get(User, user_id)
            if user and user.is_active:
                expected_version = user.token_version or 1
                token_version = payload.get("ver", 1)
                if token_version != expected_version:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Session invalidated due to security update.",
                        headers={"WWW-Authenticate": "Bearer"},
                    )
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


class AuthThrottler:
    """In-memory rate limiter and failed login tracker.

    Protects against brute force and credential stuffing with sliding-window
    temporary throttling (not permanent lockouts) and generic error messages.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._failed_attempts: dict[str, list[float]] = {}
        self._registrations: dict[str, list[float]] = {}
        self.max_failed = 5
        self.failed_window_sec = 900.0  # 15 minutes
        self.cooldown_sec = 60.0       # 60s cooldown if max reached
        self.max_registrations = 10
        self.registration_window_sec = 600.0  # 10 minutes

    def check_login_allowed(self, identifier: str, client_ip: str) -> None:
        now = time.time()
        keys = [f"id:{identifier.lower()}", f"ip:{client_ip}"]
        with self._lock:
            for key in keys:
                attempts = [t for t in self._failed_attempts.get(key, []) if now - t < self.failed_window_sec]
                self._failed_attempts[key] = attempts
                if len(attempts) >= self.max_failed:
                    last_attempt = max(attempts)
                    elapsed = now - last_attempt
                    if elapsed < self.cooldown_sec:
                        retry_after = int(self.cooldown_sec - elapsed) + 1
                        log.warning(
                            "SECURITY_EVENT: Login throttled for identifier=%s (ip=%s). Retry after %ds",
                            identifier,
                            client_ip,
                            retry_after,
                        )
                        raise HTTPException(
                            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                            detail=f"Too many failed login attempts. Please try again in {retry_after} seconds.",
                            headers={"Retry-After": str(retry_after)},
                        )

    def record_failed_login(self, identifier: str, client_ip: str) -> None:
        now = time.time()
        with self._lock:
            for key in [f"id:{identifier.lower()}", f"ip:{client_ip}"]:
                attempts = [t for t in self._failed_attempts.get(key, []) if now - t < self.failed_window_sec]
                attempts.append(now)
                self._failed_attempts[key] = attempts
        log.warning("SECURITY_EVENT: Failed login attempt for user=%s from ip=%s", identifier, client_ip)

    def record_successful_login(self, identifier: str, client_ip: str) -> None:
        with self._lock:
            self._failed_attempts.pop(f"id:{identifier.lower()}", None)
        log.info("SECURITY_EVENT: Successful login for user=%s from ip=%s", identifier, client_ip)

    def check_registration_allowed(self, client_ip: str) -> None:
        now = time.time()
        key = f"reg_ip:{client_ip}"
        with self._lock:
            attempts = [t for t in self._registrations.get(key, []) if now - t < self.registration_window_sec]
            self._registrations[key] = attempts
            if len(attempts) >= self.max_registrations:
                log.warning("SECURITY_EVENT: Registration rate limit reached for ip=%s", client_ip)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Registration limit reached. Please wait before creating more accounts.",
                )
            attempts.append(now)

    def reset(self) -> None:
        with self._lock:
            self._failed_attempts.clear()
            self._registrations.clear()


throttler = AuthThrottler()


def seed_default_demo_user(session: Session) -> User | None:
    """Seed the default demo student user if enabled and not in production."""
    cfg = get_config()
    if not cfg.seed_demo:
        log.info("Demo account seeding suppressed (production mode or EDUVERSE_SEED_DEMO=false).")
        return None

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
        token_version=1,
    )
    session.add(demo_user)
    session.flush()
    # Note: password is intentionally not logged
    log.info("Default EduVerse demo student created for local development (%s)", demo_email)
    return demo_user
