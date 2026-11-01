"""EduVerse AI Autonomous Automation Engine.

Provides durable, background-driven academic workflows for course syllabus extraction,
previous paper analysis, rubric evaluation, daily adaptive revision, exam readiness monitoring,
weekly intelligence reports, and data quality evidence audits.
"""

from . import handlers  # registers all handlers with worker pool
from .dispatcher import trigger_event
from .rules import ensure_default_rules, is_rule_enabled, list_rules, toggle_rule

__all__ = [
    "ensure_default_rules",
    "is_rule_enabled",
    "list_rules",
    "toggle_rule",
    "trigger_event",
]
