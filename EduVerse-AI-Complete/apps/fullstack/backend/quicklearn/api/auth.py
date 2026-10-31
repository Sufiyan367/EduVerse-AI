"""Authentication and session endpoints for EduVerse AI."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..activity import record_activity
from ..auth import (
    create_access_token,
    get_current_user,
    get_token_from_header,
    hash_password,
    needs_rehash,
    revoke_session_token,
    throttler,
    validate_password,
    verify_password,
)
from ..db.models import User
from ..db.session import get_db

log = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


def _client_ip(request: Request) -> str:
    """Extract client IP from request, taking proxy forwarding headers into account."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"


class RegisterRequest(BaseModel):
    email: str = Field(pattern=r"^[^@]+@[^@]+\.[^@]+$", description="Valid email address")
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(default="", max_length=255)


class LoginRequest(BaseModel):
    username: str = Field(description="Username or email address")
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class UserOut(BaseModel):
    id: int
    email: str
    username: str
    full_name: str
    avatar_color: str

    model_config = {"from_attributes": True}


class AuthResponse(BaseModel):
    token: str
    token_type: str = "bearer"
    user: UserOut


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(req: RegisterRequest, request: Request, db: Session = Depends(get_db)) -> AuthResponse:
    """Register a new student account with rate limiting and password strength validation."""
    client_ip = _client_ip(request)
    throttler.check_registration_allowed(client_ip)

    # Password validation (length >= 8 and common password protection)
    validate_password(req.password)

    # Check if email or username already taken
    existing = db.scalar(
        select(User).where(or_(User.email == req.email.lower(), User.username == req.username.strip()))
    )
    if existing:
        if existing.email == req.email.lower():
            raise HTTPException(status_code=400, detail="An account with this email already exists.")
        raise HTTPException(status_code=400, detail="This username is already taken.")

    # Create new user
    colors = ["#7C3AED", "#06B6D4", "#10B981", "#F59E0B", "#EC4899", "#3B82F6"]
    avatar_color = colors[len(req.username) % len(colors)]

    user = User(
        email=req.email.lower(),
        username=req.username.strip(),
        hashed_password=hash_password(req.password),
        full_name=req.full_name.strip() or req.username.strip(),
        avatar_color=avatar_color,
        is_active=True,
        token_version=1,
    )
    db.add(user)
    db.flush()

    token = create_access_token(
        user_id=user.id,
        username=user.username,
        email=user.email,
        token_version=user.token_version or 1,
    )
    record_activity(
        session=db,
        action="USER_REGISTERED",
        entity_type="user",
        entity_id=user.id,
        title=f"Welcome to EduVerse, {user.full_name}!",
        user_id=user.id,
    )

    return AuthResponse(token=token, user=UserOut.model_validate(user))


@router.post("/login", response_model=AuthResponse)
def login(req: LoginRequest, request: Request, db: Session = Depends(get_db)) -> AuthResponse:
    """Log in with rate limiting, failed attempt tracking, and transparent Argon2id migration."""
    client_ip = _client_ip(request)
    throttler.check_login_allowed(req.username, client_ip)

    ident = req.username.strip().lower()
    user = db.scalar(
        select(User).where(or_(User.email == ident, User.username == req.username.strip()))
    )

    if not user or not verify_password(req.password, user.hashed_password):
        throttler.record_failed_login(req.username, client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled.")

    throttler.record_successful_login(req.username, client_ip)

    # Transparent password hash migration to modern Argon2id
    if needs_rehash(user.hashed_password):
        user.hashed_password = hash_password(req.password)
        db.commit()
        log.info("Migrated password hash to Argon2id for user_id=%s", user.id)

    token = create_access_token(
        user_id=user.id,
        username=user.username,
        email=user.email,
        token_version=user.token_version or 1,
    )
    return AuthResponse(token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def get_current_profile(user: User = Depends(get_current_user)) -> UserOut:
    """Get the currently authenticated user's profile."""
    return UserOut.model_validate(user)


@router.post("/logout")
def logout(
    token: str | None = Depends(get_token_from_header),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    """Server-side session invalidation and token revocation."""
    if token:
        revoke_session_token(token, current_user.id)
    return {"message": "Logged out successfully."}


@router.post("/change-password")
def change_password(
    req: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    token: str | None = Depends(get_token_from_header),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Change password with strength validation and automatic invalidation of all active sessions."""
    user = db.get(User, current_user.id)
    if not user or not verify_password(req.current_password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )

    validate_password(req.new_password)
    if req.current_password == req.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from current password.",
        )

    user.hashed_password = hash_password(req.new_password)
    user.token_version = (user.token_version or 1) + 1
    db.commit()

    if token:
        revoke_session_token(token, user.id)

    log.info("SECURITY_EVENT: Password changed and all sessions revoked for user=%s", user.email)
    return {"message": "Password changed successfully. All previous sessions have been invalidated."}
