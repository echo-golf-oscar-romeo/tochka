"""Vision LLM client — analyses screenshots of the map to suggest restyling.

Provider-agnostic over the OpenAI-compatible Chat Completions API with image
inputs. Same model selection pattern as `clients/llm.py`:

    VISION_PROVIDER=qwen      -> DashScope, model = qwen-vl-max (default)
    VISION_PROVIDER=deepseek  -> DeepSeek, model = deepseek-vl2 (not yet
                                 available on api.deepseek.com as of writing;
                                 wired here for forward compatibility)

If the active provider has no API key configured the client returns None
gracefully and the orchestrator falls back to a hand-rolled style suggestion
so the beautify button still feels responsive.
"""

from __future__ import annotations

import base64
import logging
from typing import Any

import httpx

from app.config import get_settings

log = logging.getLogger(__name__)


def _strip_data_uri(data: str) -> tuple[str, str]:
    """Accept either raw base64 or a data URI; return (mime, base64)."""
    if data.startswith("data:"):
        try:
            head, b64 = data.split(",", 1)
            mime = head[5:].split(";")[0] or "image/png"
            return mime, b64
        except ValueError:
            return "image/png", data
    return "image/png", data


class VisionClient:
    def __init__(self) -> None:
        s = get_settings()
        provider = (s.vision_provider or "qwen").strip().lower()
        if provider not in ("qwen", "deepseek"):
            log.warning("Unknown VISION_PROVIDER=%r; using 'qwen'.", provider)
            provider = "qwen"
        self.provider = provider

        if provider == "deepseek":
            self.api_key = s.vision_api_key or s.deepseek_api_key
            self.base_url = (s.vision_base_url or s.deepseek_base_url).rstrip("/")
            self.model = s.deepseek_vision_model
        else:
            self.api_key = s.vision_api_key or s.dashscope_api_key
            self.base_url = (s.vision_base_url or s.dashscope_base_url).rstrip("/")
            self.model = s.qwen_vision_model

        self._client = httpx.AsyncClient(timeout=60.0)

    @property
    def has_key(self) -> bool:
        return bool(self.api_key)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def analyse_image(
        self,
        *,
        image_b64_or_uri: str,
        prompt: str,
        system: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 1200,
    ) -> str | None:
        """Send a single image + prompt; return the assistant text or None."""
        if not self.api_key:
            log.info("Vision (%s): no API key set.", self.provider)
            return None

        mime, b64 = _strip_data_uri(image_b64_or_uri)
        data_uri = f"data:{mime};base64,{b64}"

        messages: list[dict[str, Any]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": data_uri}},
            ],
        })

        body = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
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
            if isinstance(content, list):
                # Some providers return content as a list of parts.
                texts = [p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text"]
                content = "\n".join(t for t in texts if t)
            return (content or "").strip() or None
        except httpx.HTTPError as e:
            log.warning("Vision (%s) HTTP error: %s", self.provider, e)
            return None
        except (KeyError, IndexError, ValueError) as e:
            log.warning("Vision (%s) malformed response: %s", self.provider, e)
            return None


_singleton: VisionClient | None = None


def get_vision() -> VisionClient:
    global _singleton
    if _singleton is None:
        _singleton = VisionClient()
    return _singleton


# ---------------------------------------------------------------------------
# Defensive helper for screenshots passed through HTTP — make sure we don't
# spend tokens on a malformed payload.
# ---------------------------------------------------------------------------

def is_valid_png_b64(data: str) -> bool:
    """Quick sanity check that the payload decodes to a PNG."""
    try:
        _, b64 = _strip_data_uri(data)
        raw = base64.b64decode(b64[:80] + "==")
        # PNG signature: 89 50 4E 47 0D 0A 1A 0A
        return raw[:8] == b"\x89PNG\r\n\x1a\n"
    except Exception:
        return False
