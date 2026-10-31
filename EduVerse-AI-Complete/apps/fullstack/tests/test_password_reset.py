"""Test suite for secure password reset and forgot-password workflow."""
from __future__ import annotations

import hashlib
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from quicklearn.auth import verify_password
from quicklearn.config import Config
from quicklearn.db import models as m
from quicklearn.db.session import session_scope
from quicklearn.main import create_app


@pytest.fixture
def client(config: Config) -> TestClient:
    return TestClient(create_app(config))


def test_forgot_password_generic_response_for_both_existing_and_missing_email(client: TestClient):
    """Ensure the endpoint returns the exact same message to prevent user enumeration."""
    # 1. Existing student
    r_existing = client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "student@eduverse.ai"},
    )
    assert r_existing.status_code == 200
    msg_existing = r_existing.json()["message"]
    assert "instructions have been sent" in msg_existing

    # 2. Non-existent email
    r_missing = client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "nobody_exists_12345@example.com"},
    )
    assert r_missing.status_code == 200
    assert r_missing.json()["message"] == msg_existing


def test_password_reset_token_hashed_in_db_and_validates(client: TestClient):
    """Verify reset token is stored only as a hash and resets the password successfully."""
    # 1. Register a test user
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "email": "reset_test@example.com",
            "username": "reset_user",
            "password": "OldValidPassword123",
            "full_name": "Reset Test User",
        },
    )
    assert reg.status_code == 201
    old_token = reg.json()["token"]

    # 2. Request forgot password
    with patch("quicklearn.api.auth.send_password_reset_email") as mock_send:
        r_forgot = client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "reset_test@example.com"},
        )
        assert r_forgot.status_code == 200
        assert mock_send.called
        raw_token = mock_send.call_args[0][1]

    # Verify token is stored as SHA-256 hash in DB, not plain text
    expected_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    with session_scope() as session:
        record = session.scalar(
            select(m.PasswordResetToken).where(m.PasswordResetToken.token_hash == expected_hash)
        )
        assert record is not None
        assert record.used_at is None
        assert record.expires_at > datetime.now(timezone.utc)

    # 3. Invalid token attempt fails
    r_bad = client.post(
        "/api/v1/auth/reset-password",
        json={"token": "invalid_token_1234567890", "new_password": "NewBetterPassword999!"},
    )
    assert r_bad.status_code == 400
    assert "Invalid or expired" in (r_bad.json().get("detail") or r_bad.json().get("message", ""))

    # 4. Weak password attempt fails
    r_weak = client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw_token, "new_password": "short"},
    )
    assert r_weak.status_code in (400, 422)

    # 5. Successful reset with valid token
    r_success = client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw_token, "new_password": "NewBetterPassword999!"},
    )
    assert r_success.status_code == 200
    assert "successfully reset" in r_success.json()["message"]

    # 6. Replay attack: Used token cannot be reused
    r_replay = client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw_token, "new_password": "AnotherNewPassword123!"},
    )
    assert r_replay.status_code == 400

    # 7. Old sessions invalidated: old_token rejected on authenticated endpoints
    r_auth = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {old_token}"})
    assert r_auth.status_code == 401

    # 8. User can log in with new password
    r_login = client.post(
        "/api/v1/auth/login",
        json={"username": "reset_test@example.com", "password": "NewBetterPassword999!"},
    )
    assert r_login.status_code == 200
    assert r_login.json()["user"]["email"] == "reset_test@example.com"


def test_forgot_password_unavailable_when_unconfigured_in_production(client: TestClient):
    """In production mode without SMTP configured, returns 503 instead of false simulation."""
    with patch.dict(os.environ, {"EDUVERSE_ENV": "production", "EDUVERSE_SMTP_HOST": ""}):
        r = client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "student@eduverse.ai"},
        )
        assert r.status_code == 503
        assert "not configured" in r.json().get("detail", "")
