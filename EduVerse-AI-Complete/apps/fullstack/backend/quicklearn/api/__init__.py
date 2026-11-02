"""REST and WebSocket API, all under ``/api/v1`` (PRD §8).

Provides full student learning and exam intelligence endpoints:
- Authentication & User Sessions
- Course Workspace & Syllabus Map
- Previous Paper Intelligence & Analytics
- Exam Simulator & AI Rubric Assessment
- Student Mastery Graph & Adaptive Remediation Planning
- Study Library, Grounded AI Chat, Quizzes, Spaced Flashcards, Notes
"""

from __future__ import annotations

from fastapi import APIRouter

from . import (
    adaptive,
    automation,
    auth,
    cards,
    chat,
    courses,
    dashboard,
    evaluation,
    guided_learning,
    knowledge_gap,
    library,
    notes,
    papers,
    podcasts,
    quiz,
    revision_planner,
    simulator,
    sources,
    syllabus,
    system,
)

api_router = APIRouter(prefix="/api/v1")

# Core & Authentication
api_router.include_router(auth.router)
api_router.include_router(dashboard.router)
api_router.include_router(system.router)
api_router.include_router(library.router)

# Academic Exam Intelligence & Course Workspace
api_router.include_router(courses.router)
api_router.include_router(syllabus.router)
api_router.include_router(guided_learning.router)
api_router.include_router(papers.router)
api_router.include_router(simulator.router)
api_router.include_router(evaluation.router)
api_router.include_router(adaptive.router)
api_router.include_router(automation.router)

# Study & RAG Tools
api_router.include_router(sources.router)
api_router.include_router(notes.router)
api_router.include_router(cards.router)
api_router.include_router(quiz.router)
api_router.include_router(chat.router)
api_router.include_router(knowledge_gap.router)
api_router.include_router(revision_planner.router)
api_router.include_router(podcasts.router)

__all__ = ["api_router"]
