"""LLM client — provider-agnostic over the OpenAI-compatible Chat Completions API.

Both DashScope (Qwen) and DeepSeek expose the same endpoint shape:

    POST {base_url}/chat/completions
    Body: {"model", "messages": [{role, content}], "temperature", "max_tokens"}
    Auth: Bearer <api_key>

Tochka switches providers via the LLM_PROVIDER env var ("qwen" | "deepseek").
Default is "qwen"; "deepseek" exists as a workaround while a DashScope account
is pending activation.

For the full tool-calling loop we'll graduate to qwen-agent.Assistant; see
QWEN-AGENT-HOOK in orchestrator/agent.py. This client covers single-turn
completions: the clarifying question and per-section narrative writing.

Graceful failure: returns None on missing key, network error, or malformed
response. Callers handle the None case by falling back to a hard-coded string.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import get_settings

log = logging.getLogger(__name__)


class LLMClient:
    def __init__(self) -> None:
        s = get_settings()
        provider = (s.llm_provider or "qwen").strip().lower()
        if provider not in ("qwen", "deepseek"):
            log.warning("Unknown LLM_PROVIDER=%r; falling back to 'qwen'.", provider)
            provider = "qwen"
        self.provider = provider
        if provider == "deepseek":
            self.api_key = s.deepseek_api_key
            self.base_url = s.deepseek_base_url.rstrip("/")
            self.model = s.deepseek_model
        else:
            self.api_key = s.dashscope_api_key
            self.base_url = s.dashscope_base_url.rstrip("/")
            self.model = s.qwen_model
        self._client = httpx.AsyncClient(timeout=30.0)

    @property
    def has_key(self) -> bool:
        return bool(self.api_key)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.3,
        max_tokens: int = 600,
        model: str | None = None,
        **extra: Any,
    ) -> str | None:
        """Single-turn completion.

        Returns the assistant text on success, or None on graceful failure
        (no API key, network error, malformed response).
        """
        if not self.api_key:
            log.info("LLM (%s): no API key set; falling back to canned text.", self.provider)
            return None

        body = {
            "model": model or self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **extra,
        }
        try:
            r = await self._client.post(
                f"{self.base_url}/chat/completions",
                json=body,
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            r.raise_for_status()
            data = r.json()
            content = data["choices"][0]["message"]["content"]
            if isinstance(content, str):
                return content.strip() or None
            return None
        except httpx.HTTPError as e:
            log.warning("LLM (%s) HTTP error: %s", self.provider, e)
            return None
        except (KeyError, IndexError, ValueError) as e:
            log.warning("LLM (%s) response shape unexpected: %s", self.provider, e)
            return None


_singleton: LLMClient | None = None


def get_llm() -> LLMClient:
    global _singleton
    if _singleton is None:
        _singleton = LLMClient()
    return _singleton
