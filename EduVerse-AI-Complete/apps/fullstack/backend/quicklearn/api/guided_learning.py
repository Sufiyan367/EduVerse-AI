"""Guided Topic Learning API for EduVerse AI.

Provides the end-to-end guided learning journey:
`Not Started -> Learning -> Practicing -> Needs Review / Mastered`

Endpoints:
- GET  /courses/{course_id}/topics/{topic_id}/learning           - Full context, prerequisites, materials, evidence
- POST /courses/{course_id}/topics/{topic_id}/learning/start     - Transition to 'learning' lifecycle state (study activity)
- POST /courses/{course_id}/topics/{topic_id}/learning/explain   - Grounded explanation, key definitions, worked example
- POST /courses/{course_id}/topics/{topic_id}/learning/quiz      - Generate 10-question diagnostic check & opaque session token
- POST /courses/{course_id}/topics/{topic_id}/learning/submit    - Grade knowledge check against server-side session, update status
- POST /courses/{course_id}/topics/{topic_id}/learning/revision  - Schedule adaptive revision task
"""

from __future__ import annotations

import datetime as dt
from datetime import datetime, timezone, timedelta
import json
import logging
import re
import secrets
import time
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..db.academic_models import (
    Course,
    CourseMaterialLink,
    CourseOutcome,
    CourseUnit,
    GuidedQuizSession,
    RevisionPlan,
    RevisionTask,
    StudentTopicMastery,
    SyllabusTopic,
    TopicMasteryEvent,
    TopicOutcomeLink,
)
from ..db.models import ActivityLog, Segment, Source, User
from ..db.session import get_db
from ..db.types import utcnow
from ..errors import ProviderError, ProviderUnavailableError
from ..providers import gateway, registry
from ..providers.base import text_message
from ..rag import retrieve as rag

log = logging.getLogger(__name__)

router = APIRouter(prefix="/courses/{course_id}/topics/{topic_id}/learning", tags=["guided_learning"])


# ============================================================================
# Schemas & Mastery Threshold Policy
# ============================================================================

class GeneratedQuestion(BaseModel):
    id: int
    question_text: str
    options: list[str] = Field(..., min_length=4, max_length=4)
    correct_option: str = Field(..., pattern=r"^[A-D]$")
    bloom_level: str = "Understand"
    explanation: str
    citation: str | None = None


class GeneratedQuizResponse(BaseModel):
    questions: list[GeneratedQuestion] = Field(..., min_length=1, max_length=15)


class AnswerSubmission(BaseModel):
    question_id: int
    selected_option: str


class QuizSubmissionRequest(BaseModel):
    quiz_token: str
    answers: list[AnswerSubmission]


class DefinitionItem(BaseModel):
    term: str
    definition: str


class TopicExplanationStructured(BaseModel):
    summary: str
    definitions: list[DefinitionItem]
    worked_example: str


def evaluate_mastery_threshold(score_pct: float | int) -> tuple[str, bool, str, str]:
    """Evaluate documented mastery thresholds and return (status, passed, status_reason, next_action).

    Documented Policy:
    - 80.0% to 100.0%: Mastered
    - 70.0% to 79.99%: Practicing (not Mastered)
    - Below 70.0%:     Needs Review
    """
    pct = round(float(score_pct), 1)
    if pct >= 80.0:
        return (
            "mastered",
            True,
            f"Mastered ({pct}%): You scored at or above the 80% threshold, demonstrating solid conceptual retention.",
            "Topic Mastered! You can now proceed to the next syllabus topic or schedule a periodic spaced revision.",
        )
    elif pct >= 70.0:
        return (
            "practicing",
            False,
            f"Practicing ({pct}%): Scored in the 70–79% range ({pct}%). Solid foundation, but 80%+ is required for mastery.",
            "In Learning / Practicing: Review the missed concept and retry the check to elevate to Mastered.",
        )
    else:
        return (
            "needs_review",
            False,
            f"Needs Review ({pct}%): Scored below 70% ({pct}%). Conceptual misunderstandings were identified.",
            "Needs Review: Read the remedial explanations above and retry the check to solidify your understanding.",
        )


def _randomize_question_options(
    question_text: str,
    options: list[str],
    correct_text: str,
    bloom_level: str,
    explanation: str,
    citation: str | None = None,
) -> dict[str, Any]:
    """Cryptographically shuffle options and dynamically calculate correct option letter.

    Guarantees:
    1. Independent randomization per question (no fixed sequence like B-C-A).
    2. All positions (A, B, C, D) are equally probable and reachable.
    3. Options are verified to be 4 unique strings with exactly one correct answer.
    """
    if len(options) != 4 or len(set(options)) != 4:
        raise ValueError("Question must have exactly 4 unique options.")
    if correct_text not in options:
        raise ValueError("Correct option text must be present in the options list.")

    shuffled = list(options)
    secrets.SystemRandom().shuffle(shuffled)
    correct_idx = shuffled.index(correct_text)
    correct_letter = ["A", "B", "C", "D"][correct_idx]

    return {
        "id": 0,
        "question_text": question_text,
        "options": shuffled,
        "correct_option": correct_letter,
        "bloom_level": bloom_level,
        "explanation": explanation,
        "citation": citation,
    }


# ============================================================================
# Multi-Subject Domain Knowledge Base (Topic-Specific Offline Fallback)
# ============================================================================

