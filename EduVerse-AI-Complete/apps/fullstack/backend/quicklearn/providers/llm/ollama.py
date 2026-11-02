"""Ollama — fully local inference. Nothing leaves the machine.

This is the primary provider that makes EduVerse AI's central privacy claim literal.
Uses native Ollama /api/chat with configurable reasoning (thinking modes),
hardware-optimized context limits, keep_alive management, multimodal vision,
and privacy-preserving thinking trace filtering, while retaining dual OpenAI-compatible
fallback support.
"""

from __future__ import annotations

import json
import logging
import os
import re
from collections.abc import AsyncIterator, Sequence
from typing import Any, Literal

import httpx

from ...errors import ProviderResponseError, ProviderUnavailableError
from ..base import (
    ConnectionResult,
    ContentPart,
    LLMProvider,
    LLMResponse,
    Message,
    ModelInfo,
)
from ..http import DEFAULT_TIMEOUT, build_client, request_json
from .openai_compat import OpenAICompatLLM, StructuredMode

log = logging.getLogger(__name__)

ThinkingLevel = Literal["high", "medium", "low", "off"]


def normalize_ollama_urls(raw_url: str) -> tuple[str, str]:
    """Normalize input Ollama URL into (native_base, v1_base).
    
    Accepts:
      - 'http://127.0.0.1:11434'
      - 'http://127.0.0.1:11434/v1'
      - 'http://127.0.0.1:11434/v1/'
      - 'http://localhost:11434'
    Returns:
      (native_base, v1_base) where:
      native_base = 'http://127.0.0.1:11434' (for /api/tags, /api/chat, /api/show)
      v1_base = 'http://127.0.0.1:11434/v1' (for /models, /chat/completions)
    """
    clean = (raw_url or "http://127.0.0.1:11434").strip().rstrip("/")
    if clean.endswith("/v1"):
        native_base = clean[:-3].rstrip("/")
        v1_base = clean
    else:
        native_base = clean
        v1_base = f"{clean}/v1"
    return native_base, v1_base


def _clean_thinking_trace(text: str) -> str:
    """Strip raw internal model scratchpad/thinking tokens from user-facing text.

    Privacy requirement: EduVerse never exposes internal <think>...</think> traces
    to the frontend or persistent chat logs.
    """
    if not text:
        return ""
    # Strip <think>...</think> blocks
    cleaned = re.sub(r"<think>[\s\S]*?</think>", "", text).strip()
    if not cleaned and text:
        # If model only generated think tags without outside content, strip tags cleanly
        cleaned = re.sub(r"</?think>", "", text).strip()
    # Strip optional "Thinking Process: ... \n\n" prefix if present
    cleaned = re.sub(r"^Thinking Process:[\s\S]*?\n\n+", "", cleaned).strip()
    return cleaned


