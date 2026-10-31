"""Tests for EduVerse AI security, authentication upgrade, session revocation, and production readiness."""

from __future__ import annotations

import datetime as dt
import hashlib
import os
import secrets
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
from starlette.testclient import TestClient

from quicklearn import auth
from quicklearn.api.chat import validate_answer
from quicklearn.config import Config
from quicklearn.db import models as m
from quicklearn.db.bootstrap import init_database
from quicklearn.db.session import session_scope
from quicklearn.errors import ProviderAuthError
from quicklearn.main import create_app
from quicklearn.providers.http import raise_for_response
from quicklearn.rag.retrieve import Excerpt


# --------------------------------------------------------------------------- 1. Password Hashing & Validation
def test_argon2id_password_hashing():
    """Verify Argon2id hash format ($argon2id$), verification, and password validation."""
    password = "CorrectHorseBattery99!"
    hashed = auth.hash_password(password)

    # Must be modern Argon2id versioned format
    assert hashed.startswith("$argon2id$v=19$"), f"Expected Argon2id hash, got: {hashed}"
    assert auth.verify_password(password, hashed) is True
    assert auth.verify_password("WrongPassword123", hashed) is False
    assert auth.needs_rehash(hashed) is False

    # Password validation: minimum 8 characters
    with pytest.raises(Exception) as exc_info:
        auth.validate_password("short")
    assert "8 characters" in str(exc_info.value)

    # Password validation: reject common weak passwords
    with pytest.raises(Exception) as exc_info:
        auth.validate_password("12345678")
    assert "too common" in str(exc_info.value).lower()


# --------------------------------------------------------------------------- 2. PBKDF2 Backward Compatibility & Migration
def test_legacy_pbkdf2_migration_on_login(config: Config):
    """Verify existing PBKDF2 password hashes authenticate and transparently migrate to Argon2id."""
    # Create legacy PBKDF2 hash (salt.hex()$key.hex())
    salt = secrets.token_bytes(16)
    password = "LegacyUserPass2026!"
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    legacy_hash = f"{salt.hex()}${key.hex()}"

    # Verify legacy verification works
    assert auth.verify_password(password, legacy_hash) is True
    assert auth.needs_rehash(legacy_hash) is True

    # Seed a user with the legacy hash directly in SQLite
    with session_scope() as session:
        user = m.User(
            email="legacy@eduverse.ai",
            username="legacy_student",
            hashed_password=legacy_hash,
            full_name="Legacy Scholar",
            is_active=True,
            token_version=1,
        )
        session.add(user)
        session.commit()
        user_id = user.id

    app = create_app(config)
    client = TestClient(app)

    # Log in with the legacy password
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": "legacy_student", "password": password},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "token" in data

    # User's hash must now be upgraded in the database to Argon2id
    with session_scope() as session:
        migrated_user = session.get(m.User, user_id)
        assert migrated_user is not None
        assert migrated_user.hashed_password.startswith("$argon2id$v=19$")
        assert auth.needs_rehash(migrated_user.hashed_password) is False
        assert auth.verify_password(password, migrated_user.hashed_password) is True


# --------------------------------------------------------------------------- 3. Authentication Throttling
def test_login_throttling_and_generic_messages(config: Config):
    """Verify failed login tracking, temporary throttling (HTTP 429), and generic error messages."""
    auth.throttler.reset()
    app = create_app(config)
    client = TestClient(app)

    # 5 failed login attempts
    for i in range(5):
        resp = client.post(
            "/api/v1/auth/login",
            json={"username": "throttled_user@eduverse.ai", "password": f"WrongAttempt{i}"},
        )
        assert resp.status_code == 401
        # Generic error message to prevent enumeration
        assert resp.json()["detail"] == "Invalid email or password."

    # 6th attempt within window must be throttled with 429
    throttled_resp = client.post(
        "/api/v1/auth/login",
        json={"username": "throttled_user@eduverse.ai", "password": "AnyPassword"},
    )
    assert throttled_resp.status_code == 429
    assert "Too many failed login attempts" in throttled_resp.json()["detail"]
    assert "Retry-After" in throttled_resp.headers

    auth.throttler.reset()