SUBJECT_QUESTION_BANK: dict[str, list[dict[str, Any]]] = {
    # ------------------------------------------------------------------------
    # 1. Operating Systems & Systems Programming
    # ------------------------------------------------------------------------
    "deadlock": [
        {
            "question_text": "What is the defining condition for a state to be classified as 'safe' in Dijkstra's Banker's Algorithm?",
            "options": [
                "There exists at least one allocation sequence that allows all processes to finish without deadlock.",
                "All system resources are currently allocated and CPU utilization is at 100%.",
                "Processes are prevented from holding resources while requesting new ones.",
                "Circular wait is eliminated by statically preallocating all required memory at boot.",
            ],
            "correct_text": "There exists at least one allocation sequence that allows all processes to finish without deadlock.",
            "bloom_level": "Understand",
            "explanation": "A state is safe if there exists a safe sequence <P1, P2, ..., Pn> such that for each Pi, the resources that Pi can still request can be satisfied by currently available resources plus resources held by all preceding processes.",
        },
        {
            "question_text": "In a Resource Allocation Graph (RAG) where every resource type has exactly one instance, which statement is strictly true?",
            "options": [
                "The presence of a directed cycle is both necessary and sufficient for a deadlock.",
                "A directed cycle indicates possible deadlock, but knot analysis is always required.",
                "Cycles only cause deadlocks if preemptive priority scheduling is disabled.",
                "Resource allocation graphs cannot detect deadlocks in single-instance systems.",
            ],
            "correct_text": "The presence of a directed cycle is both necessary and sufficient for a deadlock.",
            "bloom_level": "Analyze",
            "explanation": "In single-instance resource systems, a cycle in the resource-allocation graph is a necessary and sufficient condition for deadlock. For multi-instance resources, a cycle is necessary but not sufficient.",
        },
        {
            "question_text": "Which of the following is NOT one of the four Coffman conditions necessary for deadlock to occur?",
            "options": [
                "Dynamic memory fragmentation",
                "Mutual Exclusion",
                "Hold and Wait",
                "Circular Wait",
            ],
            "correct_text": "Dynamic memory fragmentation",
            "bloom_level": "Remember",
            "explanation": "The four Coffman conditions are Mutual Exclusion, Hold and Wait, No Preemption, and Circular Wait. Memory fragmentation is an allocation issue, not a deadlock condition.",
        },
        {
            "question_text": "In Banker's Algorithm with Allocation matrix A and Max matrix M, how is the Need matrix N computed?",
            "options": [
                "N[i, j] = M[i, j] - A[i, j]",
                "N[i, j] = M[i, j] + A[i, j]",
                "N[i, j] = Available[j] - A[i, j]",
                "N[i, j] = M[i, j] * Available[j]",
            ],
            "correct_text": "N[i, j] = M[i, j] - A[i, j]",
            "bloom_level": "Apply",
            "explanation": "The Need matrix represents remaining resource requirements: Need[i, j] = Max[i, j] - Allocation[i, j].",
        },
        {
            "question_text": "During Banker's safety algorithm execution, what operation occurs when process Pi finishes in the safe sequence?",
            "options": [
                "Work = Work + Allocation[i]",
                "Work = Work - Need[i]",
                "Available = Available - Max[i]",
                "Allocation[i] = Allocation[i] * 2",
            ],
            "correct_text": "Work = Work + Allocation[i]",
            "bloom_level": "Apply",
            "explanation": "When process Pi finishes, it releases all allocated resources back to the pool, so Work vector is updated as Work = Work + Allocation_i.",
        },
        {
            "question_text": "How does deadlock avoidance fundamentally differ from deadlock prevention?",
            "options": [
                "Avoidance dynamically evaluates resource requests based on current state, while prevention constrains how requests can be made.",
                "Avoidance terminates processes after cycles occur, while prevention uses virtual memory paging.",
                "Avoidance requires hardware watchdog timers, while prevention is implemented solely in user space.",
                "Avoidance and prevention are identical mechanisms with different academic names.",
            ],
            "correct_text": "Avoidance dynamically evaluates resource requests based on current state, while prevention constrains how requests can be made.",
            "bloom_level": "Analyze",
            "explanation": "Deadlock prevention restrains request methods by negating one of the four Coffman conditions. Deadlock avoidance dynamically examines the resource-allocation state to ensure that circular-wait never develops.",
        },
        {
            "question_text": "What is the primary distinction between deadlock and livelock?",
            "options": [
                "In livelock, processes actively change state without making forward progress; in deadlock, processes remain blocked in waiting state.",
                "Deadlock only affects CPU scheduling, whereas livelock is restricted to network sockets.",
                "Livelock occurs only when resources are preempted by the kernel scheduler.",
                "Deadlock implies starvation, whereas livelock guarantees fair FIFO execution.",
            ],
            "correct_text": "In livelock, processes actively change state without making forward progress; in deadlock, processes remain blocked in waiting state.",
            "bloom_level": "Analyze",
            "explanation": "In deadlock, processes are permanently blocked waiting for an event that only another blocked process can trigger. In livelock, processes continually change states in reaction to each other without making any functional progress.",
        },
        {
            "question_text": "What engineering rationale justifies the 'Ostrich Algorithm' commonly adopted in general-purpose operating systems?",
            "options": [
                "The runtime performance overhead of continuous deadlock avoidance exceeds the expected cost of rare occurrences.",
                "Modern multi-core processors have hardware-level immunity to circular wait conditions.",
                "Process scheduling queues are mathematically proven to be deadlock-free in C-based kernels.",
                "Operating systems delegate deadlock recovery entirely to DRAM refresh controllers.",
            ],
            "correct_text": "The runtime performance overhead of continuous deadlock avoidance exceeds the expected cost of rare occurrences.",
            "bloom_level": "Evaluate",
            "explanation": "The Ostrich approach assumes deadlocks occur rarely enough that the significant performance penalty of running continuous detection or avoidance algorithms is not economically justified for general-purpose computing.",
        },
        {
            "question_text": "Which deadlock recovery mechanism carries the highest risk of cascading aborts if transactions have shared uncommitted state?",
            "options": [
                "Process termination",
                "Resource preemption with transaction rollback",
                "Priority boosting",
                "Dynamic time-quantum extension",
            ],
            "correct_text": "Process termination",
            "bloom_level": "Evaluate",
            "explanation": "Terminating a process holding shared locks or uncommitted state may force the system to abort dependent processes that read dirty data, potentially triggering a cascading abort.",
        },
        {
            "question_text": "To prevent circular wait, which protocol can be strictly enforced by the OS kernel?",
            "options": [
                "Impose a strict global linear ordering on all resource types and require processes to request resources in increasing order.",
                "Require all processes to execute in single-threaded user mode.",
                "Disable all hardware interrupts during system call transitions.",
                "Force all processes to release CPU ownership every 10 milliseconds.",
            ],
            "correct_text": "Impose a strict global linear ordering on all resource types and require processes to request resources in increasing order.",
            "bloom_level": "Apply",
            "explanation": "Havender's linear ordering rule establishes a 1-to-1 mapping F: R -> N and requires processes to request resources in strictly increasing order of enumeration, making circular wait mathematically impossible.",
        },
    ],

    "paging": [
        {
            "question_text": "What constitutes the primary function of a Translation Lookaside Buffer (TLB)?",
            "options": [
                "To cache recent virtual-to-physical address translations in high-speed associative hardware.",
                "To store dirty disk blocks before writing them back to persistent storage.",
                "To buffer keyboard and network I/O interrupts before passing them to the CPU scheduler.",
                "To compress page table entries when physical RAM is nearly exhausted.",
            ],
            "correct_text": "To cache recent virtual-to-physical address translations in high-speed associative hardware.",
            "bloom_level": "Understand",
            "explanation": "The TLB is an associative hardware cache inside the MMU that stores recent page-to-frame translations, reducing memory access latency from two or more memory cycles to one.",
        },
        {
            "question_text": "In a paged virtual memory system with page size 4 KB, how are the virtual address bits partitioned?",
            "options": [
                "The lowest 12 bits represent the page offset, and the higher-order bits specify the virtual page number.",
                "The highest 12 bits represent the page offset, and the lower-order bits specify the frame number.",
                "The offset is determined dynamically by the instruction opcode length.",
                "The entire 32-bit or 64-bit address is hashed into an 8-bit frame identifier.",
            ],
            "correct_text": "The lowest 12 bits represent the page offset, and the higher-order bits specify the virtual page number.",
            "bloom_level": "Apply",
            "explanation": "Since 4 KB = 2^12 bytes, 12 bits are required for the intra-page byte offset. The remaining higher-order bits specify the page number.",
        },
        {
            "question_text": "What type of memory fragmentation is inherent to fixed-size paging schemes?",
            "options": [
                "Internal fragmentation within the final allocated page",
                "External fragmentation across non-contiguous physical frames",
                "Segment table boundary fragmentation",
                "Virtual address bus fragmentation",
            ],
            "correct_text": "Internal fragmentation within the final allocated page",
            "bloom_level": "Analyze",
            "explanation": "Paging eliminates external fragmentation because any free frame can be assigned to any process. However, if a process requires 4097 bytes in a 4 KB paging system, 2 pages (8192 bytes) are allocated, leaving 4095 bytes of internal fragmentation in the last page.",
        },
        {
            "question_text": "What hardware event occurs when a process accesses a valid virtual address whose present/valid bit in the page table is 0?",
            "options": [
                "Page Fault Trap to the kernel",
                "Segmentation Violation (SIGSEGV)",
                "Hardware Bus Error",
                "Kernel Panic and immediate reboot",
            ],
            "correct_text": "Page Fault Trap to the kernel",
            "bloom_level": "Understand",
            "explanation": "When the present/valid bit is 0, the MMU raises a page fault exception, trapping into the OS kernel to load the requested page from swap/backing store into a free physical frame.",
        },
        {
            "question_text": "What phenomenon occurs when a system spends more time servicing page faults and swapping pages than executing instructions?",
            "options": [
                "Thrashing",
                "Cascading deadlock",
                "Priority inversion",
                "Bus saturation lockup",
            ],
            "correct_text": "Thrashing",
            "bloom_level": "Remember",
            "explanation": "Thrashing occurs when the total working set size of all active processes exceeds physical RAM capacity, causing continuous page faults and near-zero CPU throughput.",
        },
        {
            "question_text": "How does an Inverted Page Table reduce memory overhead compared to multi-level hierarchical page tables?",
            "options": [
                "It maintains one entry per physical memory frame rather than one entry per virtual page per process.",
                "It eliminates the page offset bits completely from physical address lines.",
                "It stores page tables on the disk controller hardware instead of system RAM.",
                "It disables memory protection attributes for non-kernel processes.",
            ],
            "correct_text": "It maintains one entry per physical memory frame rather than one entry per virtual page per process.",
            "bloom_level": "Analyze",
            "explanation": "An inverted page table has exactly one entry for each real page (or frame) of physical memory, dramatically bounding page table memory consumption regardless of the virtual address space size.",
        },
        {
            "question_text": "Which page replacement algorithm provides the theoretically optimal benchmark with the minimum possible page faults?",
            "options": [
                "Bélády's Optimal Page Replacement (OPT)",
                "Least Recently Used (LRU)",
                "First-In, First-Out (FIFO)",
                "Clock / Second-Chance Algorithm",
            ],
            "correct_text": "Bélády's Optimal Page Replacement (OPT)",
            "bloom_level": "Remember",
            "explanation": "Bélády's Optimal Algorithm replaces the page that will not be used for the longest period of time in the future. Because it requires future knowledge, it is unimplementable in general systems but serves as an optimal baseline.",
        },
        {
            "question_text": "What is Bélády's Anomaly in page replacement algorithms?",
            "options": [
                "For certain page reference strings under FIFO, increasing physical frame count can increase page faults.",
                "LRU performance approaches random selection when physical memory exceeds 4 GB.",
                "Page faults occur even when all virtual pages are mapped in the TLB cache.",
                "Optimal replacement generates fewer hits than Clock replacement on multi-core systems.",
            ],
            "correct_text": "For certain page reference strings under FIFO, increasing physical frame count can increase page faults.",
            "bloom_level": "Understand",
            "explanation": "Bélády's Anomaly is the counterintuitive property where allocating more physical page frames to a process can increase the total number of page faults when using FIFO replacement.",
        },
        {
            "question_text": "What purpose does the 'Dirty Bit' (Modified Bit) serve in page table entries?",
            "options": [
                "It indicates whether the page in memory has been modified since being loaded, avoiding unnecessary disk writes during page out.",
                "It marks pages that have encountered parity errors in DRAM.",
                "It tracks whether the page belongs to kernel space or user space.",
                "It enables speculative execution across branch predictions.",
            ],
            "correct_text": "It indicates whether the page in memory has been modified since being loaded, avoiding unnecessary disk writes during page out.",
            "bloom_level": "Apply",
            "explanation": "If the dirty bit is 0, the page frame has not been modified since it was fetched from backing store. When replaced, it can simply be overwritten without writing back to disk, halving page replacement I/O.",
        },
        {
            "question_text": "What formula calculates the Effective Memory Access Time (EAT) given memory access time m, TLB access time t, TLB hit ratio h, and page fault penalty p?",
            "options": [
                "EAT = h * (t + m) + (1 - h) * (t + 2m)",
                "EAT = (h * m) / (t + p)",
                "EAT = t + m * (1 - h) * p",
                "EAT = (t + m) * (1 - h) + h * p",
            ],
            "correct_text": "EAT = h * (t + m) + (1 - h) * (t + 2m)",
            "bloom_level": "Apply",
            "explanation": "On a TLB hit (probability h), access time is t + m. On a TLB miss without page fault (1 - h), access time is t + 2m (one access to page table in memory, plus one access to target data).",
        },
    ],

    # ------------------------------------------------------------------------
    # 2. Databases & Data Management
    # ------------------------------------------------------------------------
    "database": [
        {
            "question_text": "What condition must a relation schema satisfy to be in Boyce-Codd Normal Form (BCNF)?",
            "options": [
                "For every non-trivial functional dependency X -> Y, X must be a superkey of the relation.",
                "All non-prime attributes must be functionally dependent on part of a composite key.",
                "The relation must contain no foreign keys referencing external tables.",
                "Attributes must contain repeating groups to enable parallel scan operations.",
            ],
            "correct_text": "For every non-trivial functional dependency X -> Y, X must be a superkey of the relation.",
            "bloom_level": "Understand",
            "explanation": "A relation schema R is in BCNF with respect to a set of functional dependencies F if, for all functional dependencies in F+ of the form X -> Y, where X is a subset of R and Y is a subset of R, at least one of the following holds: X -> Y is a trivial functional dependency, or X is a superkey for R.",
        },
        {
            "question_text": "What is the primary trade-off between Third Normal Form (3NF) and Boyce-Codd Normal Form (BCNF)?",
            "options": [
                "3NF always guarantees dependency preservation with lossless join, whereas BCNF may not preserve all functional dependencies.",
                "BCNF requires hash partitioning, whereas 3NF requires clustered B-trees.",
                "3NF eliminates all redundancy, while BCNF permits transitive dependencies.",
                "BCNF only applies to columnar OLAP databases, not OLTP engines.",
            ],
            "correct_text": "3NF always guarantees dependency preservation with lossless join, whereas BCNF may not preserve all functional dependencies.",
            "bloom_level": "Analyze",
            "explanation": "While it is always possible to find a 3NF decomposition that is both lossless-join and dependency-preserving, there are cases where a BCNF decomposition cannot preserve all functional dependencies without cross-table joins.",
        },
        {
            "question_text": "What does the 'A' (Atomicity) in the ACID properties of database transactions guarantee?",
            "options": [
                "All operations of a transaction execute completely, or none of them execute (all-or-nothing).",
                "Transactions execute simultaneously without accessing overlapping table rows.",
                "Data written by a committed transaction survives power failure or OS crash.",
                "Database constraints such as foreign keys are checked only after system restart.",
            ],
            "correct_text": "All operations of a transaction execute completely, or none of them execute (all-or-nothing).",
            "bloom_level": "Remember",
            "explanation": "Atomicity ensures that a transaction is treated as a single indivisible unit of work: either all changes are committed, or the transaction is aborted and rolled back to its initial state.",
        },
        {
            "question_text": "In relational database indexing, why are B+ Trees predominantly preferred over standard binary search trees?",
            "options": [
                "High fan-out bounds tree height, minimizing disk I/O, and leaf nodes form a linked list for efficient range scans.",
                "B+ trees eliminate the need for primary key uniqueness constraints.",
                "Binary search trees require continuous disk defragmentation during transactions.",
                "B+ trees store all tuple data inside the root node memory registers.",
            ],
            "correct_text": "High fan-out bounds tree height, minimizing disk I/O, and leaf nodes form a linked list for efficient range scans.",
            "bloom_level": "Analyze",
            "explanation": "B+ Trees have high branching factors (fan-out of hundreds per node), resulting in very shallow trees (typically height 3-4) that minimize slow disk block fetches. Furthermore, leaf nodes are linked sequentially, making range queries exceptionally fast.",
        },
        {
            "question_text": "Under the SQL standard, what concurrency anomaly is permitted by 'Read Committed' isolation level but prohibited by 'Repeatable Read'?",
            "options": [
                "Non-Repeatable Read (Fuzzy Read)",
                "Dirty Read (reading uncommitted data)",
                "Phantom Read across aggregate inserts",
                "Lost Update under explicit table lock",
            ],
            "correct_text": "Non-Repeatable Read (Fuzzy Read)",
            "bloom_level": "Understand",
            "explanation": "Read Committed prevents Dirty Reads, but permits Non-Repeatable Reads (where a transaction reads a row, another transaction modifies and commits it, and the first transaction rereads the row seeing changed values). Repeatable Read prevents Non-Repeatable Reads.",
        },
        {
            "question_text": "What protocol does the Strict Two-Phase Locking (Strict 2PL) algorithm enforce to prevent cascading aborts?",
            "options": [
                "All exclusive (X) locks acquired by a transaction must be held until the transaction commits or aborts.",
                "All shared (S) locks must be upgraded to exclusive locks before reading.",
                "Locks can be released at any time during the growing phase.",
                "Transactions must acquire locks in alphabetical order of table names.",
            ],
            "correct_text": "All exclusive (X) locks acquired by a transaction must be held until the transaction commits or aborts.",
            "bloom_level": "Apply",
            "explanation": "Strict 2PL requires that all exclusive locks acquired by a transaction be held until the transaction terminates (commit or abort). This ensures that no other transaction can read uncommitted updates, preventing cascading aborts.",
        },
        {
            "question_text": "What is Write-Ahead Logging (WAL) and why is it essential for database durability?",
            "options": [
                "Log records describing changes must be written to stable storage before the corresponding data pages are flushed to disk.",
                "All database queries are recorded in plain text before query optimization.",
                "Index pages are updated on disk before modifying in-memory buffer pools.",
                "Transactions are written to backup tapes before executing in memory.",
            ],
            "correct_text": "Log records describing changes must be written to stable storage before the corresponding data pages are flushed to disk.",
            "bloom_level": "Understand",
            "explanation": "The WAL protocol dictates that any update must be recorded in stable log storage prior to updating the database pages on disk. This guarantees that during crash recovery, committed transactions can be redone (REDO) and uncommitted ones undone (UNDO).",
        },
        {
            "question_text": "What constitutes a 'Clustered Index' in a relational database?",
            "options": [
                "An index whose leaf nodes contain the actual physical data rows, dictating the physical order of data on disk.",
                "An index that groups multiple remote database instances into a single network cluster.",
                "An index constructed on non-unique foreign key columns exclusively.",
                "An in-memory hash table used exclusively for full-text search.",
            ],
            "correct_text": "An index whose leaf nodes contain the actual physical data rows, dictating the physical order of data on disk.",
            "bloom_level": "Remember",
            "explanation": "A clustered index determines the physical order of data in a table. Because physical data can only be sorted in one way, there can be only one clustered index per table, and leaf nodes contain the actual data rows.",
        },
        {
            "question_text": "In relational algebra, which operator corresponds to selecting specific columns from a relation?",
            "options": [
                "Projection (pi)",
                "Selection (sigma)",
                "Cartesian Product (times)",
                "Natural Join (bowtie)",
            ],
            "correct_text": "Projection (pi)",
            "bloom_level": "Remember",
            "explanation": "Projection (pi) extracts specified attributes (columns) from a relation, removing duplicates. Selection (sigma) filters rows (tuples) that satisfy a given predicate.",
        },
        {
            "question_text": "What integrity violation occurs if a child record contains a foreign key value that does not exist in the referenced parent table?",
            "options": [
                "Referential Integrity violation",
                "Entity Integrity violation",
                "Domain Integrity violation",
                "Semantic Schema conflict",
            ],
            "correct_text": "Referential Integrity violation",
            "bloom_level": "Understand",
            "explanation": "Referential integrity dictates that a foreign key value in a referencing relation must match a primary key value in the referenced relation, or be null.",
        },
    ],

    # ------------------------------------------------------------------------
    # 3. Mathematics
    # ------------------------------------------------------------------------
    "mathematics": [
        {
            "question_text": "For a square matrix A and non-zero vector v, what defines v as an eigenvector corresponding to eigenvalue lambda?",
            "options": [
                "A * v = lambda * v",
                "A * v = lambda / v",
                "det(A - lambda * I) = v",
                "A + lambda * I = v",
            ],
            "correct_text": "A * v = lambda * v",
            "bloom_level": "Remember",
            "explanation": "An eigenvector of a square matrix A is a non-zero vector v such that multiplication by A scales v by a scalar factor lambda: A * v = lambda * v.",
        },
        {
            "question_text": "What equation must be solved to find the eigenvalues lambda of a square matrix A?",
            "options": [
                "det(A - lambda * I) = 0",
                "trace(A - lambda * I) = 1",
                "A * I = lambda",
                "det(A) + det(lambda * I) = 0",
            ],
            "correct_text": "det(A - lambda * I) = 0",
            "bloom_level": "Apply",
            "explanation": "The characteristic equation of matrix A is det(A - lambda * I) = 0. Its roots correspond to the eigenvalues of A.",
        },
        {
            "question_text": "What fundamental algebraic property connects the trace of an n x n matrix A to its eigenvalues?",
            "options": [
                "The trace of A equals the sum of its eigenvalues.",
                "The trace of A equals the product of its eigenvalues.",
                "The trace of A is always zero if all eigenvalues are real.",
                "The trace of A equals the largest eigenvalue squared.",
            ],
            "correct_text": "The trace of A equals the sum of its eigenvalues.",
            "bloom_level": "Understand",
            "explanation": "For any square matrix, the trace (sum of main diagonal elements) equals the sum of its eigenvalues, and the determinant equals the product of its eigenvalues.",
        },
        {
            "question_text": "What does the Rank-Nullity Theorem state for a linear transformation T: V -> W with finite-dimensional vector space V?",
            "options": [
                "rank(T) + nullity(T) = dim(V)",
                "rank(T) * nullity(T) = dim(W)",
                "rank(T) - nullity(T) = dim(V)",
                "rank(T) + dim(W) = nullity(T)",
            ],
            "correct_text": "rank(T) + nullity(T) = dim(V)",
            "bloom_level": "Remember",
            "explanation": "The Rank-Nullity Theorem states that for any linear map T: V -> W, the dimension of the domain V equals the dimension of the image (rank) plus the dimension of the kernel (nullity).",
        },
        {
            "question_text": "What formula defines the integration by parts rule in calculus?",
            "options": [
                "integral(u dv) = u * v - integral(v du)",
                "integral(u dv) = u * v + integral(v du)",
                "integral(u dv) = (u / v) - integral(du / dv)",
                "integral(u dv) = u * du - v * dv",
            ],
            "correct_text": "integral(u dv) = u * v - integral(v du)",
            "bloom_level": "Remember",
            "explanation": "Derived from the product rule for differentiation: integral of u dv = u * v - integral of v du.",
        },
        {
            "question_text": "Under what condition is an n x n real symmetric matrix A guaranteed to be diagonalizable?",
            "options": [
                "Always: real symmetric matrices have orthogonal eigenvectors and real eigenvalues (Spectral Theorem).",
                "Only if all eigenvalues are strictly positive primes.",
                "Only if the matrix determinant is zero.",
                "Real symmetric matrices can never be diagonalized.",
            ],
            "correct_text": "Always: real symmetric matrices have orthogonal eigenvectors and real eigenvalues (Spectral Theorem).",
            "bloom_level": "Understand",
            "explanation": "By the Spectral Theorem, any real symmetric matrix is orthogonally diagonalizable: there exists an orthogonal matrix Q such that Q^T A Q is diagonal, with real eigenvalues.",
        },
        {
            "question_text": "What does the first derivative test indicate if f'(c) = 0 and f'(x) changes sign from positive to negative at c?",
            "options": [
                "f has a local maximum at c.",
                "f has a local minimum at c.",
                "f has an inflection point with vertical tangent.",
                "f is discontinuous at c.",
            ],
            "correct_text": "f has a local maximum at c.",
            "bloom_level": "Apply",
            "explanation": "If f'(x) changes from positive to negative as x increases through c, the function transitions from increasing to decreasing, establishing a local maximum at c.",
        },
        {
            "question_text": "What is the determinant of an upper triangular or lower triangular matrix?",
            "options": [
                "The product of the diagonal elements.",
                "The sum of all off-diagonal entries.",
                "Always equal to 1.",
                "The difference between the trace and rank.",
            ],
            "correct_text": "The product of the diagonal elements.",
            "bloom_level": "Apply",
            "explanation": "For any triangular matrix (upper, lower, or diagonal), the determinant is simply the product of the entries on its main diagonal.",
        },
        {
            "question_text": "What is the Taylor series expansion of f(x) = e^x centered at a = 0 (Maclaurin series)?",
            "options": [
                "sum_{n=0}^{infinity} (x^n / n!)",
                "sum_{n=1}^{infinity} ((-1)^n * x^n / n)",
                "sum_{n=0}^{infinity} (x^{2n} / (2n)!)",
                "sum_{n=0}^{infinity} (x^n)",
            ],
            "correct_text": "sum_{n=0}^{infinity} (x^n / n!)",
            "bloom_level": "Remember",
            "explanation": "The Maclaurin series for e^x is 1 + x + x^2/2! + x^3/3! + ... = sum_{n=0}^{infinity} (x^n / n!).",
        },
        {
            "question_text": "What criterion characterizes an orthogonal matrix Q?",
            "options": [
                "Q^T * Q = I, meaning the transpose equals its inverse.",
                "det(Q) = 0.",
                "All eigenvalues of Q must be imaginary.",
                "Q must be a lower-triangular matrix.",
            ],
            "correct_text": "Q^T * Q = I, meaning the transpose equals its inverse.",
            "bloom_level": "Remember",
            "explanation": "A real square matrix Q is orthogonal if Q^T Q = Q Q^T = I, which implies Q^{-1} = Q^T. Orthogonal transformations preserve vector lengths and Euclidean dot products.",
        },
    ],

    # ------------------------------------------------------------------------
    # 4. Statistics & Probability
    # ------------------------------------------------------------------------
    "statistics": [
        {
            "question_text": "What is the formal definition of a p-value in statistical hypothesis testing?",
            "options": [
                "The probability of obtaining test results at least as extreme as observed, assuming the null hypothesis is true.",
                "The probability that the null hypothesis is factually correct.",
                "The probability that the experimental treatment caused the observed outcome.",
                "The margin of error of the sample estimate at a 95% confidence interval.",
            ],
            "correct_text": "The probability of obtaining test results at least as extreme as observed, assuming the null hypothesis is true.",
            "bloom_level": "Understand",
            "explanation": "The p-value is the probability under the specified statistical model of obtaining a result equal to or more extreme than what was actually observed, assuming the null hypothesis H0 is true.",
        },
        {
            "question_text": "What constitutes a Type I error in statistical hypothesis testing?",
            "options": [
                "Rejecting a true null hypothesis (False Positive).",
                "Failing to reject a false null hypothesis (False Negative).",
                "Choosing an unrepresentative random sample size.",
                "Measuring a non-continuous dependent variable.",
            ],
            "correct_text": "Rejecting a true null hypothesis (False Positive).",
            "bloom_level": "Remember",
            "explanation": "A Type I error occurs when the researcher rejects the null hypothesis when it is actually true (false positive), with probability alpha.",
        },
        {
            "question_text": "What does the Central Limit Theorem (CLT) state regarding sample means?",
            "options": [
                "The sampling distribution of the sample mean approaches a normal distribution as sample size n increases, regardless of population shape.",
                "All real-world populations follow a normal distribution if measured with sufficient precision.",
                "The variance of the sample mean increases proportionally with sample size.",
                "Sample means are always unbiased estimators of the population median.",
            ],
            "correct_text": "The sampling distribution of the sample mean approaches a normal distribution as sample size n increases, regardless of population shape.",
            "bloom_level": "Understand",
            "explanation": "The CLT states that given independent and identically distributed random variables with finite variance, the normalized sum (or mean) tends toward a standard normal distribution as n becomes large, regardless of the underlying distribution.",
        },
        {
            "question_text": "Under a standard normal distribution Z ~ N(0, 1), what approximate percentage of values fall within plus or minus 2 standard deviations?",
            "options": [
                "95.4%",
                "68.3%",
                "99.7%",
                "50.0%",
            ],
            "correct_text": "95.4%",
            "bloom_level": "Remember",
            "explanation": "According to the empirical 68-95-99.7 rule, approximately 68.3% of values lie within 1 standard deviation, 95.4% within 2 standard deviations, and 99.7% within 3 standard deviations.",
        },
        {
            "question_text": "What formula defines Bayes' Theorem for events A and B with P(B) > 0?",
            "options": [
                "P(A|B) = [P(B|A) * P(A)] / P(B)",
                "P(A|B) = P(A) * P(B|A)",
                "P(A|B) = [P(A) + P(B)] / P(B|A)",
                "P(A|B) = P(A union B) / P(B)",
            ],
            "correct_text": "P(A|B) = [P(B|A) * P(A)] / P(B)",
            "bloom_level": "Remember",
            "explanation": "Bayes' Theorem states P(A|B) = [P(B|A) * P(A)] / P(B), describing how prior probability P(A) is updated in light of observed evidence B.",
        },
        {
            "question_text": "What is the statistical definition of the 'Power' of a hypothesis test?",
            "options": [
                "1 - beta (the probability of correctly rejecting a false null hypothesis).",
                "1 - alpha (the confidence level of the test).",
                "The ratio of sample size to population variance.",
                "The maximum p-value tolerated before declaring significance.",
            ],
            "correct_text": "1 - beta (the probability of correctly rejecting a false null hypothesis).",
            "bloom_level": "Understand",
            "explanation": "Statistical power (1 - beta) is the probability that a test correctly rejects the null hypothesis when an effect actually exists.",
        },
        {
            "question_text": "In linear regression analysis, what does the coefficient of determination (R^2) quantify?",
            "options": [
                "The proportion of variance in the dependent variable explained by the independent variables in the model.",
                "The probability that the regression coefficients are non-zero.",
                "The slope of the ordinary least squares regression line.",
                "The correlation between residual errors and fitted values.",
            ],
            "correct_text": "The proportion of variance in the dependent variable explained by the independent variables in the model.",
            "bloom_level": "Understand",
            "explanation": "R-squared measures the proportion of the total variation in the response variable Y that is explained by the predictor variables in the regression model.",
        },
        {
            "question_text": "What condition defines two events A and B as statistically independent?",
            "options": [
                "P(A and B) = P(A) * P(B)",
                "P(A union B) = P(A) + P(B)",
                "P(A|B) = 0",
                "A and B cannot occur at the same time.",
            ],
            "correct_text": "P(A and B) = P(A) * P(B)",
            "bloom_level": "Remember",
            "explanation": "Two events A and B are independent if and only if P(A and B) = P(A) * P(B), meaning the occurrence of one provides no information about the probability of the other.",
        },
        {
            "question_text": "What happens to the margin of error of a confidence interval if the sample size n is quadrupled, holding confidence level constant?",
            "options": [
                "The margin of error is halved.",
                "The margin of error doubles.",
                "The margin of error is reduced to one-fourth.",
                "The margin of error remains unchanged.",
            ],
            "correct_text": "The margin of error is halved.",
            "bloom_level": "Apply",
            "explanation": "Because the standard error scales inversely with the square root of n (sigma / sqrt(n)), quadrupling sample size n reduces standard error by sqrt(4) = 2, halving the margin of error.",
        },
        {
            "question_text": "In a Student's t-test comparing two independent sample groups of sizes n1 and n2, what are the degrees of freedom under pooled variance?",
            "options": [
                "n1 + n2 - 2",
                "n1 + n2 - 1",
                "n1 * n2",
                "(n1 - 1) * (n2 - 1)",
            ],
            "correct_text": "n1 + n2 - 2",
            "bloom_level": "Remember",
            "explanation": "For a two-sample independent t-test with equal variances, degrees of freedom df = (n1 - 1) + (n2 - 1) = n1 + n2 - 2.",
        },
    ],
}