class OllamaLLM(OpenAICompatLLM):
    name = "ollama"
    label = "Ollama (Local Reasoning)"
    default_base_url = "http://localhost:11434/v1"
    structured_mode: StructuredMode = "json_object"
    requires_api_key = False
    is_local = True
    _context_window = 4096

    @property
    def supports_vision(self) -> bool:
        model_name = (self.default_model or "").lower()
        return any(v in model_name for v in ("vision", "vl", "llava", "minicpm", "bakllava", "moondream"))

    def __init__(
        self,
        *,
        base_url: str = "",
        api_key: str = "",
        model: str = "",
        think: str = "",
        num_ctx: int = 0,
        keep_alive: str = "",
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        raw_url = base_url or os.environ.get("OLLAMA_BASE_URL") or self.default_base_url
        self.native_base_url, self.v1_base_url = normalize_ollama_urls(raw_url)
        super().__init__(api_key=api_key, base_url=self.v1_base_url, extra_headers=extra_headers)

        self.default_model = model or os.environ.get("OLLAMA_MODEL") or "qwen3.5:4b"

        # Reasoning / Thinking mode
        raw_think = (think or os.environ.get("OLLAMA_THINK") or "high").lower()
        self.think: ThinkingLevel = raw_think if raw_think in ("high", "medium", "low", "off") else "high"

        # Context Window: default 4096 (can expand up to 8192 if VRAM permits)
        env_ctx = int(os.environ.get("OLLAMA_NUM_CTX") or 0)
        self.num_ctx = num_ctx or env_ctx or 4096

        # Keep alive in memory (default 10 minutes)
        self.keep_alive = keep_alive or os.environ.get("OLLAMA_KEEP_ALIVE") or "10m"

    @property
    def context_window(self) -> int:
        return self.num_ctx

    def _payload(
        self,
        messages: Sequence[Message],
        *,
        model: str,
        temperature: float,
        max_tokens: int,
        json_schema: dict[str, Any] | None = None,
        stream: bool = False,
    ) -> dict[str, Any]:
        payload = super()._payload(
            messages,
            model=model or self.default_model,
            temperature=temperature,
            max_tokens=max_tokens,
            json_schema=json_schema,
            stream=stream,
        )
        # Add Ollama-native options
        payload["options"] = {
            "num_predict": max_tokens,
            "num_ctx": self.num_ctx,
            "temperature": temperature,
        }
        payload["keep_alive"] = self.keep_alive
        if json_schema is not None:
            payload["think"] = False
        elif self.think not in ("off", False) and max_tokens > 500:
            payload["think"] = True
        else:
            payload["think"] = False
        return payload

    def _build_payload(
        self,
        messages: Sequence[Message],
        *,
        model: str = "",
        temperature: float = 0.3,
        max_tokens: int = 4096,
        json_schema: dict[str, Any] | None = None,
        stream: bool = False,
    ) -> dict[str, Any]:
        """Build native /api/chat payload with reasoning/thinking options."""
        ollama_msgs: list[dict[str, Any]] = []
        for m in messages:
            role = m.get("role", "user")
            raw_content = m.get("content", "")
            if isinstance(raw_content, str):
                ollama_msgs.append({"role": role, "content": raw_content})
            else:
                text_parts: list[str] = []
                images: list[str] = []
                for part in raw_content:
                    if part["type"] == "text":
                        text_parts.append(part["text"])
                    elif part["type"] == "image":
                        images.append(part["data"])
                entry: dict[str, Any] = {"role": role, "content": "\n".join(text_parts)}
                if images:
                    entry["images"] = images
                ollama_msgs.append(entry)

        target_model = model or self.default_model
        native_payload: dict[str, Any] = {
            "model": target_model,
            "messages": ollama_msgs,
            "stream": stream,
            "temperature": temperature,
            "options": {
                "num_predict": max_tokens,
                "num_ctx": self.num_ctx,
                "temperature": temperature,
            },
            "keep_alive": self.keep_alive,
        }
        if json_schema is not None:
            native_payload["think"] = False
            native_payload["format"] = json_schema
        elif self.think not in ("off", False) and max_tokens > 500:
            native_payload["think"] = True
        else:
            native_payload["think"] = False
        return native_payload

    async def complete(
        self,
        messages: Sequence[Message],
        *,
        model: str,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        json_schema: dict[str, Any] | None = None,
    ) -> LLMResponse:
        """Execute completion, trying native /api/chat and falling back to /chat/completions."""
        native_url = f"{self.native_base_url}/api/chat"

        target_model = model or self.default_model
        native_payload = self._build_payload(
            messages,
            model=target_model,
            temperature=temperature,
            max_tokens=max_tokens,
            json_schema=json_schema,
            stream=False,
        )

        try:
            resp = await self._client.post(native_url, json=native_payload)
            if resp.status_code == 200:
                data = resp.json()
                if "choices" in data:
                    return self._parse_completion(data, target_model)
                message = data.get("message") or {}
                raw_text = message.get("content") or ""
                if not raw_text and message.get("thinking"):
                    raw_text = message.get("thinking") or ""
                clean_text = _clean_thinking_trace(raw_text)
                return LLMResponse(
                    text=clean_text,
                    model=str(data.get("model") or target_model),
                    prompt_tokens=int(data.get("prompt_eval_count") or 0),
                    completion_tokens=int(data.get("eval_count") or 0),
                    finish_reason="stop" if data.get("done") else "unknown",
                    raw=data,
                )
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            raise ProviderUnavailableError(
                f"Could not reach {self.label} at {self.base_url} ({exc}). Is the daemon running?",
                provider=self.name,
            ) from exc
        except Exception as exc:
            log.debug("Native /api/chat failed (%s), falling back to OpenAI compat: %s", type(exc).__name__, exc)

        # Fallback to OpenAI compatible /chat/completions endpoint
        res = await super().complete(
            messages,
            model=target_model,
            temperature=temperature,
            max_tokens=max_tokens,
            json_schema=json_schema,
        )
        # Scrub thinking trace from response
        clean_text = _clean_thinking_trace(res.text)
        return LLMResponse(
            text=clean_text,
            model=res.model,
            prompt_tokens=res.prompt_tokens,
            completion_tokens=res.completion_tokens,
            finish_reason=res.finish_reason,
            raw=res.raw,
        )

    async def stream(
        self,
        messages: Sequence[Message],
        *,
        model: str,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        """Stream response tokens while suppressing raw thinking scratchpad tokens."""
        native_url = f"{self.native_base_url}/api/chat"
        target_model = model or self.default_model

        payload = self._build_payload(
            messages,
            model=target_model,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )

        in_think = False

        def _filter_delta(delta: str) -> str:
            nonlocal in_think
            while "<think>" in delta and "</think>" in delta:
                pre = delta.split("<think>", 1)[0]
                post = delta.split("</think>", 1)[1]
                delta = pre + post

            if "<think>" in delta:
                in_think = True
                delta, _ = delta.split("<think>", 1)

            if in_think:
                if "</think>" in delta:
                    in_think = False
                    _, delta = delta.split("</think>", 1)
                else:
                    delta = ""
            return delta

        try:
            async with self._client.stream("POST", native_url, json=payload) as response:
                if response.is_success:
                    async for line in response.aiter_lines():
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            item = json.loads(line)
                            msg = item.get("message") or {}
                            raw_content = msg.get("content") or ""
                            delta = _filter_delta(raw_content)
                            if delta:
                                yield delta
                        except Exception:
                            continue
                    return
        except httpx.ConnectError:
            raise
        except Exception as exc:
            log.debug("Native streaming failed, falling back to OpenAI compat: %s", exc)

        # Fallback to OpenAI compatible streaming
        async for chunk in super().stream(
            messages,
            model=target_model,
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            delta = _filter_delta(chunk)
            if delta:
                yield delta

    async def list_models(self) -> list[ModelInfo]:
        """Enumerate pulled models via Ollama's native endpoint, falling back to /v1/models."""
        try:
            data = await request_json(
                self._client,
                "GET",
                f"{self.native_base_url}/api/tags",
                provider=self.name,
                label=self.label,
            )
            models = []
            for item in data.get("models") or []:
                if not isinstance(item, dict):
                    continue
                model_id = item.get("model") or item.get("name")
                if not model_id:
                    continue
                details = item.get("details") or {}
                bits = [
                    str(details.get(k))
                    for k in ("parameter_size", "quantization_level")
                    if details.get(k)
                ]
                suffix = f" ({', '.join(bits)})" if bits else ""
                models.append(ModelInfo(id=str(model_id), name=f"{model_id}{suffix}"))
            if models:
                return sorted(models, key=lambda m: m.id)
        except Exception as exc:
            log.debug("Ollama native /api/tags failed, falling back to OpenAI compat /v1/models: %s", exc)

        return await super().list_models()

    async def test_connection(self) -> ConnectionResult:
        """Validate connection and provide actionable guidance.
        
        Distinguishes:
        1. Ollama daemon offline.
        2. Ollama daemon online, model missing.
        3. Model installed but inference failing.
        4. Model fully operational.
        """
        # 1. Check daemon status and list installed models
        try:
            models = await self.list_models()
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            return ConnectionResult(
                ok=False,
                message=(
                    f"Ollama daemon is offline at {self.native_base_url}. "
                    "Start it by running `ollama serve` or open the Ollama Windows application."
                ),
                models=[],
            )
        except httpx.TimeoutException:
            return ConnectionResult(
                ok=False,
                message=f"Local Ollama request timed out at {self.native_base_url}.",
                models=[],
            )
        except Exception as exc:
            msg = str(exc)
            if any(err in msg.lower() for err in ("connecterror", "connection refused", "all connection attempts failed", "unavailable")):
                return ConnectionResult(
                    ok=False,
                    message=(
                        f"Ollama daemon is offline at {self.native_base_url}. "
                        "Start it by running `ollama serve` or open the Ollama Windows application."
                    ),
                    models=[],
                )
            return ConnectionResult(ok=False, message=msg, models=[])

        # 2. Check if any model exists
        if not models:
            return ConnectionResult(
                ok=False,
                message=(
                    f"Connected to Ollama at {self.native_base_url}, but no models are installed. "
                    f"Run `ollama pull {self.default_model}` to download the required model."
                ),
                models=[],
            )

        # 3. Check if target model is present
        target_model = self.default_model
        clean_target = target_model.split(":")[0].lower()
        model_installed = any(
            m.id == target_model or m.id.lower().startswith(f"{clean_target}:") or m.id.lower() == clean_target
            for m in models
        )
        if not model_installed:
            return ConnectionResult(
                ok=False,
                message=(
                    f"Ollama daemon is online, but required model '{target_model}' is missing. "
                    f"Run: ollama pull {target_model}"
                ),
                models=models,
            )

        # 4. Verify model GGUF validity via /api/show
        try:
            show_resp = await self._client.post(
                f"{self.native_base_url}/api/show",
                json={"model": target_model},
                timeout=5.0,
            )
            if show_resp.status_code != 200:
                return ConnectionResult(
                    ok=False,
                    message=f"Model '{target_model}' manifest check failed with HTTP {show_resp.status_code}.",
                    models=models,
                )
        except Exception as exc:
            return ConnectionResult(
                ok=False,
                message=f"Model '{target_model}' manifest inspection failed: {exc}",
                models=models,
            )

        # 5. Operational inference verification
        try:
            probe_payload = {
                "model": target_model,
                "messages": [{"role": "user", "content": "ping"}],
                "stream": False,
                "think": False,
                "options": {"num_predict": 1},
            }
            resp = await self._client.post(
                f"{self.native_base_url}/api/chat",
                json=probe_payload,
                timeout=5.0,
            )
            if resp.status_code != 200:
                return ConnectionResult(
                    ok=False,
                    message=f"Model '{target_model}' is installed, but inference returned HTTP {resp.status_code}: {resp.text}",
                    models=models,
                )
        except httpx.TimeoutException:
            # Model is valid and currently busy generating another request in Ollama queue
            pass
        except Exception as exc:
            return ConnectionResult(
                ok=False,
                message=f"Model '{target_model}' is installed, but inference probe failed: {exc}",
                models=models,
            )

        return ConnectionResult(
            ok=True,
            message=f"Connected to Ollama — model '{target_model}' fully operational ({len(models)} model(s) available).",
            models=models,
        )


async def call_ollama_text(
    prompt: str,
    system: str = "",
    model: str = "qwen3.5:4b",
    temperature: float = 0.2,
    max_tokens: int = 2048,
) -> str:
    """Direct helper to call local Ollama instance with optional system prompt and clean thinking trace filtering."""
    base_url = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    native_base, _ = normalize_ollama_urls(base_url)
    url = f"{native_base}/api/chat"
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
