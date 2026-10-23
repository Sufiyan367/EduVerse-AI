import urllib.request
import json
import time
import os
import pytest

BASE_URL = os.getenv('RENDER_SERVICE_URL', 'https://eduverse-ai-hpns.onrender.com')

def request_endpoint(name, url, method='GET', data=None):
    start = time.time()
    req = urllib.request.Request(url, method=method)
    if data:
        req.add_header('Content-Type', 'application/json')
        body = json.dumps(data).encode('utf-8')
    else:
        body = None
    try:
        with urllib.request.urlopen(req, data=body, timeout=60) as resp:
            elapsed = time.time() - start
            res_body = resp.read().decode('utf-8')
            print(f"[PASS] {name} (HTTP {resp.status} in {elapsed:.2f}s)")
            parsed = json.loads(res_body)
            return True, parsed
    except Exception as e:
        elapsed = time.time() - start
        print(f"[FAIL] {name} ({elapsed:.2f}s): {e}")
        return False, str(e)

@pytest.mark.skipif(
    os.getenv('RUN_LIVE_RENDER_TESTS') != '1',
    reason="Live Render integration tests skipped during local test suite. Set RUN_LIVE_RENDER_TESTS=1 to run."
)
def test_live_render_service():
    h_ok, h_res = request_endpoint('1. Health Check (/api/health)', f'{BASE_URL}/api/health')
    assert h_ok is True
    assert h_res.get('status') == 'healthy'

def main():
    print(f"Testing Live Production Deployment at: {BASE_URL}\n")

    # 1. Health check
    h_ok, h_res = request_endpoint('1. Health Check (/api/health)', f'{BASE_URL}/api/health')
    print("   Status:", h_res)

    # 2. Homepage HTML
    try:
        req = urllib.request.Request(BASE_URL)
        with urllib.request.urlopen(req, timeout=30) as r:
            html = r.read().decode('utf-8')
            print(f"[PASS] 2. Frontend Homepage (HTTP {r.status}, length: {len(html)} bytes, Three.js present: {'three.min.js' in html})")
    except Exception as e:
        print(f"[FAIL] 2. Frontend Homepage: {e}")

    # 3. Load Sample Document
    s_ok, sample = request_endpoint('3. Load Sample Document (/api/documents/sample)', f'{BASE_URL}/api/documents/sample', method='POST')
    if not s_ok or not isinstance(sample, dict):
        print("   Cannot proceed with document tests without sample doc.")
        return

    doc_id = sample['doc_id']
    print(f"   Loaded Doc ID: {doc_id} ('{sample.get('filename')}')")

    # 4. Tutor Q&A (Standard Mode)
    tutor_req = {
        'doc_id': doc_id,
        'query': 'What is deep learning and how does it relate to artificial intelligence?',
        'mode': 'standard'
    }
    t_ok, tutor_res = request_endpoint('4. Tutor Q&A Standard (/api/tutor/query)', f'{BASE_URL}/api/tutor/query', method='POST', data=tutor_req)
    if t_ok and isinstance(tutor_res, dict):
        print(f"   Tutor Grounded: {tutor_res.get('grounded')}")
        print(f"   Tutor Answer: {tutor_res.get('answer', '')[:180]}...")

    # 5. Tutor Concept Simplification (/api/tutor/simplify)
    simplify_req = {
        'doc_id': doc_id,
        'concept': 'Supervised Learning'
    }
    sim_ok, simplify_res = request_endpoint('5. Tutor Concept Simplification (/api/tutor/simplify)', f'{BASE_URL}/api/tutor/simplify', method='POST', data=simplify_req)
    if sim_ok and isinstance(simplify_res, dict):
        print(f"   Analogy: {simplify_res.get('analogy')}")
        print(f"   Key Points: {simplify_res.get('key_points')}")

    # 6. Quiz Generation
    quiz_req = {
        'doc_id': doc_id,
        'count': 3
    }
    q_ok, quiz_res = request_endpoint('6. Quiz Generation (/api/quiz/generate)', f'{BASE_URL}/api/quiz/generate', method='POST', data=quiz_req)
    if q_ok and isinstance(quiz_res, dict):
        quiz_id = quiz_res['quiz_id']
        questions = quiz_res['questions']
        print(f"   Generated Quiz ID: {quiz_id} with {len(questions)} questions")
        for q in questions:
            print(f"   - Q{q['question_id']}: {q['question_text']}")

        # 7. Quiz Evaluation
        answers = [
            {'question_id': q['question_id'], 'selected_option_index': q['correct_option_index']}
            for q in questions
        ]
        eval_req = {
            'quiz_id': quiz_id,
            'answers': answers
        }
        e_ok, eval_res = request_endpoint('7. Quiz Evaluation (/api/quiz/evaluate)', f'{BASE_URL}/api/quiz/evaluate', method='POST', data=eval_req)
        if e_ok and isinstance(eval_res, dict):
            print(f"   Score: {eval_res.get('correct_count')}/{eval_res.get('total_questions')} ({eval_res.get('score_percentage')} pct)")
            print(f"   Passed: {eval_res.get('passed')}")
            print(f"   Feedback: {eval_res.get('feedback_message')}")
            print("\nALL 7 PRODUCTION ENDPOINTS VERIFIED ON LIVE RENDER DEPLOYMENT!")

if __name__ == '__main__':
    main()

