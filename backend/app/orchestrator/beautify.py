"""Beautify-map agent.

One iteration:
  1. Receive a PNG screenshot of the current map view + the current layer
     paint properties from the frontend.
  2. Send both to a vision LLM with a prompt that asks for specific
     MapLibre paint property changes (no narrative, JSON only).
  3. Parse the JSON, sanity-check it, return structured suggestions.

The frontend applies the returned suggestions and may call again with the
new screenshot. Each call is independent; we don't keep state server-side.

When the vision LLM is unavailable (no API key / provider failure), we fall
back to a small hand-rolled heuristic — bumping competitor circle radius
down a notch and lifting isochrone fill opacity if it's near-invisible —
so the button still feels alive on stage.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.clients.vision import get_vision, is_valid_png_b64

log = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are a senior cartographer reviewing a Hong Kong location-intelligence map. Your job is to suggest specific MapLibre paint-property changes that make the map more readable, beautiful, and informative. Be opinionated and tasteful.

Rules:
- Output ONLY a JSON object (no prose, no markdown). The object MUST have:
    {
      "notes": "<one short sentence describing what you changed and why>",
      "updates": [
        { "layer_id": "<existing layer id>", "paint": { "<paint-prop>": <value>, ... } },
        ...
      ]
    }
- Only suggest changes for layers that exist in the input.
- Only use real MapLibre paint properties (circle-color, circle-radius,
  circle-opacity, circle-stroke-color, circle-stroke-width, fill-color,
  fill-opacity, line-color, line-width, line-opacity).
- Hex colors only ("#RRGGBB"). No named colors.
- Keep the palette tasteful and accessible. Avoid neon. Prefer at most 3
  colours total across all layers.
- If a layer is already well-styled, omit it from updates.
- Maximum 4 updates per call.
"""


USER_TEMPLATE = """Iteration {iter_n} of {iter_max}.

The map below shows the user's network of locations (user-network), walking catchments (isochrones), and competitor banks (competitors). The current layer paint properties are:

{current_styles_json}

Look at the screenshot. What 2–4 specific paint-property changes would make it look better and convey more meaning? Output the JSON object only."""


_JSON_OBJECT_RE = re.compile(r"\{[\s\S]*\}")


def _extract_json(text: str) -> dict | None:
    m = _JSON_OBJECT_RE.search(text)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


_ALLOWED_PAINT_PROPS = {
    "circle-color", "circle-radius", "circle-opacity",
    "circle-stroke-color", "circle-stroke-width",
    "fill-color", "fill-opacity", "fill-outline-color",
    "line-color", "line-width", "line-opacity",
}
_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _sanitise_updates(updates: list[dict], known_layer_ids: set[str]) -> list[dict]:
    out: list[dict] = []
    for u in updates[:6]:
        if not isinstance(u, dict):
            continue
        layer_id = u.get("layer_id")
        paint = u.get("paint")
        if not isinstance(layer_id, str) or layer_id not in known_layer_ids:
            continue
        if not isinstance(paint, dict):
            continue
        cleaned: dict[str, Any] = {}
        for k, v in paint.items():
            if k not in _ALLOWED_PAINT_PROPS:
                continue
            # Hex colors: validate; numbers: clamp; otherwise drop.
            if "color" in k:
                if isinstance(v, str) and _HEX_RE.match(v):
                    cleaned[k] = v
            elif k in ("circle-radius", "circle-stroke-width", "line-width"):
                try:
                    n = float(v)
                    if 0 <= n <= 50:
                        cleaned[k] = n
                except (TypeError, ValueError):
                    pass
            elif "opacity" in k:
                try:
                    n = float(v)
                    if 0 <= n <= 1:
                        cleaned[k] = n
                except (TypeError, ValueError):
                    pass
        if cleaned:
            out.append({"layer_id": layer_id, "paint": cleaned})
    return out[:4]


def _looks_like_markdown_fence(text: str) -> str | None:
    """OpenRouter-Qwen sometimes wraps the JSON in ```json fences. Strip those."""
    import re as _re
    m = _re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    return m.group(1) if m else None


def _fallback_suggestions(current_styles: list[dict]) -> dict:
    """If the vision LLM is unavailable, propose a couple of safe nudges
    so the button still feels alive on stage."""
    updates: list[dict] = []
    for s in current_styles:
        lid = s.get("layer_id")
        paint = s.get("paint") or {}
        if lid == "competitors":
            if float(paint.get("circle-radius", 4)) > 3.5:
                updates.append({"layer_id": "competitors",
                                "paint": {"circle-radius": 3.5, "circle-opacity": 0.75}})
        elif lid == "isochrones":
            if float(paint.get("fill-opacity", 0.13)) < 0.18:
                updates.append({"layer_id": "isochrones",
                                "paint": {"fill-opacity": 0.18, "line-opacity": 0.7}})
        elif lid == "user-network":
            updates.append({"layer_id": "user-network",
                            "paint": {"circle-stroke-width": 2.0, "circle-radius": 8}})
    return {
        "notes": "Vision provider unavailable — applied a small hand-rolled refinement.",
        "updates": updates[:3],
        "provider": "fallback",
    }


async def run_beautify_turn(
    *,
    screenshot: str,
    current_styles: list[dict],
    iteration: int,
    iteration_max: int,
) -> dict[str, Any]:
    """Single beautify iteration. Returns:
       {notes, updates, provider}
    """
    if not is_valid_png_b64(screenshot):
        return {
            "notes": "The screenshot didn't decode as a PNG — try again.",
            "updates": [],
            "provider": "error",
            "error": "invalid_screenshot",
        }

    known_ids = {s.get("layer_id") for s in current_styles if s.get("layer_id")}
    vision = get_vision()
    if not vision.has_key:
        out = _fallback_suggestions(current_styles)
        return out

    prompt = USER_TEMPLATE.format(
        iter_n=iteration,
        iter_max=iteration_max,
        current_styles_json=json.dumps(current_styles, indent=2),
    )
    raw = await vision.analyse_image(
        image_b64_or_uri=screenshot,
        prompt=prompt,
        system=SYSTEM_PROMPT,
        temperature=0.3,
        max_tokens=900,
    )
    if not raw:
        out = _fallback_suggestions(current_styles)
        out["notes"] = "Vision call failed; applied a small hand-rolled refinement."
        return out

    parsed = _extract_json(raw)
    if not parsed:
        # OpenRouter-Qwen sometimes ships JSON wrapped in ``` fences. Try that.
        fenced = _looks_like_markdown_fence(raw)
        if fenced:
            parsed = _extract_json(fenced)
    if not parsed:
        log.info("Beautify: could not parse JSON from vision output: %.200s", raw)
        out = _fallback_suggestions(current_styles)
        out["notes"] = "Vision response wasn't valid JSON; applied a small hand-rolled refinement."
        return out

    notes = str(parsed.get("notes") or "").strip() or "Refinement applied."
    raw_updates = parsed.get("updates") if isinstance(parsed.get("updates"), list) else []
    updates = _sanitise_updates(raw_updates, known_ids)
    return {
        "notes": notes,
        "updates": updates,
        "provider": vision.provider,
    }
