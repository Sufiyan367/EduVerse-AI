"""LM Studio — local inference behind an OpenAI-compatible server."""

from __future__ import annotations

from ..base import ConnectionResult
from .openai_compat import OpenAICompatLLM, StructuredMode


class LMStudioLLM(OpenAICompatLLM):
    name = "lmstudio"
    label = "LM Studio"
    default_base_url = "http://localhost:1234/v1"
    structured_mode: StructuredMode = "json_schema"
    requires_api_key = False
    is_local = True
    _context_window = 32_768

    async def test_connection(self) -> ConnectionResult:
        """Validate connection and provide actionable guidance if LM Studio is not running."""
        res = await super().test_connection()
        if not res.ok and any(
            err in res.message.lower()
            for err in ("connecterror", "connection refused", "all connection attempts failed", "unavailable")
        ):
            return ConnectionResult(
                ok=False,
                message=(
                    f"LM Studio local server is not reachable at {self.base_url}. "
                    "Open LM Studio, load a model into memory, and click 'Start Server' on the Local Server tab (port 1234)."
                ),
                models=[],
            )
        if res.ok and not res.models:
            return ConnectionResult(
                ok=False,
                message=(
                    f"Connected to LM Studio at {self.base_url}, but no models are loaded. "
                    "Load a model in LM Studio before starting inference."
                ),
                models=[],
            )
        return res
