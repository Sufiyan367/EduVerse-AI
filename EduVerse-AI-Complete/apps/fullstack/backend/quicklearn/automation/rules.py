"""Automation Rule configuration and toggle management.

Allows enabling, disabling, and configuring individual autonomous triggers.
"""

from __future__ import annotations

import logging
from typing import Any
from sqlalchemy.orm import Session
from sqlalchemy import select

from ..db.academic_models import AutomationRule
from ..db.types import utcnow

log = logging.getLogger(__name__)

DEFAULT_RULES = [
    {
        "rule_name": "auto_syllabus_extraction",
        "trigger_event": "syllabus_uploaded",
        "is_enabled": True,
        "config": {"auto_extract_cos": True, "min_units": 1},
    },
    {
        "rule_name": "auto_material_mapping",
        "trigger_event": "course_material_uploaded",
        "is_enabled": True,
        "config": {"min_confidence": 0.65, "flag_ambiguous": True},
    },
    {
        "rule_name": "auto_paper_analysis",
        "trigger_event": "previous_paper_uploaded",
        "is_enabled": True,
        "config": {"extract_bloom_levels": True, "disclose_sample_size": True},
    },
    {
        "rule_name": "auto_exam_evaluation",
        "trigger_event": "exam_session_completed",
        "is_enabled": True,
        "config": {"auto_schedule_revision": True, "mastery_threshold": 0.60},
    },
    {
        "rule_name": "daily_revision_scheduler",
        "trigger_event": "scheduled_revision_due",
        "is_enabled": True,
        "config": {"schedule_time": "07:00", "timezone": "Asia/Kolkata", "max_daily_tasks": 3},
    },
    {
        "rule_name": "exam_readiness_monitor",
        "trigger_event": "exam_date_added",
        "is_enabled": True,
        "config": {"alert_threshold_percent": 50.0},
    },
    {
        "rule_name": "weekly_intelligence_report",
        "trigger_event": "weekly_report_due",
        "is_enabled": True,
        "config": {"day_of_week": "Sunday", "time": "20:00"},
    },
    {
        "rule_name": "evidence_audit_engine",
        "trigger_event": "audit_check_due",
        "is_enabled": True,
        "config": {"verify_citations": True, "verify_rubrics": True},
    },
]


def ensure_default_rules(session: Session, user_id: int | None = None) -> list[AutomationRule]:
    """Ensure all default automation rules exist for a user or globally."""
    rules = []
    for item in DEFAULT_RULES:
        stmt = select(AutomationRule).where(
            AutomationRule.rule_name == item["rule_name"],
            AutomationRule.user_id == user_id,
        )
        existing = session.execute(stmt).scalar_one_or_none()
        if existing is None:
            rule = AutomationRule(
                user_id=user_id,
                rule_name=item["rule_name"],
                trigger_event=item["trigger_event"],
                is_enabled=item["is_enabled"],
                config=dict(item["config"]),
                created_at=utcnow(),
                updated_at=utcnow(),
            )
            session.add(rule)
            session.flush()
            rules.append(rule)
        else:
            rules.append(existing)
    return rules


def is_rule_enabled(session: Session, rule_name: str, user_id: int | None = None) -> bool:
    """Check if a specific automation rule is enabled for a user."""
    # Check user-specific rule first
    if user_id is not None:
        user_rule = session.execute(
            select(AutomationRule).where(
                AutomationRule.rule_name == rule_name,
                AutomationRule.user_id == user_id,
            )
        ).scalar_one_or_none()
        if user_rule is not None:
            return user_rule.is_enabled

    # Fall back to global rule
    global_rule = session.execute(
        select(AutomationRule).where(
            AutomationRule.rule_name == rule_name,
            AutomationRule.user_id.is_(None),
        )
    ).scalar_one_or_none()
    if global_rule is not None:
        return global_rule.is_enabled

    # Default to True for known default rules
    return any(r["rule_name"] == rule_name and r["is_enabled"] for r in DEFAULT_RULES)


def list_rules(session: Session, user_id: int | None = None) -> list[dict[str, Any]]:
    """Return all automation rules for a user."""
    ensure_default_rules(session, user_id)
    stmt = select(AutomationRule).where(
        (AutomationRule.user_id == user_id) | (AutomationRule.user_id.is_(None))
    ).order_by(AutomationRule.id.asc())
    rules = session.execute(stmt).scalars().all()
    
    # User rules override globals by rule_name
    rule_map = {}
    for r in rules:
        if r.user_id is None and r.rule_name not in rule_map:
            rule_map[r.rule_name] = r
        elif r.user_id is not None:
            rule_map[r.rule_name] = r

    return [
        {
            "id": r.id,
            "rule_name": r.rule_name,
            "trigger_event": r.trigger_event,
            "is_enabled": r.is_enabled,
            "config": r.config or {},
            "user_id": r.user_id,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        }
        for r in rule_map.values()
    ]


def toggle_rule(
    session: Session,
    rule_name: str,
    is_enabled: bool,
    config: dict[str, Any] | None = None,
    user_id: int | None = None,
) -> AutomationRule:
    """Toggle a rule and update its configuration."""
    stmt = select(AutomationRule).where(
        AutomationRule.rule_name == rule_name,
        AutomationRule.user_id == user_id,
    )
    rule = session.execute(stmt).scalar_one_or_none()
    if rule is None:
        # Find trigger_event from defaults
        trigger = next((r["trigger_event"] for r in DEFAULT_RULES if r["rule_name"] == rule_name), "custom")
        rule = AutomationRule(
            user_id=user_id,
            rule_name=rule_name,
            trigger_event=trigger,
            is_enabled=is_enabled,
            config=config or {},
            created_at=utcnow(),
            updated_at=utcnow(),
        )
        session.add(rule)
    else:
        rule.is_enabled = is_enabled
        if config is not None:
            merged = dict(rule.config or {})
            merged.update(config)
            rule.config = merged
        rule.updated_at = utcnow()

    session.flush()
    return rule
