"""Vision LLM client — analyses screenshots of the map to suggest restyling.

Provider-agnostic over the OpenAI-compatible Chat Completions API with image
inputs. Same selection pattern as `clients/llm.py`:

    VISION_PROVIDER=qwen        -> DashScope (qwen-vl-max). Best once your
                                   Alibaba account is active.
    VISION_PROVIDER=openrouter  -> OpenRouter, default model
                                   qwen/qwen2.5-vl-32b-instruct. Recommended
                                   while DashScope is pending — works from HK,
                                   cheap (~$0.40/M input tokens), openly
                                   licensed Qwen-VL with vision quality very
                                   close to qwen-vl-max.
    VISION_PROVIDER=deepseek    -> placeholder for when DeepSeek publishes a
                                   vision API. Today falls through to canned
                                   suggestions.

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
        if provider not in ("qwen", "deepseek", "openrouter"):
            log.warning("Unknown VISION_PROVIDER=%r; using 'qwen'.", provider)
            provider = "qwen"
        self.provider = provider

        if provider == "openrouter":
            self.api_key = s.vision_api_key or s.openrouter_api_key
            self.base_url = (s.vision_base_url or s.openrouter_base_url).rstrip("/")
            self.model = s.openrouter_vision_model
        elif provider == "deepseek":
            self.api_key = s.vision_api_key or s.deepseek_api_key
            self.base_url = (s.vision_base_url or s.deepseek_base_url).rstrip("/")
            self.model = s.deepseek_vision_model
        else:
            self.api_key = s.vision_api_key or s.dashscope_api_key
            self.base_url = (s.vision_base_url or s.dashscope_base_url).rstrip("/")
            self.model = s.qwen_vision_model

        self._client = httpx.AsyncClient(timeout=60.0)
        # Holds the most recent failure reason for the orchestrator to
        # surface back to the user, instead of a generic "returned nothing".
        self.last_error: str | None = None

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
        self.last_error = None
        if not self.api_key:
            self.last_error = f"no API key configured for VISION_PROVIDER={self.provider}"
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
        headers: dict[str, str] = {"Authorization": f"Bearer {self.api_key}"}
        if self.provider == "openrouter":
            # OpenRouter uses these headers for attribution/discoverability.
            # Both optional; included as good citizens.
            headers["HTTP-Referer"] = "https://github.com/echo-golf-oscar-romeo/tochka"
            headers["X-Title"] = "tochka — location intelligence"
        try:
            r = await self._client.post(
                f"{self.base_url}/chat/completions",
                json=body,
                headers=headers,
            )
        except httpx.HTTPError as e:
            self.last_error = f"network error: {e}"
            log.warning("Vision (%s/%s) network error: %s", self.provider, self.model, e)
            return None

        # Surface the actual response body on non-2xx so we can tell apart
        # "model unavailable", "invalid key", "rate limit", etc. instead of
        # the silent "returned nothing" the user sees in the UI.
        if r.status_code >= 400:
            body_preview = r.text[:500] if r.text else "(empty body)"
            self.last_error = f"HTTP {r.status_code}: {body_preview[:200]}"
            log.warning(
                "Vision (%s/%s) HTTP %s: %s",
                self.provider, self.model, r.status_code, body_preview,
            )
            return None

        try:
            data = r.json()
        except ValueError as e:
            self.last_error = f"non-JSON response: {r.text[:120]}"
            log.warning("Vision (%s/%s) non-JSON response: %s; preview: %s",
                        self.provider, self.model, e, r.text[:300])
            return None

        # OpenRouter sometimes returns a top-level {"error": {...}} with HTTP 200.
        if isinstance(data, dict) and data.get("error"):
            err = data["error"]
            msg = err.get("message") if isinstance(err, dict) else str(err)
            self.last_error = f"provider error: {msg}"
            log.warning("Vision (%s/%s) provider error: %s", self.provider, self.model, msg)
            return None

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            self.last_error = f"malformed response shape: {e}"
            log.warning("Vision (%s/%s) malformed response: %s; raw: %s",
                        self.provider, self.model, e, str(data)[:300])
            return None

        if isinstance(content, list):
            # Some providers return content as a list of parts.
            texts = [p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text"]
            content = "\n".join(t for t in texts if t)
        return (content or "").strip() or None


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
