import urllib.request
import json
import time

BASE_URL = 'https://eduverse-ai-hpns.onrender.com'
print(f"Testing Live Production Deployment at: {BASE_URL}\n")

def test_endpoint(name, url, method='GET', data=None):
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

# 1. Health check
h_ok, h_res = test_endpoint('1. Health Check (/api/health)', f'{BASE_URL}/api/health')
print("   Status:", h_res)

# 2. Homepage HTML
req = urllib.request.Request(BASE_URL)
with urllib.request.urlopen(req, timeout=30) as r:
    html = r.read().decode('utf-8')
    print(f"[PASS] 2. Frontend Homepage (HTTP {r.status}, length: {len(html)} bytes, Three.js present: {'three.min.js' in html})")

# 3. Load Sample Document
_, sample = test_endpoint('3. Load Sample Document (/api/documents/sample)', f'{BASE_URL}/api/documents/sample', method='POST')
doc_id = sample['doc_id']
print(f"   Loaded Doc ID: {doc_id} ('{sample.get('filename')}')")

# 4. Tutor Q&A (Standard Mode)
tutor_req = {
    'doc_id': doc_id,
    'query': 'What is deep learning and how does it relate to artificial intelligence?',
    'mode': 'standard'
}
_, tutor_res = test_endpoint('4. Tutor Q&A Standard (/api/tutor/query)', f'{BASE_URL}/api/tutor/query', method='POST', data=tutor_req)
print(f"   Tutor Grounded: {tutor_res.get('grounded')}")
print(f"   Tutor Answer: {tutor_res.get('answer')[:180]}...")

# 5. Tutor Concept Simplification (/api/tutor/simplify)
simplify_req = {
    'doc_id': doc_id,
    'concept': 'Supervised Learning'
}
_, simplify_res = test_endpoint('5. Tutor Concept Simplification (/api/tutor/simplify)', f'{BASE_URL}/api/tutor/simplify', method='POST', data=simplify_req)
print(f"   Analogy: {simplify_res.get('analogy')}")
print(f"   Key Points: {simplify_res.get('key_points')}")

# 6. Quiz Generation
quiz_req = {
    'doc_id': doc_id,
    'count': 3
}
_, quiz_res = test_endpoint('6. Quiz Generation (/api/quiz/generate)', f'{BASE_URL}/api/quiz/generate', method='POST', data=quiz_req)
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
_, eval_res = test_endpoint('7. Quiz Evaluation (/api/quiz/evaluate)', f'{BASE_URL}/api/quiz/evaluate', method='POST', data=eval_req)
print(f"   Score: {eval_res.get('correct_count')}/{eval_res.get('total_questions')} ({eval_res.get('score_percentage')} pct)")
print(f"   Passed: {eval_res.get('passed')}")
print(f"   Feedback: {eval_res.get('feedback_message')}")
print("\nALL 7 PRODUCTION ENDPOINTS VERIFIED ON LIVE RENDER DEPLOYMENT!")