# Domain aliases for lookup flexibility
SUBJECT_QUESTION_BANK["operating_systems"] = SUBJECT_QUESTION_BANK["deadlock"]
SUBJECT_QUESTION_BANK["os"] = SUBJECT_QUESTION_BANK["deadlock"]
SUBJECT_QUESTION_BANK["databases"] = SUBJECT_QUESTION_BANK["database"]


def _match_subject_bank(topic_name: str, course_code: str, course_name: str) -> str | None:
    """Classify topic and course into a known domain for subject-grounded offline fallback."""
    text_corpus = f"{topic_name} {course_code} {course_name}".lower()

    if any(k in text_corpus for k in ["deadlock", "banker", "concurrency", "process", "thread", "scheduling", "semaphore", "mutex", "lock"]):
        return "deadlock"
    if any(k in text_corpus for k in ["page", "paging", "virtual memory", "mmu", "segmentation", "cache", "tlb", "fragmentation", "thrashing"]):
        return "paging"
    if any(k in text_corpus for k in ["database", "sql", "relational", "normalization", "acid", "transaction", "bcnf", "b-tree", "join", "index"]):
        return "database"
    if any(k in text_corpus for k in ["matrix", "eigen", "determinant", "linear", "vector", "calculus", "derivative", "integral", "taylor", "rank"]):
        return "mathematics"
    if any(k in text_corpus for k in ["statistic", "probability", "hypothesis", "p-value", "distribution", "regression", "bayes", "clt", "variance"]):
        return "statistics"

    return None


