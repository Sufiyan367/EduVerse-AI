from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

# --- Document Schemas ---
class DocumentUploadResponse(BaseModel):
    doc_id: str
    filename: str
    pages: int
    char_count: int
    preview: str
    status: str = "ready"
    message: str = "Document processed successfully"

class DocumentInfo(BaseModel):
    doc_id: str
    filename: str
    pages: int
    char_count: int
    upload_timestamp: str

class DocumentPassage(BaseModel):
    doc_id: str
    filename: str
    page_number: int
    total_pages: int
    passage_text: str
    char_count: int

# --- Knowledge Constellation Schemas ---
class ConceptNode(BaseModel):
    id: str
    label: str
    category: str = "Core Concept"
    definition: str
    page_reference: int = 1
    excerpt: str = ""

class ConceptEdge(BaseModel):
    source: str
    target: str
    relationship: str
    description: str = ""

class ConstellationResponse(BaseModel):
    doc_id: str
    filename: str
    nodes: List[ConceptNode]
    edges: List[ConceptEdge]
    summary: str = ""

# --- Tutor Q&A Schemas ---
class SourceEvidence(BaseModel):
    page_number: int
    source_quote: str
    relevance_score: float = 1.0

class TutorQueryRequest(BaseModel):
    doc_id: str
    query: str
    mode: Optional[str] = "standard"  # "standard" or "simplify"

class TutorQueryResponse(BaseModel):
    doc_id: str
    query: str
    answer: str
    context_excerpt: Optional[str] = None
    grounded: bool = True
    status: str = "supported"  # "supported" | "partially_supported" | "unsupported"
    evidence: List[SourceEvidence] = []
    disclaimer: str = (
        "Notice: Explanations are synthesized from your uploaded syllabus notes. "
        "Review primary textbook sources for rigorous derivations."
    )

class ConceptSimplifyRequest(BaseModel):
    doc_id: str
    concept: str

class ConceptSimplifyResponse(BaseModel):
    doc_id: str
    concept: str
    analogy: str
    key_points: List[str]
    syllabus_definition: str
    grounded: bool = True

# --- Quiz Schemas ---
class QuizQuestion(BaseModel):
    question_id: int
    question_text: str
    options: List[str]
    correct_option_index: int
    rationale: str

class QuizGenerateRequest(BaseModel):
    doc_id: str
    count: int = Field(default=3, ge=1, le=10)

class QuizGenerateResponse(BaseModel):
    quiz_id: str
    doc_id: str
    questions: List[QuizQuestion]
    total_questions: int

class QuizAnswerSubmission(BaseModel):
    question_id: int
    selected_option_index: int

class QuizEvaluateRequest(BaseModel):
    quiz_id: str
    answers: List[QuizAnswerSubmission]

class QuestionResult(BaseModel):
    question_id: int
    question_text: str
    selected_option_index: int
    correct_option_index: int
    is_correct: bool
    rationale: str

class QuizEvaluationResponse(BaseModel):
    quiz_id: str
    total_questions: int
    correct_count: int
    score_percentage: float
    passed: bool
    breakdown: List[QuestionResult]
    feedback_message: str

class AssessmentHistoryItem(BaseModel):
    eval_id: str
    quiz_id: str
    doc_id: str
    filename: str
    score_percentage: float
    correct_count: int
    total_questions: int
    passed: bool
    evaluated_at: str

class AssessmentHistoryResponse(BaseModel):
    history: List[AssessmentHistoryItem]
    total_assessments: int
    average_score: float

# --- Health Schema ---
class HealthResponse(BaseModel):
    status: str
    project: str
    version: str
    llm_provider: str
    active_documents: int
