"""Import all autonomous automation handlers to register them with the worker pool."""

from . import audit_engine
from . import course_intelligence
from . import exam_to_adaptive
from . import paper_analyst
from . import readiness_monitor
from . import revision_scheduler
from . import weekly_intelligence

__all__ = [
    "audit_engine",
    "course_intelligence",
    "exam_to_adaptive",
    "paper_analyst",
    "readiness_monitor",
    "revision_scheduler",
    "weekly_intelligence",
]
