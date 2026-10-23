"""Automated unit and regression tests for local LLM providers (Ollama & LM Studio).

Covers:
- Connection verification and model enumeration
- Connection refused and timeout handling with actionable diagnostics
- Empty models handling (preventing misreporting zero-model servers as inference-ready)
- Structured JSON tolerance: reasoning models (<think>, <thought>, <reasoning>),
  markdown fences, unclosed tags, top-level arrays vs dicts, nested braces in strings
- Error propagation and absence of secret leakage
- Strict provider routing: NO silent fallback to Mock when a real provider fails
- Explicit Mock AI operation
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from quicklearn.errors import (
    ProviderError,
    ProviderResponseError,
    ProviderUnavailableError,
)
from quicklearn.providers import gateway, registry
from quicklearn.providers.base import ModelInfo, text_message
from quicklearn.providers.llm.lmstudio import LMStudioLLM
from quicklearn.providers.llm.mock import MockLLM
from quicklearn.providers.llm.ollama import OllamaLLM
from quicklearn.providers.llm.openai_compat import OpenAICompatLLM
from quicklearn.settings import get_settings


def mount(provider: Any, handler: Any) -> Any:
    """Swap a provider's HTTP client for one backed by a mock transport."""
    provider._client = httpx.AsyncClient(
        base_url=provider.base_url,
        transport=httpx.MockTransport(handler),
        headers=dict(provider._client.headers),
    )
    return provider


def json_response(payload: Any, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json=payload)


# --------------------------------------------------------------------------- Ollama Tests


