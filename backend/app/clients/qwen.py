"""DashScope (Qwen) client wrapper.

We default to Qwen-Agent for the tool-calling loop. This client is the
lower-level escape hatch — single-turn completion, narrative writing, the
clarifying-question generator.

DashScope speaks an OpenAI-compatible REST endpoint. We use httpx directly
to avoid pinning the openai SDK; switch to qwen-agent's higher-level Assistant
class once we're wiring the tool loop.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.config import get_settings


class QwenClient:
    def __init__(self) -> None:
        s = get_settings()
        self.api_key = s.dashscope_api_key
        self.base_url = s.dashscope_base_url.rstrip("/")
        self.model = s.qwen_model
        self._client = httpx.AsyncClient(timeout=30.0)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def chat(self, messages: list[dict[str, str]], **kwargs: Any) -> str:
        """Single-turn completion. Returns the assistant text."""
        if not self.api_key:
            raise RuntimeError("DASHSCOPE_API_KEY is not set.")
        # DashScope OpenAI-compatible endpoint shape:
        # POST {base_url}/services/aigc/text-generation/generation
        # Body: {"model": ..., "input": {"messages": [...]}, "parameters": {...}}
        body = {
            "model": self.model,
            "input": {"messages": messages},
            "parameters": {"result_format": "message", **kwargs},
        }
        r = await self._client.post(
            f"{self.base_url}/services/aigc/text-generation/generation",
            json=body,
            headers={"Authorization": f"Bearer {self.api_key}"},
        )
        r.raise_for_status()
        data = r.json()
        # Path: output.choices[0].message.content
        return data["output"]["choices"][0]["message"]["content"]


_singleton: QwenClient | None = None


def get_qwen() -> QwenClient:
    global _singleton
    if _singleton is None:
        _singleton = QwenClient()
    return _singleton