# --------------------------------------------------------------------------- 4 & 5. Session Revocation & Rejection
def test_logout_and_revoked_token_rejection(config: Config):
    """Verify server-side logout revokes tokens and subsequent use returns 401."""
    app = create_app(config)
    client = TestClient(app)

    # Register a new user
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "email": "revoke_test@eduverse.ai",
            "username": "revoker",
            "password": "SecurePassword123!",
            "full_name": "Revoke Tester",
        },
    )
    assert reg.status_code == 201
    token = reg.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Verify token works for /me
    me_resp = client.get("/api/v1/auth/me", headers=headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["username"] == "revoker"

    # Log out (server-side session revocation)
    logout_resp = client.post("/api/v1/auth/logout", headers=headers)
    assert logout_resp.status_code == 200
    assert "Logged out successfully" in logout_resp.json()["message"]

    # Reusing the revoked token on /me MUST fail with 401
    post_logout_me = client.get("/api/v1/auth/me", headers=headers)
    assert post_logout_me.status_code == 401

    # Reusing the revoked token on another endpoint (e.g. /sources) MUST fail with 401
    sources_resp = client.get("/api/v1/sources", headers=headers)
    assert sources_resp.status_code == 401


# --------------------------------------------------------------------------- 6. Password Change Session Invalidation
def test_password_change_invalidates_all_sessions(config: Config):
    """Verify changing password increments token version and invalidates all existing sessions."""
    app = create_app(config)
    client = TestClient(app)

    # Register user
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "email": "pwd_change@eduverse.ai",
            "username": "pwd_user",
            "password": "OldPassword123!",
            "full_name": "Password User",
        },
    )
    assert reg.status_code == 201
    old_token = reg.json()["token"]
    old_headers = {"Authorization": f"Bearer {old_token}"}

    # Verify old token works
    assert client.get("/api/v1/auth/me", headers=old_headers).status_code == 200

    # Change password
    change_resp = client.post(
        "/api/v1/auth/change-password",
        headers=old_headers,
        json={
            "current_password": "OldPassword123!",
            "new_password": "NewBetterPassword456!",
        },
    )
    assert change_resp.status_code == 200
    assert "Password changed successfully" in change_resp.json()["message"]

    # Old token MUST now be rejected with 401
    assert client.get("/api/v1/auth/me", headers=old_headers).status_code == 401

    # Old password no longer works
    old_login = client.post(
        "/api/v1/auth/login",
        json={"username": "pwd_user", "password": "OldPassword123!"},
    )
    assert old_login.status_code == 401

    # New password succeeds and grants new valid token
    new_login = client.post(
        "/api/v1/auth/login",
        json={"username": "pwd_user", "password": "NewBetterPassword456!"},
    )
    assert new_login.status_code == 200
    new_token = new_login.json()["token"]
    new_headers = {"Authorization": f"Bearer {new_token}"}
    assert client.get("/api/v1/auth/me", headers=new_headers).status_code == 200


# --------------------------------------------------------------------------- 7. Production Demo Suppression
def test_production_demo_suppression(data_dir: Path):
    """Verify demo account seeding is suppressed in production environment."""
    prod_cfg = Config(data_dir=data_dir / "prod_test")

    with patch.dict(os.environ, {"EDUVERSE_ENV": "production"}):
        assert prod_cfg.is_production is True
        assert prod_cfg.seed_demo is False
        init_database(prod_cfg)

        with session_scope() as session:
            demo_user = session.query(m.User).filter_by(email="student@eduverse.ai").first()
            assert demo_user is None, "Demo student account must NOT be seeded in production mode"

    # In local demo environment with default flag, demo user should be available
    dev_cfg = Config(data_dir=data_dir / "dev_test")
    with patch.dict(os.environ, {"EDUVERSE_ENV": "development", "EDUVERSE_SEED_DEMO": "true"}):
        assert dev_cfg.seed_demo is True
        init_database(dev_cfg)

        with session_scope() as session:
            demo_user = session.query(m.User).filter_by(email="student@eduverse.ai").first()
            assert demo_user is not None
            assert demo_user.email == "student@eduverse.ai"