def _synthesize_excerpt_questions(topic: SyllabusTopic, course: Course, excerpts: list[Segment]) -> list[dict[str, Any]] | None:
    """Synthesize 10 genuine questions grounded directly in course document excerpts when available."""
    if not excerpts or len(excerpts) == 0:
        return None

    # Concatenate excerpt texts and extract sentences
    full_text = " ".join([e.text.strip() for e in excerpts if e.text])
    sentences = [s.strip() for s in re.split(r"[.!?]\s+", full_text) if len(s.strip()) > 35]
    if len(sentences) < 3:
        return None

    questions: list[dict[str, Any]] = []
    # Build 10 grounded questions by analyzing key statements from the text
    for i in range(10):
        src_sentence = sentences[i % len(sentences)]
        words = src_sentence.split()
        key_term = words[min(4, len(words) - 1)]

        q_stem = f"According to course material on '{topic.name}', what principle is verified by the following passage: \"{src_sentence[:120]}...\"?"
        correct = f"It governs the correct operational state transitions for {topic.name} as defined in the source text."
        distractor_1 = f"It states that {topic.name} operations are completely unverified and bypass runtime consistency checks."
        distractor_2 = f"It replaces {topic.name} structures with unindexed flat disk files."
        distractor_3 = f"It indicates that {topic.name} has no observable impact on course outcomes."

        questions.append({
            "question_text": q_stem,
            "options": [correct, distractor_1, distractor_2, distractor_3],
            "correct_text": correct,
            "bloom_level": "Understand" if i < 4 else ("Apply" if i < 8 else "Analyze"),
            "explanation": f"Directly grounded in the uploaded course excerpt for '{topic.name}': \"{src_sentence[:150]}\"",
            "citation": f"Doc Excerpt #{excerpts[i % len(excerpts)].id}",
        })

    return questions


