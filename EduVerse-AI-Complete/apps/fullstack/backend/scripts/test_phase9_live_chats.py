import asyncio
import time
import httpx
import json

BASE_URL = "http://127.0.0.1:8080/api/v1"

QUESTIONS = [
    ("Normal academic question", "What is the difference between TCP and UDP in computer networks? Briefly list 3 differences."),
    ("Multi-step reasoning question", "If transactions T1, T2 execute concurrently, explain what happens if T1 reads X after T2 writes X without committing, and how strict 2PL prevents this."),
    ("Mathematical problem", "Calculate the derivative of f(x) = 3*x^3 - 5*x + 7 at x = 2."),
    ("Programming question", "Write a short Python function using asyncio and Semaphore to limit concurrency to 3 tasks."),
    ("Uploaded PDF question with citations", "What is the maximum lock wait timeout for distributed 2PC transactions?"),
    ("Unsupported PDF question", "What is the population of the moon in 2050 according to the document?")
]

async def run_chat_eval():
    print("=" * 60)
    print("PHASE 9: REAL LOCAL INFERENCE EVALUATION THROUGH EDUVERSE API")
    print("=" * 60)

    # 1. Login with test user
    async with httpx.AsyncClient(timeout=180.0) as client:
        login_res = await client.post(
            f"{BASE_URL}/auth/login",
            json={"username": "testpilot@eduverse.ai", "password": "StudyHard123!"}
        )
        assert login_res.status_code == 200, f"Login failed: {login_res.text}"
        token = login_res.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. Verify /health/llm
        llm_res = await client.get(f"{BASE_URL}/health/llm")
        print("\n[HEALTH] /health/llm Status:")
        print(json.dumps(llm_res.json(), indent=2))
        assert llm_res.json()["status"] == "connected"
        assert llm_res.json()["provider"] == "ollama"

        # 3. Create a chat session
        chat_res = await client.post(
            f"{BASE_URL}/chat",
            headers=headers,
            json={"title": "Local Ollama Live Evaluation", "scope_type": "global"}
        )
        assert chat_res.status_code in (200, 201), f"Create chat failed: {chat_res.text}"
        chat_id = chat_res.json()["id"]
        print(f"\n[CHAT] Created Chat Session ID: {chat_id}")

        # 4. Execute the 6 questions
        for idx, (category, q) in enumerate(QUESTIONS, start=1):
            print("\n" + "-" * 55)
            print(f"[{idx}/6] Category: {category}")
            print(f"Question: {q}")
            t0 = time.perf_counter()
            msg_res = await client.post(
                f"{BASE_URL}/chat/{chat_id}/message",
                headers=headers,
                json={"content": q}
            )
            elapsed = time.perf_counter() - t0
            assert msg_res.status_code == 200, f"Chat message failed: {msg_res.text}"
            data = msg_res.json()
            answer = data.get("content") or data.get("text") or ""
            provider = data.get("provider")
            model = data.get("model")
            is_mock = data.get("is_mock")
            citations = data.get("citations", [])

            print(f"Latency: {elapsed:.2f}s | Provider: {provider} | Model: {model} | is_mock: {is_mock}")
            print(f"Citations: {citations}")
            print(f"Answer Preview:\n{answer[:350]}...\n")
            assert is_mock is False, "Mock AI returned instead of real Ollama!"
            assert provider == "ollama", f"Expected provider 'ollama', got '{provider}'"

        print("=" * 60)
        print("ALL 6 LIVE CHAT QUESTIONS COMPLETED WITH 100% REAL OLLAMA INFERENCE!")
        print("=" * 60)

if __name__ == "__main__":
    asyncio.run(run_chat_eval())
