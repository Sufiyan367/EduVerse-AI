"""Unit and regression tests for Ollama local provider in EduVerse AI."""

from __future__ import annotations

import pytest
from quicklearn.providers.llm.ollama import OllamaLLM, normalize_ollama_urls, _clean_thinking_trace
from quicklearn.providers.base import ConnectionResult, ModelInfo


def test_ollama_url_normalization():
    """Verify robust URL normalization handles both native base and /v1 paths."""
    # 1. Base URL with port only
    native, v1 = normalize_ollama_urls("http://127.0.0.1:11434")
    assert native == "http://127.0.0.1:11434"
    assert v1 == "http://127.0.0.1:11434/v1"

    # 2. Base URL with /v1
    native, v1 = normalize_ollama_urls("http://127.0.0.1:11434/v1")
    assert native == "http://127.0.0.1:11434"
    assert v1 == "http://127.0.0.1:11434/v1"

    # 3. Base URL with trailing slashes
    native, v1 = normalize_ollama_urls("http://localhost:11434/v1///")
    assert native == "http://localhost:11434"
    assert v1 == "http://localhost:11434/v1"

    # 4. Custom host
    native, v1 = normalize_ollama_urls("http://ai-server.lan:11434")
    assert native == "http://ai-server.lan:11434"
    assert v1 == "http://ai-server.lan:11434/v1"


def test_ollama_thinking_trace_cleaning():
    """Verify deep-thinking tags and traces are cleanly stripped from user-facing text."""
    raw = "<think>\nThinking about the derivative of 3x^3 - 5x + 7\nPower rule gives 9x^2 - 5\n</think>\nThe derivative is 9x^2 - 5."
    cleaned = _clean_thinking_trace(raw)
    assert cleaned == "The derivative is 9x^2 - 5."
    assert "<think>" not in cleaned

    # Raw thinking without tags
    raw_trace = "Thinking Process:\n1. Solve derivative\n\nResult is 31."
    cleaned_trace = _clean_thinking_trace(raw_trace)
    assert cleaned_trace == "Result is 31."


def test_ollama_payload_options():
    """Verify options include num_predict, num_ctx, and intelligent thinking toggles."""
    ollama = OllamaLLM(base_url="http://127.0.0.1:11434", model="qwen3.5:4b", num_ctx=4096, think="high")

    # 1. Standard chat completion (max_tokens > 500) -> think: True
    payload = ollama._build_payload(
        [{"role": "user", "content": "Explain strict 2PL"}],
        model="qwen3.5:4b",
        temperature=0.3,
        max_tokens=2000,
    )
    assert payload["options"]["num_predict"] == 2000
    assert payload["options"]["num_ctx"] == 4096
    assert payload["options"]["temperature"] == 0.3
    assert payload["think"] is True

    # 2. Fast helper query (max_tokens <= 500) -> think: False for speed
    fast_payload = ollama._build_payload(
        [{"role": "user", "content": "rewrite query"}],
        model="qwen3.5:4b",
        temperature=0.2,
        max_tokens=200,
    )
    assert fast_payload["options"]["num_predict"] == 200
    assert fast_payload["think"] is False

    # 3. Structured output with JSON schema -> think: False to avoid schema corruption
    schema_payload = ollama._build_payload(
        [{"role": "user", "content": "generate quiz"}],
        model="qwen3.5:4b",
        temperature=0.2,
        max_tokens=1000,
        json_schema={"type": "object", "properties": {"q": {"type": "string"}}},
    )
    assert schema_payload["format"] == {"type": "object", "properties": {"q": {"type": "string"}}}
    assert schema_payload["think"] is False


@pytest.mark.asyncio
async def test_ollama_live_connection_if_daemon_running():
    """Verify live Ollama connection if daemon is reachable on 11434."""
    ollama = OllamaLLM(base_url="http://127.0.0.1:11434", model="qwen3.5:4b")
    result = await ollama.test_connection()
    if result.ok:
        assert "fully operational" in result.message
        assert any("qwen3.5:4b" in m.id for m in result.models)
    else:
        # If offline or missing, actionable message is provided
        assert ("offline" in result.message) or ("missing" in result.message) or ("pull" in result.message)
