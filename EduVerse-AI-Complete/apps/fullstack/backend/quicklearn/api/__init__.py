"""REST and WebSocket API, all under ``/api/v1`` (PRD §8).

Provides full student learning endpoints: Authentication, Dashboard Analytics,
Study Library, Grounded AI Chat, Quizzes, Spaced Flashcards, Notes,
Knowledge Gap Detection, and Adaptive Revision Planning.
"""

from __future__ import annotations

from fastapi import APIRouter

from . import (
    auth,
    cards,
    chat,
    dashboard,
    knowledge_gap,
    library,
    notes,
    podcasts,
    quiz,
    revision_planner,
    sources,
    system,
)

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router)
api_router.include_router(dashboard.router)
api_router.include_router(sources.router)
api_router.include_router(notes.router)
api_router.include_router(cards.router)
api_router.include_router(quiz.router)
api_router.include_router(chat.router)
api_router.include_router(knowledge_gap.router)
api_router.include_router(revision_planner.router)
api_router.include_router(podcasts.router)
api_router.include_router(library.router)
api_router.include_router(system.router)

__all__ = ["api_router"]
