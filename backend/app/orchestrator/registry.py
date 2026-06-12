"""Analysis-step registry — the methodologist's tool shelf.

Every step the orchestrator can schedule lives here with a one-line
description (shown to the planning LLM), its data dependencies, and an async
runner. Runners read/write a shared `ctx` dict so later steps can consume
earlier outputs (isochrones → population → huff …), return styled map layers
(streamed to the client as soon as the step finishes), and optionally a
plain-English finding for the report.

The methodologist composes a plan as an ordered list of step names; the
orchestrator resolves dependencies (auto-inserting prerequisites) and
executes. Adding a new analytical capability = adding one entry here.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from app.models.network import Network
from app.tools import (
    competitors,
    demand,
    modeling,
    opportunity,
    rationalisation,
    reachability,
    viz,
)

log = logging.getLogger(__name__)


@dataclass
class StepResult:
    layers: list[dict] = field(default_factory=list)      # Layer model dumps
    summary: dict[str, Any] = field(default_factory=dict)  # for tool_result event
    finding: tuple[str, str] | None = None                 # (title, text) for the report


Runner = Callable[[Network, dict], Awaitable[StepResult]]


@dataclass
class Step:
    name: str
    description: str          # one line, shown to the methodologist LLM
    requires: tuple[str, ...] = ()   # ctx keys that must exist first
    produces: tuple[str, ...] = ()   # ctx keys this step fills
    run: Runner | None = None


# ---------------------------------------------------------------------------
# Base data steps
# ---------------------------------------------------------------------------

async def _run_isochrones(network: Network, ctx: dict) -> StepResult:
    isos = await reachability.isochrone_walk(network.locations, minutes=10)
    ctx["isochrones"] = isos
    return StepResult(
        layers=[viz.build_isochrones_layer(isos).model_dump()],
        summary={"n_polygons": len(isos)},
    )


async def _run_competitors(network: Network, ctx: dict) -> StepResult:
    comp = await competitors.competitors_in_radius(network.locations, radius_m=500)
    ctx["competitors"] = comp
    own = competitors.infer_own_brand(network.locations)
    summary: dict[str, Any] = {"n": len(comp)}
    if own:
        summary["excluded_own_brand"] = own
    return StepResult(
        layers=[viz.build_competitors_layer(comp).model_dump()],
        summary=summary,
    )


async def _run_population(network: Network, ctx: dict) -> StepResult:
    pop = await demand.population_in_polygon(ctx.get("isochrones", []))
    ctx["population"] = pop
    return StepResult(summary={"total": pop.get("total_population")})


async def _run_huff(network: Network, ctx: dict) -> StepResult:
    scores = await modeling.huff_model(
        network.locations, ctx.get("competitors", []), ctx.get("population", {}))
    ctx["scores"] = scores
    return StepResult(summary={"n_scored": len(scores)})


async def _run_anomalies(network: Network, ctx: dict) -> StepResult:
    anomalies = await modeling.anomaly_detect(ctx.get("scores", []))
    ctx["anomalies"] = anomalies
    return StepResult(
        layers=[viz.build_anomalies_layer(anomalies, network).model_dump()],
        summary={"outliers": len(anomalies)},
    )


async def _run_opportunity(network: Network, ctx: dict) -> StepResult:
    cells = await opportunity.opportunity_hexes(network.locations, top_n=60)
    ctx["opportunity_cells"] = cells
    top = cells[0]["properties"] if cells else {}
    finding = None
    if cells:
        finding = ("Uncovered demand", (
            f"The top uncovered cell holds {top.get('population', 0):,} residents "
            f"{int(top.get('distance_to_nearest_branch_m', 0)):,} m from the nearest branch."
        ))
    return StepResult(
        layers=[viz.build_opportunity_layer(cells).model_dump()],
        summary={"n_cells": len(cells)},
        finding=finding,
    )


async def _run_cannibalisation(network: Network, ctx: dict) -> StepResult:
    pairs = await rationalisation.cannibalisation_pairs(network.locations, max_distance_m=800)
    ctx["cannibalisation_pairs"] = pairs
    return StepResult(
        layers=[viz.build_cannibalisation_layer(pairs).model_dump()],
        summary={"n_pairs": len(pairs)},
    )


async def _run_district_choropleth(network: Network, ctx: dict) -> StepResult:
    from app.orchestrator.chat_tools import run_choropleth
    r = await run_choropleth(network=network, metric="population")
    if r.get("error") or not r.get("layer"):
        return StepResult(summary={"note": r.get("answer", "districts unavailable")})
    ctx["district_population"] = r.get("rows", [])
    return StepResult(
        layers=[r["layer"]],
        summary={"districts": len(r.get("rows", []))},
        finding=("District demand context", r["answer"]),
    )


# ---------------------------------------------------------------------------
# Advanced method steps — wrap the chat method handlers, which already
# return styled layers + plain-English interpretations.
# ---------------------------------------------------------------------------

def _method_runner(handler_name: str, title: str, params: dict | None = None) -> Runner:
    async def _run(network: Network, ctx: dict) -> StepResult:
        from app.orchestrator import method_tools
        handler = getattr(method_tools, handler_name)
        r = await handler(network, params or {})
        if r.get("error") or not r.get("layer"):
            return StepResult(summary={"note": r.get("answer", "no result")})
        ctx.setdefault("method_findings", []).append((title, r["answer"]))
        return StepResult(
            layers=[r["layer"]],
            summary={"rows": len(r.get("rows", []))},
            finding=(title, r["answer"]),
        )
    return _run


REGISTRY: dict[str, Step] = {s.name: s for s in [
    Step("isochrone_walk",
         "10-minute walking catchment polygons around every location (Mapbox).",
         produces=("isochrones",), run=_run_isochrones),
    Step("competitors_in_radius",
         "Competitor banks/ATMs within 500 m of each location (OSM; own brand excluded).",
         produces=("competitors",), run=_run_competitors),
    Step("population_in_polygon",
         "Residents inside the walking catchments (Kontur population grid).",
         requires=("isochrones",), produces=("population",), run=_run_population),
    Step("huff_model",
         "Huff gravity shares + expected demand per location from competition and population.",
         requires=("competitors", "population"), produces=("scores",), run=_run_huff),
    Step("anomaly_detect",
         "Flag locations whose actual volume beats or misses the Huff expectation.",
         requires=("scores",), produces=("anomalies",), run=_run_anomalies),
    Step("opportunity_hexes",
         "Real population cells scored by uncovered demand — where people live far from any branch.",
         produces=("opportunity_cells",), run=_run_opportunity),
    Step("cannibalisation_pairs",
         "Own-network branch pairs under 800 m apart that likely split the same catchment.",
         produces=("cannibalisation_pairs",), run=_run_cannibalisation),
    Step("district_choropleth",
         "Population choropleth of the 18 HK districts — the demand backdrop for any expansion story.",
         produces=("district_population",), run=_run_district_choropleth),
    Step("whitespace_gaps",
         "Under-served white space: high-demand cells far from every existing site.",
         run=_method_runner("run_whitespace", "White-space gaps")),
    Step("mclp_coverage",
         "Maximal-coverage optimisation: P optimal sites covering the most residents (MCLP/CBC).",
         run=_method_runner("run_optimize_coverage", "Coverage optimisation")),
    Step("best_new_site",
         "Rank candidate sites by marginal net-new demand captured beyond the current network.",
         run=_method_runner("run_best_new_point", "Best new site")),
    Step("lisa_hotspots",
         "LISA / Moran spatial statistics: significant hot and cold clusters of performance.",
         run=_method_runner("run_hotspots", "Performance hot spots")),
    Step("find_similar",
         "Cosine look-alikes of the best performer over spatial-context embeddings.",
         run=_method_runner("run_find_similar", "Look-alike locations")),
    Step("cluster_segments",
         "KMeans segmentation of the network into location types by spatial context.",
         run=_method_runner("run_cluster", "Network segments")),
    Step("drivers_regression",
         "Which contextual factors drive performance; over/under-performers vs context.",
         run=_method_runner("run_drivers", "Performance drivers")),
    Step("accessibility_2sfca",
         "Two-step floating catchment accessibility: which neighbourhoods are access-poor.",
         run=_method_runner("run_accessibility", "Accessibility (2SFCA)")),
]}

# Which step produces each ctx key — used to auto-insert prerequisites.
_PRODUCER: dict[str, str] = {}
for _s in REGISTRY.values():
    for _k in _s.produces:
        _PRODUCER.setdefault(_k, _s.name)


def resolve_plan(step_names: list[str], max_steps: int = 9) -> list[str]:
    """Validate + dependency-resolve an ordered step list.

    Unknown names are dropped; prerequisites are inserted before their
    dependents (recursively); duplicates collapse to first occurrence."""
    out: list[str] = []

    def _add(name: str, depth: int = 0) -> None:
        if name in out or name not in REGISTRY or depth > 4:
            return
        for req in REGISTRY[name].requires:
            producer = _PRODUCER.get(req)
            if producer and producer not in out:
                _add(producer, depth + 1)
        out.append(name)

    for n in step_names:
        _add(n)
    return out[:max_steps]


def default_plan(archetypes: list[str], user_intent: str | None = None) -> list[str]:
    """Deterministic fallback plan — archetype bases plus intent-keyed extras.

    Used when the methodologist LLM is unavailable; also the safety net the
    LLM's output is resolved against."""
    base: list[str] = ["district_choropleth", "isochrone_walk", "competitors_in_radius",
                       "population_in_polygon", "huff_model"]
    extras: list[str] = []
    if "diagnose" in archetypes:
        extras += ["anomaly_detect", "lisa_hotspots"]
    if "expand" in archetypes:
        extras += ["opportunity_hexes", "whitespace_gaps"]
    if "rationalise" in archetypes:
        extras += ["cannibalisation_pairs", "cluster_segments"]

    # Intent keywords refine the tail (mirrors the chat method router).
    intent = (user_intent or "").lower()
    if intent:
        from app.orchestrator.method_tools import classify_method
        m = classify_method(intent)
        if m is not None:
            extra_by_kind = {
                "optimize_coverage": "mclp_coverage",
                "best_new_point": "best_new_site",
                "whitespace": "whitespace_gaps",
                "hotspots": "lisa_hotspots",
                "find_similar": "find_similar",
                "cluster": "cluster_segments",
                "drivers": "drivers_regression",
                "accessibility": "accessibility_2sfca",
            }
            step = extra_by_kind.get(m.kind)
            if step and step not in extras:
                extras.append(step)
    return resolve_plan(base + extras)


def catalog_for_prompt() -> str:
    """The step catalog the methodologist LLM chooses from."""
    lines = []
    for s in REGISTRY.values():
        req = f" (needs: {', '.join(s.requires)})" if s.requires else ""
        lines.append(f"- {s.name}: {s.description}{req}")
    return "\n".join(lines)