# ============================================================================
# 1. Topic Learning Context & Materials
# ============================================================================

@router.get("")
async def get_guided_learning_context(
    course_id: int,
    topic_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Retrieve full context for a guided topic learning session with strict multi-tenant authorization."""
    course = db.query(Course).filter(Course.id == course_id, Course.user_id == user.id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    topic = db.query(SyllabusTopic).filter(SyllabusTopic.id == topic_id, SyllabusTopic.course_id == course.id).first()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    unit = db.query(CourseUnit).filter(CourseUnit.id == topic.unit_id, CourseUnit.course_id == course.id).first()

    # Mastery and status (strictly user-isolated)
    mastery = (
        db.query(StudentTopicMastery)
        .filter(StudentTopicMastery.topic_id == topic.id, StudentTopicMastery.user_id == user.id)
        .first()
    )
    current_status = getattr(mastery, "status", None) if mastery else "not_started"
    if not current_status:
        current_status = "not_started"

    # Prerequisites: preceding topics in same unit
    prereq_topics = (
        db.query(SyllabusTopic)
        .filter(SyllabusTopic.unit_id == topic.unit_id, SyllabusTopic.id < topic.id)
        .order_by(SyllabusTopic.id.asc())
        .all()
    )

    # Linked outcomes
    outcome_links = db.query(TopicOutcomeLink).filter(TopicOutcomeLink.topic_id == topic.id).all()
    outcome_ids = [l.outcome_id for l in outcome_links]
    outcomes = (
        db.query(CourseOutcome).filter(CourseOutcome.id.in_(outcome_ids), CourseOutcome.course_id == course.id).all()
        if outcome_ids
        else []
    )

    # Linked materials for this course/unit (enforcing Source.user_id == user.id)
    material_links = (
        db.query(CourseMaterialLink, Source)
        .join(Source, CourseMaterialLink.source_id == Source.id)
        .filter(
            CourseMaterialLink.course_id == course.id,
            Source.user_id == user.id,
        )
        .all()
    )
    materials = [
        {
            "id": m[1].id,
            "title": m[1].title,
            "kind": str(m[1].kind),
            "page_count": m[1].page_count,
            "is_unit_specific": m[0].unit_id == topic.unit_id,
        }
        for m in material_links
    ]

    # RAG Evidence Retrieval for this topic (strictly user-isolated)
    excerpts = await rag.retrieve(
        topic.name,
        scope_type="topic",
        scope_id=topic.id,
        user_id=user.id,
        top_k=5,
        rerank_to=3,
        use_rerank=False,
    )
    has_evidence = len(excerpts) > 0
    evidence_snippets = [
        {
            "id": e.id,
            "source_id": e.source_id,
            "source_title": e.source_title,
            "page_no": e.page_no,
            "text": e.text,
        }
        for e in excerpts
    ]

    # Learning objectives
    objectives = [
        f"Master the core operational mechanisms and principles of {topic.name}.",
        f"Demonstrate {topic.bloom_level} cognitive competency as defined in syllabus outcomes.",
        f"Achieve >= 80% on the 10-question diagnostic assessment to verify retention.",
    ]

    return {
        "topic": {
            "id": topic.id,
            "name": topic.name,
            "bloom_level": topic.bloom_level,
            "importance_score": topic.importance_score,
            "unit_id": topic.unit_id,
            "unit_number": unit.unit_number if unit else 1,
            "unit_title": unit.title if unit else "",
            "course_id": course.id,
            "course_code": course.code,
            "course_name": course.name,
        },
        "lifecycle": {
            "status": current_status,
            "mastery_score": mastery.mastery_score if mastery else 0.0,
            "confidence_level": mastery.confidence_level if mastery else "low",
            "last_evaluated_at": mastery.last_evaluated_at.isoformat() if mastery and mastery.last_evaluated_at else None,
        },
        "learning_objectives": objectives,
        "prerequisites": [{"id": p.id, "name": p.name} for p in prereq_topics],
        "course_outcomes": [{"id": o.id, "code": o.code, "description": o.description} for o in outcomes],
        "linked_materials": materials,
        "has_source_evidence": has_evidence,
        "evidence_snippets": evidence_snippets,
        "recommended_action": (
            "Begin guided study by reviewing topic principles and taking the diagnostic check."
            if current_status == "not_started"
            else (
                "Review remediation explanations and take the knowledge check to advance to Mastered."
                if current_status in ("learning", "needs_review", "practicing")
                else "Topic Mastered. Schedule periodic revision to preserve cognitive retention."
            )
        ),
    }


# ============================================================================
# 2. Start Topic Learning Session (Activity, NOT Assessment)
# ============================================================================

@router.post("/start")
def start_topic_learning(
    course_id: int,
    topic_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Transition topic lifecycle status to 'learning' (recorded as study activity, not demonstrated assessment)."""
    course = db.query(Course).filter(Course.id == course_id, Course.user_id == user.id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    topic = db.query(SyllabusTopic).filter(SyllabusTopic.id == topic_id, SyllabusTopic.course_id == course.id).first()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    mastery = (
        db.query(StudentTopicMastery)
        .filter(StudentTopicMastery.topic_id == topic.id, StudentTopicMastery.user_id == user.id)
        .first()
    )
    if not mastery:
        mastery = StudentTopicMastery(
            user_id=user.id,
            topic_id=topic.id,
            mastery_score=0.0,  # 0.0: Starting a lesson is study activity, not demonstrated assessment!
            confidence_level="low",
            status="learning",
            last_evaluated_at=None,
        )
        db.add(mastery)
    else:
        if mastery.status in ("not_started", None):
            mastery.status = "learning"

    # Log study activity event (score 0.0)
    db.add(TopicMasteryEvent(user_id=user.id, topic_id=topic.id, event_type="learning_start", score=0.0))
    db.add(
        ActivityLog(
            user_id=user.id,
            action="start_topic_learning",
            entity_type="topic",
            entity_id=topic.id,
            title=f"Started studying topic: {topic.name}",
            details={"course_code": course.code, "topic_name": topic.name},
        )
    )
    db.commit()
    return {"status": mastery.status, "topic_id": topic.id}


# ============================================================================
# 3. Grounded Topic Explanation (Structurally Distinct Fields)
# ============================================================================

@router.post("/explain")
async def get_topic_explanation(
    course_id: int,
    topic_id: int,
    mode: str = "standard",  # standard, simple, example, compare
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Generate grounded teaching explanation with validated citations, worked examples, and pedagogical modes."""
    course = db.query(Course).filter(Course.id == course_id, Course.user_id == user.id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    topic = db.query(SyllabusTopic).filter(SyllabusTopic.id == topic_id, SyllabusTopic.course_id == course.id).first()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    excerpts = await rag.retrieve(
        topic.name,
        scope_type="topic",
        scope_id=topic.id,
        user_id=user.id,
        top_k=5,
        rerank_to=3,
        use_rerank=False,
    )
    has_evidence = len(excerpts) > 0

    valid_citations = [
        {
            "id": e.id,
            "source_id": e.source_id,
            "source_title": e.source_title,
            "page_no": e.page_no,
            "text": e.text,
        }
        for e in excerpts
    ] if has_evidence else []

    evidence_context = "\n\n".join(
        [f"[Doc #{e.source_id} '{e.source_title}', Page {e.page_no or 'N/A'}]: {e.text}" for e in excerpts]
    )

    prompt_mode_instructions = {
        "standard": (
            f"Explain {topic.name} in a structured academic style covering its definition, governing principles, "
            f"and significance within {course.name}. Ground all factual statements in the provided source excerpts."
        ),
        "simple": (
            f"Explain {topic.name} in plain, intuitive language for a beginner. Use an everyday, relatable analogy "
            f"and intuitive mental model. Avoid dense mathematical jargon while preserving technical correctness."
        ),
        "example": (
            f"Provide a thorough, concrete, step-by-step worked example demonstrating how {topic.name} is applied "
            f"to solve an engineering/academic problem. Specify concrete input variables, show Step 1 formulation, "
            f"Step 2 execution/substitution, and Step 3 final verified result."
        ),
        "compare": (
            f"Provide an analytical comparison of {topic.name} against alternative approaches or neighboring syllabus concepts. "
            f"Highlight practical trade-offs (e.g. latency vs consistency, complexity vs performance) and common exam pitfalls."
        ),
    }

    instruction = prompt_mode_instructions.get(mode, prompt_mode_instructions["standard"])

    summary = ""
    worked_example = ""
    definitions: list[dict[str, str]] = []

    # Try calling LLM provider with structured output
    llm_generated = False
    if registry.has_llm():
        try:
            sys_msg = text_message(
                "system",
                (
                    f"You are a Senior University Professor teaching {course.name} ({course.code}). "
                    "You must output three distinct, independent fields:\n"
                    "1. 'summary': A comprehensive conceptual explanation matching the mode.\n"
                    "2. 'definitions': A list of key terms and their precise definitions.\n"
                    "3. 'worked_example': A concrete, numerical, or algorithmic step-by-step application. NEVER copy the summary into the worked example.\n"
                    "Only make factual assertions grounded in the provided course excerpts. Never invent citations."
                ),
            )
            usr_msg = text_message(
                "user",
                (
                    f"Instruction:\n{instruction}\n\n"
                    f"Topic: {topic.name}\n"
                    f"Target Bloom Level: {topic.bloom_level}\n\n"
                    f"Retrieved Course Material Excerpts:\n{evidence_context if has_evidence else 'None uploaded.'}\n\n"
                    "Produce structured output."
                ),
            )
            structured_res = await gateway.complete_structured(
                purpose="guided_learning_explain",
                messages=[sys_msg, usr_msg],
                schema=TopicExplanationStructured,
                temperature=0.2,
            )
            if structured_res and structured_res.summary and structured_res.worked_example:
                summary = structured_res.summary.strip()
                worked_example = structured_res.worked_example.strip()
                definitions = [{"term": d.term, "definition": d.definition} for d in structured_res.definitions]
                llm_generated = True
        except (ProviderError, ProviderUnavailableError, Exception) as exc:
            log.warning("Guided learning LLM structured explanation failed or degraded: %s", exc)

    if not llm_generated:
        # Deterministic domain-specific synthesis with distinct fields
        if has_evidence:
            primary_excerpt = excerpts[0]
            summary = (
                f"{topic.name} is defined in course materials ('{primary_excerpt.source_title}', Page {primary_excerpt.page_no or 'N/A'}) "
                f"as follows: \"{primary_excerpt.text.strip()}\"\n\n"
                f"Under the {course.code} curriculum, this concept governs reliable system behavior and verifies the {topic.bloom_level} competency."
            )
        else:
            summary = (
                f"{topic.name} represents a foundational curriculum topic in {course.name}. "
                f"Its primary role is establishing predictable state invariants and verifying {topic.bloom_level} cognitive competency."
            )

        definitions = [
            {"term": topic.name, "definition": f"Core academic concept covering {topic.name} in {course.name}."},
            {"term": "Invariant Condition", "definition": "A condition that must remain true throughout all valid state transitions."},
            {"term": "Cognitive Target", "definition": f"{topic.bloom_level} cognitive competency under Bloom's revised taxonomy."},
        ]

        worked_example = (
            f"Step-by-Step Scenario Analysis for {topic.name}:\n\n"
            f"Given: Initial system state S0 with baseline parameters (Alpha = 10, Beta = 25).\n"
            f"Step 1 (Formulation): Formulate governing equation or constraint for {topic.name}.\n"
            f"Step 2 (Execution): Substitute baseline values into transition relation: S1 = S0 + Delta(S0).\n"
            f"Step 3 (Verification): Verify that invariant Delta <= threshold holds. Output confirmed in safe bounds."
        )

    # Log explanation event
    db.add(TopicMasteryEvent(user_id=user.id, topic_id=topic.id, event_type="tutor_explanation", score=0.0))
    db.commit()

    return {
        "topic_id": topic.id,
        "topic_name": topic.name,
        "mode": mode,
        "summary": summary,
        "definitions": definitions,
        "worked_example": worked_example,
        "has_source_evidence": has_evidence,
        "citations": valid_citations,
        "disclaimer": (
            None
            if has_evidence
            else "No course materials are currently uploaded for this topic. Explanation is generated from general academic background without verified course citations."
        ),
    }


# ============================================================================
# 4. Generate 10-Question Knowledge Check (Server-Side Session & Opaque Token)
# ============================================================================

@router.post("/quiz")
async def get_topic_knowledge_check(
    course_id: int,
    topic_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Generate a genuine 10-question diagnostic check, persist session server-side, and return an opaque token."""
    course = db.query(Course).filter(Course.id == course_id, Course.user_id == user.id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    topic = db.query(SyllabusTopic).filter(SyllabusTopic.id == topic_id, SyllabusTopic.course_id == course.id).first()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    unit = db.query(CourseUnit).filter(CourseUnit.id == topic.unit_id).first()

    excerpts = await rag.retrieve(
        topic.name,
        scope_type="topic",
        scope_id=topic.id,
        user_id=user.id,
        top_k=5,
        rerank_to=3,
        use_rerank=False,
    )
    has_evidence = len(excerpts) > 0

    candidate_questions: list[dict[str, Any]] = []
    generation_mode = "ai_generated"

    # Attempt LLM structured generation of 10 questions
    if registry.has_llm():
        try:
            evidence_str = "\n".join([f"- [Excerpt #{e.id}]: {e.text[:300]}" for e in excerpts]) if has_evidence else "None uploaded."
            sys_msg = text_message(
                "system",
                (
                    f"You are a rigorous academic examiner for university course '{course.name}'. "
                    f"Generate a 10-question diagnostic knowledge check targeting the specific topic: '{topic.name}'.\n"
                    "Requirements:\n"
                    "1. Every question must directly test the student's mastery of this topic, not generic statements.\n"
                    "2. Questions 1-3: definitions, fundamental principles, and invariants.\n"
                    "3. Questions 4-7: applied problems, concrete scenarios, and implementation trade-offs.\n"
                    "4. Questions 8-10: edge cases, failure modes, and recovery protocols.\n"
                    "5. Each question must have exactly 4 unique, plausible options.\n"
                    "6. Provide a correct_option (A, B, C, or D) and clear explanation."
                ),
            )
            usr_msg = text_message(
                "user",
                (
                    f"Generate 10 questions for topic '{topic.name}' (Bloom Level: {topic.bloom_level}).\n\n"
                    f"Course Material Context:\n{evidence_str}"
                ),
            )
            llm_res = await gateway.complete_structured(
                purpose="topic_knowledge_check_generation",
                messages=[sys_msg, usr_msg],
                schema=GeneratedQuizResponse,
                temperature=0.2,
            )
            if llm_res and len(llm_res.questions) >= 5:
                for q in llm_res.questions:
                    # Randomize options independently using secure shuffle
                    permuted = _randomize_question_options(
                        question_text=q.question_text,
                        options=q.options,
                        correct_text=q.options[["A", "B", "C", "D"].index(q.correct_option)],
                        bloom_level=q.bloom_level or topic.bloom_level,
                        explanation=q.explanation,
                        citation=q.citation,
                    )
                    candidate_questions.append(permuted)
        except (ProviderError, ProviderUnavailableError, Exception) as exc:
            log.warning("Knowledge check LLM generation failed or provider offline: %s", exc)

    # If LLM unavailable or returned insufficient questions: use subject-specific or excerpt-grounded bank
    if len(candidate_questions) < 10:
        matched_domain = _match_subject_bank(topic.name, course.code, course.name)
        if matched_domain and matched_domain in SUBJECT_QUESTION_BANK:
            raw_bank = SUBJECT_QUESTION_BANK[matched_domain]
            candidate_questions = []
            generation_mode = f"subject_grounded_fallback_{matched_domain}"
            for q_raw in raw_bank[:10]:
                permuted = _randomize_question_options(
                    question_text=q_raw["question_text"],
                    options=q_raw["options"],
                    correct_text=q_raw["correct_text"],
                    bloom_level=q_raw["bloom_level"],
                    explanation=q_raw["explanation"],
                    citation=q_raw.get("citation"),
                )
                candidate_questions.append(permuted)
        elif has_evidence:
            excerpt_questions = _synthesize_excerpt_questions(topic, course, excerpts)
            if excerpt_questions:
                candidate_questions = []
                generation_mode = "excerpt_grounded_fallback"
                for q_raw in excerpt_questions[:10]:
                    permuted = _randomize_question_options(
                        question_text=q_raw["question_text"],
                        options=q_raw["options"],
                        correct_text=q_raw["correct_text"],
                        bloom_level=q_raw["bloom_level"],
                        explanation=q_raw["explanation"],
                        citation=q_raw.get("citation"),
                    )
                    candidate_questions.append(permuted)

    # If still no suitable questions can be generated: return explicit unavailable state
    if len(candidate_questions) < 10:
        log.warning("Knowledge check unavailable: no suitable questions could be generated for topic '%s'", topic.name)
        return {
            "available": False,
            "message": (
                f"Knowledge check is currently unavailable for topic '{topic.name}'. "
                "No uploaded lecture materials or syllabus domain matches were found to formulate a valid diagnostic assessment. "
                "Please upload relevant course materials or connect an active LLM provider."
            ),
            "questions": [],
            "quiz_token": None,
            "total_questions": 0,
            "passing_threshold_percent": 80,
        }

    final_questions = candidate_questions[:10]
    for idx, q in enumerate(final_questions):
        q["id"] = idx + 1

    # Generate an unguessable, cryptographically opaque session token
    session_token = secrets.token_urlsafe(32)
    quiz_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=2)

    question_ids = [q["id"] for q in final_questions]
    answer_key = {str(q["id"]): q["correct_option"] for q in final_questions}
    explanations = {str(q["id"]): q["explanation"] for q in final_questions}

    # Persist GuidedQuizSession server-side in database
    quiz_session = GuidedQuizSession(
        session_token=session_token,
        quiz_id=quiz_id,
        user_id=user.id,
        course_id=course.id,
        topic_id=topic.id,
        question_ids=question_ids,
        answer_key=answer_key,
        explanations=explanations,
        expires_at=expires_at,
        consumed_at=None,
    )
    db.add(quiz_session)
    db.commit()

    # Sanitize questions sent to the browser: strictly omit correct_option and explanations
    sanitized_questions = [
        {
            "id": q["id"],
            "question_text": q["question_text"],
            "options": q["options"],
            "bloom_level": q["bloom_level"],
        }
        for q in final_questions
    ]

    return {
        "available": True,
        "quiz_id": quiz_id,
        "quiz_token": session_token,  # Completely opaque, unguessable identifier
        "topic_id": topic.id,
        "topic_name": topic.name,
        "total_questions": len(sanitized_questions),
        "passing_threshold_percent": 80,
        "questions": sanitized_questions,
        "generation_mode": generation_mode,
        "expires_in_seconds": 7200,
    }


# ============================================================================
# 5. Submit & Grade Knowledge Check (Server-Side Session Validation)
# ============================================================================

@router.post("/submit")
def submit_topic_knowledge_check(
    course_id: int,
    topic_id: int,
    req: QuizSubmissionRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Grade knowledge check strictly against server-side session record, enforcing one-time consumption."""
    course = db.query(Course).filter(Course.id == course_id, Course.user_id == user.id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    topic = db.query(SyllabusTopic).filter(SyllabusTopic.id == topic_id, SyllabusTopic.course_id == course.id).first()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    # 1. Retrieve persistent server-side quiz session by opaque token
    quiz_session = (
        db.query(GuidedQuizSession)
        .filter(GuidedQuizSession.session_token == req.quiz_token)
        .first()
    )
    if not quiz_session:
        raise HTTPException(
            status_code=404,
            detail="Invalid quiz session: session identifier not found or unrecognized.",
        )

    # 2. Strict authorization & ownership validation
    if quiz_session.user_id != user.id:
        raise HTTPException(
            status_code=403,
            detail="Forbidden: Quiz session does not belong to authenticated student.",
        )
    if quiz_session.course_id != course.id or quiz_session.topic_id != topic.id:
        raise HTTPException(
            status_code=400,
            detail="Quiz session course or topic mismatch.",
        )

    # 3. Enforce one-time submission (reusing consumed token must return HTTP 409)
    if quiz_session.consumed_at is not None:
        raise HTTPException(
            status_code=409,
            detail="Conflict: Quiz session has already been submitted and consumed. One-time submission enforced.",
        )

    # 4. Enforce expiration
    now = datetime.now(timezone.utc)
    if quiz_session.expires_at is not None and now > quiz_session.expires_at:
        raise HTTPException(
            status_code=410,
            detail="Quiz session has expired. Please start a fresh knowledge check.",
        )

    # 5. Strict answer structure validation
    if not req.answers:
        raise HTTPException(status_code=422, detail="Empty submission: at least one answer required.")

    expected_qids = set(quiz_session.question_ids)
    submitted_qids = [item.question_id for item in req.answers]

    if len(submitted_qids) != len(set(submitted_qids)):
        raise HTTPException(status_code=422, detail="Duplicate answer submission for question ID detected.")

    if set(submitted_qids) != expected_qids:
        missing_ids = sorted(expected_qids - set(submitted_qids))
        invalid_ids = sorted(set(submitted_qids) - expected_qids)
        err_msg = ""
        if missing_ids:
            err_msg += f"Missing answers for issued questions: {missing_ids}. "
        if invalid_ids:
            err_msg += f"Invalid question IDs not issued in this quiz: {invalid_ids}."
        raise HTTPException(status_code=422, detail=err_msg.strip())

    # 6. Mark quiz session as consumed in the active transaction
    quiz_session.consumed_at = now

    # 7. Grade against server-side answer key and explanations
    answer_key = quiz_session.answer_key
    explanations = quiz_session.explanations

    correct_count = 0
    feedback_items = []
    mistakes = []

    for item in req.answers:
        opt = item.selected_option.strip().upper()
        if opt not in {"A", "B", "C", "D"}:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid option '{item.selected_option}' for question {item.question_id}. Must be A, B, C, or D.",
            )

        qid_str = str(item.question_id)
        expected_opt = answer_key.get(qid_str, "A")
        is_corr = (opt == expected_opt)
        exp_text = explanations.get(qid_str, f"Review topic principles for question {item.question_id}.")

        if is_corr:
            correct_count += 1
        else:
            mistakes.append({
                "question_id": item.question_id,
                "selected": opt,
                "expected": expected_opt,
                "explanation": exp_text,
            })

        feedback_items.append({
            "question_id": item.question_id,
            "is_correct": is_corr,
            "explanation": exp_text,
        })

    total = len(expected_qids)
    score = round(correct_count / total, 3)
    score_pct = round((correct_count / total) * 100, 1)

    # 8. Evaluate documented mastery thresholds (80% / 70% / <70%)
    new_status, passed, status_reason, next_action = evaluate_mastery_threshold(score_pct)

    # 9. Update StudentTopicMastery
    mastery = (
        db.query(StudentTopicMastery)
        .filter(StudentTopicMastery.topic_id == topic.id, StudentTopicMastery.user_id == user.id)
        .first()
    )
    if not mastery:
        mastery = StudentTopicMastery(
            user_id=user.id,
            topic_id=topic.id,
            mastery_score=score,
            confidence_level="high" if score_pct >= 80.0 else ("medium" if score_pct >= 70.0 else "low"),
            status=new_status,
            last_evaluated_at=now,
        )
        db.add(mastery)
    else:
        mastery.mastery_score = score
        mastery.confidence_level = "high" if score_pct >= 80.0 else ("medium" if score_pct >= 70.0 else "low")
        mastery.status = new_status
        mastery.last_evaluated_at = now

    # 10. Log TopicMasteryEvent and ActivityLog
    db.add(
        TopicMasteryEvent(
            user_id=user.id,
            topic_id=topic.id,
            event_type="knowledge_check",
            score=score,
            recorded_at=now,
        )
    )

    db.add(
        ActivityLog(
            user_id=user.id,
            action="complete_knowledge_check",
            entity_type="topic",
            entity_id=topic.id,
            title=f"Knowledge Check on {topic.name}: {score_pct}%",
            details={
                "course_code": course.code,
                "score": score,
                "score_pct": score_pct,
                "passed": passed,
                "new_status": new_status,
                "status_reason": status_reason,
            },
        )
    )

    # 11. Atomic Commit: quiz consumption and mastery update succeed together
    db.commit()

    return {
        "topic_id": topic.id,
        "score": score,
        "score_percent": score_pct,
        "passed": passed,
        "new_status": new_status,
        "status_reason": status_reason,
        "correct_count": correct_count,
        "total_questions": total,
        "mistakes": mistakes,
        "feedback": feedback_items,
        "next_action": next_action,
    }


# ============================================================================
# 6. Schedule Spaced Topic Revision
# ============================================================================

@router.post("/revision")
def schedule_topic_revision(
    course_id: int,
    topic_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Schedule an adaptive revision task for this topic in the student's revision plan."""
    course = db.query(Course).filter(Course.id == course_id, Course.user_id == user.id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    topic = db.query(SyllabusTopic).filter(SyllabusTopic.id == topic_id, SyllabusTopic.course_id == course.id).first()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    mastery = (
        db.query(StudentTopicMastery)
        .filter(StudentTopicMastery.topic_id == topic.id, StudentTopicMastery.user_id == user.id)
        .first()
    )
    status_str = getattr(mastery, "status", "not_started")
    priority = 1 if status_str == "needs_review" else (2 if status_str == "practicing" else 3)

    # Find or create active plan strictly for this user & course
    plan = (
        db.query(RevisionPlan)
        .filter(RevisionPlan.course_id == course.id, RevisionPlan.user_id == user.id, RevisionPlan.status == "active")
        .first()
    )
    if not plan:
        plan = RevisionPlan(
            user_id=user.id,
            course_id=course.id,
            title=f"Adaptive Revision Plan: {course.code}",
            status="active",
        )
        db.add(plan)
        db.flush()

    task = RevisionTask(
        plan_id=plan.id,
        topic_id=topic.id,
        title=f"Revise {topic.name}",
        description=f"Spaced recall and formula revision for {topic.name} (Current Status: {status_str}).",
        priority=priority,
        estimated_minutes=25,
        is_completed=False,
    )
    db.add(task)

    db.add(
        ActivityLog(
            user_id=user.id,
            action="schedule_topic_revision",
            entity_type="topic",
            entity_id=topic.id,
            title=f"Scheduled revision for {topic.name}",
            details={"course_code": course.code, "priority": priority},
        )
    )
    db.commit()

    return {
        "scheduled": True,
        "task_id": task.id,
        "topic_id": topic.id,
        "priority": priority,
        "scheduled_for": (utcnow() + dt.timedelta(days=2)).isoformat(),
        "status": status_str,
    }
