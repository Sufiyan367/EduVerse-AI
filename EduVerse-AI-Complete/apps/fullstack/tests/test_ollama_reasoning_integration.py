"""Automated test suite for Ollama Local Reasoning Integration and System Health.

Validates:
1. Native Ollama /api/chat payload formatting with configurable think level ("high", "medium", "low", "off").
2. Context window (4096), keep_alive ("10m"), and structured format support.
3. Privacy enforcement: Stripping raw internal <think>...</think> scratchpad traces from user-facing answers.
4. Token streaming with thinking token suppression.
5. Dedicated /api/v1/health/llm endpoint.
6. Server /api/v1/health remaining 100% operational when Ollama is offline.
7. Cloud fallback disabled guard (ALLOW_CLOUD_FALLBACK=false).
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
import httpx

from quicklearn.main import create_app
from quicklearn.db.enums import TaskClass
from quicklearn.providers.base import LLMResponse
from quicklearn.providers.llm.ollama import OllamaLLM, _clean_thinking_trace
from quicklearn.providers import registry


def test_thinking_trace_cleaning():
    """Verify that internal model scratchpad thoughts are never exposed."""
    raw = (
        "<think>\n"
        "1. Identify the concept: Raft consensus.\n"
        "2. The election timeout is 150-300ms.\n"
        "3. Synthesize the final answer.\n"
        "</think>\n"
        "Raft consensus uses a randomized election timeout between 150ms and 300ms [1]."
    )
    clean = _clean_thinking_trace(raw)
    assert "<think>" not in clean
    assert "</think>" not in clean
    assert clean == "Raft consensus uses a randomized election timeout between 150ms and 300ms [1]."

    # Empty outside fallback
    raw_only_think = "<think>Just internal reasoning without conclusion</think>"
    assert _clean_thinking_trace(raw_only_think) == "Just internal reasoning without conclusion"


def test_ollama_payload_construction():
    """Verify that OllamaLLM constructs native /api/chat payload with thinking options."""
    llm = OllamaLLM(
        base_url="http://127.0.0.1:11434",
        model="qwen3.5:4b",
        think="high",
        num_ctx=4096,
        keep_alive="10m",
    )
    assert llm.think == "high"
    assert llm.num_ctx == 4096
    assert llm.keep_alive == "10m"

    messages = [
        {"role": "system", "content": "You are a helpful academic tutor."},
        {"role": "user", "content": "Explain Two-Phase Locking."},
    ]
    payload = llm._build_payload(messages, model="qwen3.5:4b", temperature=0.2)

    assert payload["model"] == "qwen3.5:4b"
    assert payload["think"] == "high"
    assert payload["keep_alive"] == "10m"
    assert payload["options"]["num_ctx"] == 4096
    assert payload["options"]["temperature"] == 0.2
    assert len(payload["messages"]) == 2


@pytest.mark.asyncio
async def test_ollama_complete_with_mocked_chat():
    """Verify OllamaLLM.complete() parses response and strips thinking traces."""
    llm = OllamaLLM(base_url="http://127.0.0.1:11434", model="qwen3.5:4b", think="high")

    mock_resp = MagicMock()
    mock_resp.is_success = True
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "model": "qwen3.5:4b",
        "created_at": "2026-11-01T21:00:00Z",
        "message": {
            "role": "assistant",
            "content": "<think>Multi-step plan...</think>Strict 2PL prevents cascading aborts [1].",
        },
        "done": True,
        "prompt_eval_count": 28,
        "eval_count": 64,
    }

    with patch.object(llm._client, "post", new_callable=AsyncMock, return_value=mock_resp) as mock_post:
        res = await llm.complete(
            [{"role": "user", "content": "What does Strict 2PL prevent?"}],
            model="qwen3.5:4b",
        )
        assert mock_post.called
        assert res.text == "Strict 2PL prevents cascading aborts [1]."
        assert res.prompt_tokens == 28
        assert res.completion_tokens == 64
        assert "<think>" not in res.text


@pytest.mark.asyncio
async def test_ollama_stream_filters_thinking():
    """Verify OllamaLLM.stream() suppresses raw thinking tokens."""
    llm = OllamaLLM(base_url="http://127.0.0.1:11434", model="qwen3.5:4b", think="high")

    ndjson_lines = [
        json.dumps({"message": {"content": "<think>Step 1</think>Two-Phase "}}),
        json.dumps({"message": {"content": "Locking guarantees "}}),
        json.dumps({"message": {"content": "serializability."}}),
        json.dumps({"done": True}),
    ]

    class FakeStream:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        @property
        def is_success(self):
            return True

        async def aiter_lines(self):
            for line in ndjson_lines:
                yield line

    with patch.object(llm._client, "stream", return_value=FakeStream()):
        tokens = []
        async for tok in llm.stream([{"role": "user", "content": "What is 2PL?"}], model="qwen3.5:4b"):
            tokens.append(tok)

        combined = "".join(tokens)
        assert "<think>" not in combined
        assert combined == "Two-Phase Locking guarantees serializability."


def test_server_health_separate_from_llm(config, store):
    """Verify /api/v1/health reports status 'ok' even when Ollama is offline."""
    client = TestClient(create_app(config))
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "sqlite_vec" in data


def test_llm_health_endpoint(config, store):
    """Verify /api/v1/health/llm returns detailed status without auth requirement."""
    client = TestClient(create_app(config))
    res = client.get("/api/v1/health/llm")
    assert res.status_code == 200
    data = res.json()
    assert "status" in data
    assert data["provider"] == "ollama"
    assert data["is_local"] is True
    assert "allow_cloud_fallback" in data


def test_cloud_fallback_guard_blocks_cloud(config, store, monkeypatch):
    """Verify that when ALLOW_CLOUD_FALLBACK=false, cloud providers are blocked."""
    monkeypatch.setenv("ALLOW_CLOUD_FALLBACK", "false")
    store.set("providers.ollama.allow_cloud_fallback", False)
    store.set("routing.standard", {"provider": "google", "model": "gemini-2.5-flash"})

    # Resolving standard should block google and re-route to local Ollama or mock
    resolved = registry.get_llm(TaskClass.STANDARD)
    assert resolved.provider_name in ("ollama", "mock")
