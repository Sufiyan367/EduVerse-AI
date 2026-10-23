"""Authentication and session endpoints for EduVerse AI."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..activity import record_activity
from ..auth import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from ..db.models import User
from ..db.session import get_db

log = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: str = Field(pattern=r"^[^@]+@[^@]+\.[^@]+$", description="Valid email address")
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=128)
    full_name: str = Field(default="", max_length=255)


class LoginRequest(BaseModel):
    username: str = Field(description="Username or email address")
    password: str


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
def register(req: RegisterRequest, db: Session = Depends(get_db)) -> AuthResponse:
    """Register a new student account."""
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
    )
    db.add(user)
    db.flush()

    token = create_access_token(user_id=user.id, username=user.username, email=user.email)
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
def login(req: LoginRequest, db: Session = Depends(get_db)) -> AuthResponse:
    """Log in with username or email and password."""
    ident = req.username.strip().lower()
    user = db.scalar(
        select(User).where(or_(User.email == ident, User.username == req.username.strip()))
    )

    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username/email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled.")

    token = create_access_token(user_id=user.id, username=user.username, email=user.email)
    return AuthResponse(token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def get_current_profile(user: User = Depends(get_current_user)) -> UserOut:
    """Get the currently authenticated user's profile."""
    return UserOut.model_validate(user)


@router.post("/logout")
def logout() -> dict[str, str]:
    """Client-side token disposal confirmation."""
    return {"message": "Logged out successfully."}
