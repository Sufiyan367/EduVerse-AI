import pytest
from fastapi.testclient import TestClient
import pymupdf
from backend.main import app

client = TestClient(app)

def create_dummy_pdf() -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 72), "Unit 4 Supervised Learning: Logistic regression uses sigmoid function.")
    b = doc.tobytes()
    doc.close()
    return b

def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["project"] == "EduVerse AI"
    assert "version" in data

def test_frontend_root_served():
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "EduVerse AI" in response.text

def test_document_upload_and_extraction():
    pdf_bytes = create_dummy_pdf()
    files = {"file": ("test_lecture.pdf", pdf_bytes, "application/pdf")}
    response = client.post("/api/documents/upload", files=files)
    
    assert response.status_code == 200
    data = response.json()
    assert "doc_id" in data
    assert data["filename"] == "test_lecture.pdf"
    assert data["pages"] == 1
    assert data["status"] == "ready"

def test_invalid_file_extension_rejected():
    files = {"file": ("notes.txt", b"Plain text notes", "text/plain")}
    response = client.post("/api/documents/upload", files=files)
    assert response.status_code == 400
    assert "Only standard PDF documents" in response.json()["detail"]

def test_sample_document_loader():
    response = client.post("/api/documents/sample")
    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == "Unit4_SupervisedLearning_ICEM.pdf"
    assert data["pages"] == 2
    assert "doc_id" in data

def test_tutor_query_grounded_workflow():
    # 1. Load document
    sample_resp = client.post("/api/documents/sample")
    doc_id = sample_resp.json()["doc_id"]

    # 2. Query tutor on syllabus concept
    query_payload = {
        "doc_id": doc_id,
        "query": "What is the loss function used in logistic regression?"
    }
    response = client.post("/api/tutor/query", json=query_payload)
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert len(data["answer"]) > 20
    assert data["grounded"] is True
    assert "disclaimer" in data

def test_tutor_query_non_contextual_handling():
    sample_resp = client.post("/api/documents/sample")
    doc_id = sample_resp.json()["doc_id"]

    # Query about completely unrelated topic
    query_payload = {
        "doc_id": doc_id,
        "query": "Explain quantum gravity and string theory loop dynamics."
    }
    response = client.post("/api/tutor/query", json=query_payload)
    assert response.status_code == 200
    data = response.json()
    assert "not covered in the text" in data["answer"].lower()

def test_concept_simplification_endpoint():
    sample_resp = client.post("/api/documents/sample")
    doc_id = sample_resp.json()["doc_id"]

    simplify_payload = {
        "doc_id": doc_id,
        "concept": "Overfitting"
    }
    response = client.post("/api/tutor/simplify", json=simplify_payload)
    assert response.status_code == 200
    data = response.json()
    assert "analogy" in data
    assert "key_points" in data
    assert isinstance(data["key_points"], list)

def test_quiz_generation_and_evaluation():
    sample_resp = client.post("/api/documents/sample")
    doc_id = sample_resp.json()["doc_id"]

    # 1. Generate quiz
    gen_payload = {"doc_id": doc_id, "count": 3}
    gen_resp = client.post("/api/quiz/generate", json=gen_payload)
    assert gen_resp.status_code == 200
    quiz_data = gen_resp.json()
    quiz_id = quiz_data["quiz_id"]
    questions = quiz_data["questions"]
    assert len(questions) == 3

    # Check question schema
    for q in questions:
        assert len(q["options"]) == 4
        assert 0 <= q["correct_option_index"] <= 3
        assert "rationale" in q

    # 2. Evaluate quiz
    answers = [
        {"question_id": q["question_id"], "selected_option_index": q["correct_option_index"]}
        for q in questions
    ]
    eval_payload = {"quiz_id": quiz_id, "answers": answers}
    eval_resp = client.post("/api/quiz/evaluate", json=eval_payload)
    assert eval_resp.status_code == 200
    eval_data = eval_resp.json()
    assert eval_data["total_questions"] == 3
    assert eval_data["correct_count"] == 3
    assert eval_data["score_percentage"] == 100.0
    assert eval_data["passed"] is True
    assert len(eval_data["breakdown"]) == 3