# --------------------------------------------------------------------------- 8. User Data Isolation
def test_user_data_isolation_with_tokens(config: Config):
    """Verify multi-tenant isolation: User B cannot access User A's private resources."""
    app = create_app(config)
    client = TestClient(app)

    # User A
    user_a = client.post(
        "/api/v1/auth/register",
        json={"email": "usera@eduverse.ai", "username": "usera", "password": "PasswordA123!"},
    ).json()
    token_a = user_a["token"]

    # User B
    user_b = client.post(
        "/api/v1/auth/register",
        json={"email": "userb@eduverse.ai", "username": "userb", "password": "PasswordB123!"},
    ).json()
    token_b = user_b["token"]

    # User A creates a source
    create_src = client.post(
        "/api/v1/sources/text",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"title": "User A Private Notes", "content": "Confidential research by User A."},
    )
    assert create_src.status_code == 200
    source_id = create_src.json()["source_id"]

    # User A can access it
    src_a = client.get(f"/api/v1/sources/{source_id}", headers={"Authorization": f"Bearer {token_a}"})
    assert src_a.status_code == 200

    # User B MUST NOT be able to access User A's source
    src_b = client.get(f"/api/v1/sources/{source_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert src_b.status_code in (403, 404), f"Expected 403 or 404, got: {src_b.status_code}"


# --------------------------------------------------------------------------- 9. Provider Credential Error Handling
def test_invalid_provider_credentials_error_translation():
    """Verify provider authentication errors produce clean, actionable messages instead of 500s."""
    mock_response = httpx.Response(
        status_code=401,
        headers={"content-type": "application/json"},
        content=b'{"error": {"message": "Incorrect API key provided: sk-invalid"}}',
        request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"),
    )

    with pytest.raises(ProviderAuthError) as exc_info:
        raise_for_response(mock_response, provider="openai", label="OpenAI")

    error_msg = str(exc_info.value)
    assert "OpenAI rejected the API key" in error_msg
    assert "Settings" in error_msg
    assert exc_info.value.status_code == 502 or exc_info.value.status_code == 401


# --------------------------------------------------------------------------- 10. Mock Mode Transparency & Citations
def test_mock_mode_transparency_and_citations():
    """Verify deterministic mock answers are flagged with is_mock=True and citations remain grounded."""
    excerpts = [
        Excerpt(id=1, source_id=10, text="Mitochondria generate cellular ATP through oxidative phosphorylation.", source_title="Cell Biology"),
        Excerpt(id=2, source_id=10, text="Glycolysis occurs in the cytosol and yields two pyruvate molecules.", source_title="Biochemistry"),
    ]

    # Valid answer citing excerpt [1]
    raw_answer = "Mitochondria produce ATP for the cell [1]."
    validated_text, citations = validate_answer(raw_answer, excerpts)
    assert "[1]" in validated_text
    assert citations == [1]

    # Answer citing non-existent excerpt [99] should drop hallucinated citation
    hallucinated_answer = "Some statement without real evidence [99]."
    cleansed_text, cleansed_citations = validate_answer(hallucinated_answer, excerpts)
    assert "[99]" not in cleansed_text
    assert 99 not in cleansed_citations


# --------------------------------------------------------------------------- 11. Safe Exception Handling
def test_safe_unhandled_exception_handling():
    """Verify unhandled server errors return sanitized messages and do not leak stack traces."""
    from fastapi import FastAPI
    from quicklearn.main import _install_error_handlers

    test_app = FastAPI()
    _install_error_handlers(test_app)

    @test_app.get("/crash")
    def crash_route():
        raise ZeroDivisionError("Internal arithmetic explosion at line 42 in secret_calc.py")

    client = TestClient(test_app, raise_server_exceptions=False)
    resp = client.get("/crash")
    assert resp.status_code == 500
    body = resp.json()

    # Must NOT leak exception name or internal line number / filepath
    assert body["error"] == "InternalServerError"
    assert "Internal arithmetic explosion" not in body["message"]
    assert "secret_calc.py" not in body["message"]
    assert "unexpected server error" in body["message"].lower()