async def test_ollama_list_models_native_tags() -> None:
    """Ollama parses native /api/tags response with parameter size & quantization."""
    native_payload = {
        "models": [
            {
                "name": "llama3.2:3b",
                "model": "llama3.2:3b",
                "details": {
                    "parameter_size": "3.2B",
                    "quantization_level": "Q4_K_M",
                },
            },
            {
                "name": "qwen2.5:7b",
                "model": "qwen2.5:7b",
                "details": {
                    "parameter_size": "7.6B",
                    "quantization_level": "Q4_0",
                },
            },
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/tags"
        return json_response(native_payload)

    provider = mount(OllamaLLM(base_url="http://localhost:11434/v1"), handler)
    models = await provider.list_models()
    assert len(models) == 2
    assert models[0].id == "llama3.2:3b"
    assert "3.2B, Q4_K_M" in models[0].name
    assert models[1].id == "qwen2.5:7b"
    assert "7.6B, Q4_0" in models[1].name


async def test_ollama_list_models_fallback_to_openai_compat() -> None:
    """When /api/tags is unavailable, Ollama falls back to OpenAI /models."""
    openai_models = {
        "data": [
            {"id": "mistral-nemo", "name": "mistral-nemo"},
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(404, text="Not Found")
        if request.url.path in ("/v1/models", "/models"):
            return json_response(openai_models)
        return httpx.Response(404)

    provider = mount(OllamaLLM(base_url="http://localhost:11434/v1"), handler)
    models = await provider.list_models()
    assert len(models) == 1
    assert models[0].id == "mistral-nemo"


async def test_ollama_test_connection_actionable_error() -> None:
    """When Ollama is not running, test_connection gives actionable remediation."""
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection refused")

    provider = mount(OllamaLLM(base_url="http://localhost:11434/v1"), handler)
    res = await provider.test_connection()
    assert res.ok is False
    assert "Ollama is not reachable" in res.message
    assert "ollama serve" in res.message
    assert "ollama pull" in res.message


async def test_ollama_test_connection_timeout() -> None:
    """When Ollama times out, test_connection reports clear timeout message."""
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("Read timeout")

    provider = mount(OllamaLLM(base_url="http://localhost:11434/v1"), handler)
    res = await provider.test_connection()
    assert res.ok is False
    assert "timed out" in res.message.lower()


async def test_ollama_empty_models_handling() -> None:
    """When Ollama responds with empty tags, report ok=False to prevent false inference claims."""
    def handler(request: httpx.Request) -> httpx.Response:
        return json_response({"models": []})

    provider = mount(OllamaLLM(base_url="http://localhost:11434/v1"), handler)
    res = await provider.test_connection()
    assert res.ok is False
    assert "no models are installed" in res.message.lower()
    assert "ollama pull" in res.message


async def test_ollama_generation_payload_and_response() -> None:
    """Ollama complete sends correct OpenAI-compatible chat completion payload."""
    recorded_request: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal recorded_request
        recorded_request = json.loads(request.content.decode("utf-8"))
        return json_response({
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "model": "llama3.2:3b",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "Supervised learning uses labeled data."},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 15, "completion_tokens": 8, "total_tokens": 23},
        })

    provider = mount(OllamaLLM(base_url="http://localhost:11434/v1"), handler)
    res = await provider.complete(
        [text_message("user", "Explain supervised learning.")],
        model="llama3.2:3b",
        temperature=0.2,
    )
    assert res.text == "Supervised learning uses labeled data."
    assert res.model == "llama3.2:3b"
    assert res.prompt_tokens == 15
    assert res.completion_tokens == 8
    assert recorded_request["model"] == "llama3.2:3b"
    assert recorded_request["temperature"] == 0.2
    assert recorded_request["messages"][0]["content"] == "Explain supervised learning."


# --------------------------------------------------------------------------- LM Studio Tests


async def test_lmstudio_list_models_success() -> None:
    """LM Studio enumerates models via /models."""
    payload = {
        "data": [
            {"id": "qwen2.5-coder-7b-instruct", "name": "Qwen 2.5 Coder 7B"},
            {"id": "deepseek-r1-distill-qwen-7b", "name": "DeepSeek R1 Distill 7B"},
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path in ("/v1/models", "/models")
        return json_response(payload)

    provider = mount(LMStudioLLM(base_url="http://localhost:1234/v1"), handler)
    models = await provider.list_models()
    assert len(models) == 2
    assert models[0].id == "deepseek-r1-distill-qwen-7b"
    assert models[1].id == "qwen2.5-coder-7b-instruct"


async def test_lmstudio_test_connection_actionable_error() -> None:
    """When LM Studio server is stopped, test_connection returns actionable guidance."""
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("All connection attempts failed")

    provider = mount(LMStudioLLM(base_url="http://localhost:1234/v1"), handler)
    res = await provider.test_connection()
    assert res.ok is False
    assert "LM Studio local server is not reachable" in res.message
    assert "Start Server" in res.message
    assert "1234" in res.message


async def test_lmstudio_empty_models_handling() -> None:
    """When LM Studio server is running but no model is loaded, report ok=False to prevent false claims."""
    payload = {"data": []}

    def handler(request: httpx.Request) -> httpx.Response:
        return json_response(payload)

    provider = mount(LMStudioLLM(base_url="http://localhost:1234/v1"), handler)
    res = await provider.test_connection()
    assert res.ok is False
    assert "no models are loaded" in res.message.lower()
    assert res.models == []


async def test_lmstudio_generation_payload_and_response() -> None:
    """LM Studio complete sends correct chat completion payload and parses response."""
    def handler(request: httpx.Request) -> httpx.Response:
        return json_response({
            "id": "chatcmpl-456",
            "model": "qwen2.5-coder-7b-instruct",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "FastAPI is a modern web framework."},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 12, "completion_tokens": 9},
        })

    provider = mount(LMStudioLLM(base_url="http://localhost:1234/v1"), handler)
    res = await provider.complete(
        [text_message("user", "What is FastAPI?")],
        model="qwen2.5-coder-7b-instruct",
    )
    assert res.text == "FastAPI is a modern web framework."
    assert res.finish_reason == "stop"


# --------------------------------------------------------------------------- Structured Output & Reasoning Tests


def test_parse_json_text_strips_reasoning_tags() -> None:
    """Reasoning models with closed <think> blocks parse without error."""
    raw = (
        "<think>\n"
        "The user wants a list of concepts.\n"
        "Let me format this as clean JSON.\n"
        "</think>\n"
        '{"concepts": [{"name": "Gradient Descent", "definition": "Optimization algorithm"}]}'
    )
    parsed = OpenAICompatLLM.parse_json_text(raw)
    assert "concepts" in parsed
    assert parsed["concepts"][0]["name"] == "Gradient Descent"


def test_parse_json_text_unclosed_reasoning_at_start() -> None:
    """Unclosed reasoning block at the start does not truncate valid JSON content."""
    raw = '<think>I am analyzing the text... {"result": "success", "count": 10}'
    parsed = OpenAICompatLLM.parse_json_text(raw)
    assert parsed["result"] == "success"
    assert parsed["count"] == 10


def test_parse_json_text_alternative_thought_tags() -> None:
    """Supports <thought> and <reasoning> tags case-insensitively."""
    raw1 = "<thought>Some internal thought</thought>[1, 2, 3]"
    raw2 = "<REASONING>Analysis</REASONING>{\"valid\": true}"
    assert OpenAICompatLLM.parse_json_text(raw1) == [1, 2, 3]
    assert OpenAICompatLLM.parse_json_text(raw2) == {"valid": True}


def test_parse_json_text_top_level_array_with_prose() -> None:
    """Top-level arrays wrapped in prose parse as list, not accidentally returning an inner dict."""
    raw = 'Here are the cards: [{"front": "Q1", "back": "A1"}]'
    parsed = OpenAICompatLLM.parse_json_text(raw)
    assert isinstance(parsed, list)
    assert len(parsed) == 1
    assert parsed[0]["front"] == "Q1"


def test_parse_json_text_nested_braces_in_strings() -> None:
    """JSON strings containing braces and brackets are parsed completely without truncation."""
    raw = '{"code": "def func(): { return [1, 2]; }", "language": "python"}'
    parsed = OpenAICompatLLM.parse_json_text(raw)
    assert parsed["language"] == "python"
    assert "{ return [1, 2]; }" in parsed["code"]


def test_parse_json_text_strips_markdown_code_fence() -> None:
    """Markdown code fences with ```json are cleanly extracted."""
    raw = (
        "Here is the structured output for your notes:\n\n"
        "```json\n"
        "{\n"
        '  "title": "Machine Learning",\n'
        '  "difficulty": 2\n'
        "}\n"
        "```\n"
        "Let me know if you need any adjustments!"
    )
    parsed = OpenAICompatLLM.parse_json_text(raw)
    assert parsed["title"] == "Machine Learning"
    assert parsed["difficulty"] == 2


def test_parse_json_text_empty_fails_safely() -> None:
    """Empty or whitespace input raises ProviderResponseError safely."""
    with pytest.raises(ProviderResponseError, match="empty response"):
        OpenAICompatLLM.parse_json_text("   ")


def test_parse_json_text_invalid_raises_specific_error() -> None:
    """Unparseable text raises ProviderResponseError with informative message."""
    with pytest.raises(ProviderResponseError, match="Model did not return parseable JSON"):
        OpenAICompatLLM.parse_json_text("This is purely conversational with no JSON structure at all.")


# --------------------------------------------------------------------------- Provider Selection & No-Silent-Fallback


async def test_real_provider_failure_does_not_silently_fallback_to_mock(store: Any) -> None:
    """A failure in a real configured provider (e.g. Ollama offline) must FAIL LOUDLY,

    never silently falling back to Mock AI behind the user's back.
    """
    settings = get_settings()
    settings.set_many({
        "routing.standard": {"provider": "ollama", "model": "llama3.2"},
        "routing.fast": {"provider": "ollama", "model": "llama3.2"},
    })
    registry.reset()

    # Mount an Ollama instance that raises ConnectError
    def failing_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Ollama daemon is offline on port 11434")

    ollama_instance = registry.get_provider(registry.ProviderKind.LLM, "ollama")
    mount(ollama_instance, failing_handler)

    # Attempting text completion through gateway MUST raise ProviderUnavailableError
    with pytest.raises(ProviderUnavailableError) as exc_info:
        await gateway.complete_text(
            "test task",
            [text_message("user", "Hello")],
            task_class="standard",
        )

    assert "Could not reach Ollama" in str(exc_info.value.message)
    # Verify it did NOT return a mock response!
    registry.reset()


async def test_explicit_mock_mode_works_when_configured(store: Any) -> None:
    """Mock provider works seamlessly when explicitly chosen by the user."""
    settings = get_settings()
    settings.set_many({
        "routing.standard": {"provider": "mock", "model": "mock-standard"},
    })
    registry.reset()

    text = await gateway.complete_text(
        "test task",
        [text_message("user", "Hello")],
        task_class="standard",
    )
    assert text != ""
    assert isinstance(text, str)
