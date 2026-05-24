"""LLM-backed helpers used by the orchestrator.

Each helper has the same shape: real LLM call if the active provider's API
key is present and the call succeeds; otherwise return None and let the
caller fall back to a hard-coded string. Active provider is selected by
the LLM_PROVIDER env var (qwen | deepseek). This keeps the demo defensible
even if WiFi drops or the provider's endpoint is misbehaving on the day.
"""

from __future__ import annotations

import logging

from app.clients.llm import get_llm
from app.models.network import Network
from app.orchestrator.prompts import (
    CLARIFY_USER_PROMPT,
    NARRATIVE_USER_PROMPT,
    SYSTEM_ORCHESTRATOR,
)

log = logging.getLogger(__name__)


def _network_summary(network: Network) -> str:
    n = len(network.locations)
    districts = {loc.raw_fields.get("district") for loc in network.locations if loc.raw_fields.get("district")}
    types = {loc.raw_fields.get("type") for loc in network.locations if loc.raw_fields.get("type")}
    parts = [f"{n} locations"]
    if districts:
        parts.append(f"across {len(districts)} districts ({', '.join(sorted(d for d in districts if d))})")
    if types:
        parts.append(f"types: {', '.join(sorted(t for t in types if t))}")
    return "; ".join(parts)


async def llm_clarify(
    network: Network,
    *,
    poi_type: str,
    options: list[str],
) -> str | None:
    """Generate the clarifying question. Returns None on failure (caller falls back)."""
    llm = get_llm()
    if not llm.has_key:
        return None
    text = await llm.chat(
        messages=[
            {"role": "system", "content": SYSTEM_ORCHESTRATOR},
            {"role": "user", "content": CLARIFY_USER_PROMPT.format(
                poi_type=poi_type or "unknown",
                summary=_network_summary(network),
                options_csv=", ".join(options),
            )},
        ],
        temperature=0.3,
        max_tokens=120,
    )
    if not text:
        return None
    # Defensive: collapse to a single line, ensure it ends with '?'.
    one_line = " ".join(text.split())
    if not one_line.endswith("?"):
        one_line = one_line.rstrip(".") + "?"
    return one_line


async def llm_plan(
    network: Network,
    *,
    archetypes: list[str],
    tool_names: list[str],
) -> str | None:
    """A one-or-two-sentence narration of the plan for the chosen task.

    Falls back to None if the LLM is unavailable; the orchestrator emits a
    hand-rolled string in that case so the user still sees reasoning.
    """
    llm = get_llm()
    if not llm.has_key:
        return None
    prompt = (
        f"The user wants to run the following analytical archetype(s) on a Hong Kong "
        f"network of {len(network.locations)} locations: {', '.join(archetypes)}.\n\n"
        f"The deterministic tools you can sequence are: {', '.join(tool_names)}.\n\n"
        f"In ONE sentence (max 2), explain what the analysis will produce, leading "
        f"with the most consequential output. Speak directly to the user (\"I'll …\"). "
        f"No bullet points, no preamble. Plain text only."
    )
    text = await llm.chat(
        messages=[
            {"role": "system", "content": SYSTEM_ORCHESTRATOR},
            {"role": "user", "content": prompt},
        ],
        temperature=0.4,
        max_tokens=120,
    )
    if not text:
        return None
    return " ".join(text.split())   # collapse newlines


async def llm_narrate(
    *,
    section_id: str,
    section_title: str,
    fallback: str,
    kpis: dict[str, str] | None,
    callouts: list[str] | None,
) -> str | None:
    """Rewrite a section description. Returns None on failure (keep fallback)."""
    llm = get_llm()
    if not llm.has_key:
        return None
    text = await llm.chat(
        messages=[
            {"role": "system", "content": SYSTEM_ORCHESTRATOR},
            {"role": "user", "content": NARRATIVE_USER_PROMPT.format(
                section_id=section_id,
                section_title=section_title,
                kpis=kpis or {},
                callouts=callouts or [],
                fallback=fallback,
            )},
        ],
        temperature=0.4,
        max_tokens=400,
    )
    if not text:
        return None
    return text.strip().strip('"').strip()
