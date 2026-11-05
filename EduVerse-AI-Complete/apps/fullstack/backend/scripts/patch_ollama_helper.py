from pathlib import Path

ollama_py = Path("EduVerse-AI-repo/EduVerse-AI-Complete/apps/fullstack/backend/quicklearn/providers/llm/ollama.py")
content = ollama_py.read_text(encoding="utf-8")

helper_func = """

async def call_ollama_text(
    prompt: str,
    system: str = "",
    model: str = "qwen3.5:4b",
    temperature: float = 0.2,
    max_tokens: int = 2048,
) -> str:
    \"\"\"Direct helper to call local Ollama instance with optional system prompt and clean thinking trace filtering.\"\"\"
    base_url = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    url = f"{base_url.rstrip('/')}/api/chat"
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
        },
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(url, json=payload)
        if resp.is_success:
            data = resp.json()
            content = data.get("message", {}).get("content", "")
            return _clean_thinking_trace(content)
        raise RuntimeError(f"Ollama call failed with status {resp.status_code}: {resp.text}")
"""

if "async def call_ollama_text" not in content:
    content += helper_func
    ollama_py.write_text(content, encoding="utf-8")
    print("Added call_ollama_text to ollama.py")
else:
    print("call_ollama_text already exists in ollama.py")
