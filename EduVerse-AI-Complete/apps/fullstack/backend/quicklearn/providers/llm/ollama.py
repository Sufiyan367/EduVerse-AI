"""Ollama — fully local inference. Nothing leaves the machine.

This is the provider that makes the project's central privacy claim literal rather than
aspirational, so it needs to work as smoothly as the cloud options.
"""

from __future__ import annotations

import logging

from ..base import ConnectionResult, ModelInfo
from ..http import request_json
from .openai_compat import OpenAICompatLLM, StructuredMode

log = logging.getLogger(__name__)


class OllamaLLM(OpenAICompatLLM):
    name = "ollama"
    label = "Ollama"
    default_base_url = "http://localhost:11434/v1"
    structured_mode: StructuredMode = "json_object"
    requires_api_key = False
    is_local = True
    _context_window = 32_768

    async def list_models(self) -> list[ModelInfo]:
        """Enumerate pulled models via Ollama's native endpoint, falling back to /v1/models."""
        native_base = self.base_url.removesuffix("/v1").rstrip("/")
        try:
            data = await request_json(
                self._client,
                "GET",
                f"{native_base}/api/tags",
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
            log.debug("Ollama native /api/tags failed, falling back to OpenAI compat /models: %s", exc)

        return await super().list_models()

    async def test_connection(self) -> ConnectionResult:
        """Validate connection and provide actionable guidance if Ollama is not running."""
        res = await super().test_connection()
        if not res.ok and any(
            err in res.message.lower()
            for err in ("connecterror", "connection refused", "all connection attempts failed", "unavailable")
        ):
            return ConnectionResult(
                ok=False,
                message=(
                    f"Ollama is not reachable at {self.base_url}. "
                    "Make sure Ollama is installed and running (`ollama serve` or open the Ollama application), "
                    "and at least one model is downloaded (e.g. `ollama pull llama3.2` or `ollama pull qwen2.5`)."
                ),
                models=[],
            )
        if res.ok and not res.models:
            return ConnectionResult(
                ok=False,
                message=(
                    f"Connected to Ollama at {self.base_url}, but no models are installed. "
                    "Pull a model first using `ollama pull llama3.2` or `ollama pull qwen2.5` before attempting inference."
                ),
                models=[],
            )
        return res
