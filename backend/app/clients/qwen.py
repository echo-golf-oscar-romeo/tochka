"""DashScope (Qwen) client wrapper.

Uses the OpenAI-compatible endpoint at /compatible-mode/v1/chat/completions.
Same wire format as the openai SDK, so we can swap in `openai` later without
caller changes if we want. For now we go through httpx to avoid pinning that
SDK.

For the full tool-calling loop we'll graduate to qwen-agent.Assistant; see
QWEN-AGENT-HOOK in orchestrator/agent.py. This client covers single-turn
completions: the clarifying question and per-section narrative writing.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import get_settings

log = logging.getLogger(__name__)


class QwenClient:
    def __init__(self) -> None:
        s = get_settings()
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
        (no API key, network error, malformed response). Callers handle the
        None case by falling back to a hard-coded string.
        """
        if not self.api_key:
            log.info("Qwen: no API key set; falling back to canned text.")
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
            log.warning("Qwen HTTP error: %s", e)
            return None
        except (KeyError, IndexError, ValueError) as e:
            log.warning("Qwen response shape unexpected: %s", e)
            return None


_singleton: QwenClient | None = None


def get_qwen() -> QwenClient:
    global _singleton
    if _singleton is None:
        _singleton = QwenClient()
    return _singleton
