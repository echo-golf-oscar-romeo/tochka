"""LLM-backed helpers used by the orchestrator.

Each helper has the same shape: real LLM call if the active provider's API
key is present and the call succeeds; otherwise return None and let the
caller fall back to a hard-coded string. Active provider is selected by
the LLM_PROVIDER env var (qwen | deepseek). This keeps the demo defensible
even if WiFi drops or the provider's endpoint is misbehaving on the day.
"""

from __future__ import annotations

import logging
from pathlib import Path

from app.clients.llm import get_llm
from app.models.network import Network
from app.orchestrator.prompts import (
    CLARIFY_USER_PROMPT,
    NARRATIVE_USER_PROMPT,
    SYSTEM_ORCHESTRATOR,
)

log = logging.getLogger(__name__)

_REPORT_SKILL_PATH = Path(__file__).resolve().parent / "SKILL_report.md"
_REPORT_SKILL: str | None = None


def _report_skill() -> str:
    global _REPORT_SKILL
    if _REPORT_SKILL is None:
        try:
            _REPORT_SKILL = _REPORT_SKILL_PATH.read_text(encoding="utf-8")
        except OSError:
            _REPORT_SKILL = ""
    return _REPORT_SKILL


# The analytical arsenal the methodology narrator can draw on. Kept here (not
# in prompts.py) so it stays in sync with what app/tools actually implements.
METHOD_ARSENAL = """\
Available analytical methods (all implemented, deterministic):
- Catchments: Mapbox walking/driving isochrones; metric buffers (ST_Buffer via EPSG:3857).
- Demand: Kontur population on H3 r8 hexes; CSDI iGeoCom POIs (37k, by category);
  competitor banks/ATMs from OSM; on-demand OSM fetch for any category.
- Gravity & decay: Huff share matrices with exponential / gaussian / power /
  linear distance-decay kernels.
- Coverage optimisation: p-median (min weighted distance), LSCP (fewest sites
  to cover all demand), MCLP (max demand covered with P sites), nearest-
  facility location-allocation — PuLP/CBC MILPs with greedy fallbacks.
- Spatial statistics: global Moran's I, local Moran (LISA hot/cold clusters),
  Getis-Ord Gi* hot spots, IDW interpolation, 2SFCA accessibility.
- Site selection: multi-criteria suitability ranking (weighted overlay),
  best-new-point by marginal net-new coverage, whitespace gap detection.
- Look-alikes: per-location spatial-context embeddings (population,
  competition, CSDI POI mix, centrality) → cosine similarity, KMeans
  segmentation, drivers regression with over/under-performance residuals."""


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
    """Multi-paragraph methodology — what the analysis will produce, why this
    sequence, and what each step contributes. Shown verbatim in the
    Methodology pop-over while tools run.

    Falls back to None if the LLM is unavailable; the orchestrator emits a
    hand-rolled string in that case so the user still sees reasoning.
    """
    llm = get_llm()
    if not llm.has_key:
        return None
    summary = _network_summary(network)
    prompt = (
        f"You are designing a Hong Kong location-intelligence methodology for "
        f"the archetype(s): {', '.join(archetypes)}.\n\n"
        f"Network summary: {summary}.\n\n"
        f"{METHOD_ARSENAL}\n\n"
        f"Deterministic tools queued for THIS run (in roughly the order I'll call them):\n"
        f"  {', '.join(tool_names)}\n\n"
        f"Write the methodology as a short, executive-readable plan:\n"
        f"  • Lead with ONE sentence stating the headline output (what the user "
        f"will see at the end).\n"
        f"  • Then a SECOND sentence giving your REASONING — why this sequence of "
        f"tools is the right way to answer the question, and what the chief risk is.\n"
        f"  • Then 3–5 numbered steps, each tying a tool to the concrete intermediate "
        f"output it produces (e.g. '1. isochrone_walk → 10-min walking polygons '\n"
        f"    'around each branch, the catchment we'll measure demand inside.').\n\n"
        f"Speak in first person (\"I'll …\"). No markdown headings. Plain text only."
    )
    text = await llm.chat(
        messages=[
            {"role": "system", "content": SYSTEM_ORCHESTRATOR},
            {"role": "user", "content": prompt},
        ],
        temperature=0.45,
        max_tokens=600,
    )
    if not text:
        return None
    return text.strip()


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
    system = SYSTEM_ORCHESTRATOR
    skill = _report_skill()
    if skill:
        system += "\n\n" + skill
    text = await llm.chat(
        messages=[
            {"role": "system", "content": system},
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
