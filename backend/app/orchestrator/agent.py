"""Orchestrator — the four-question loop, emits SSE-shaped events.

This is the *skeleton*. The real Qwen-Agent tool-calling loop slots in where
indicated (search for QWEN-AGENT-HOOK below). For demo mode and for the
happy-path test the orchestrator runs a pre-determined sequence using the
plain tool functions, which themselves return canned data when DEMO_MODE=true.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from app.clients.llm import get_llm
from app.config import get_settings
from app.models.analysis import AnalysisRequest, Archetype, DataLayerPlan
from app.models.network import Network
from app.orchestrator.decision import needs_clarification, pick_methodology
from app.orchestrator.llm import llm_clarify, llm_narrate, llm_plan
from app.tools import (
    competitors,
    demand,
    geocoding,
    modeling,
    opportunity,
    rationalisation,
    reachability,
    viz,
)

# Hard-coded fallback question — used when DASHSCOPE_API_KEY is missing or the
# LLM call fails. Keeps the demo loop runnable offline.
FALLBACK_CLARIFY = (
    "These look like bank branches. Optimise for retail customer access, "
    "SME access, or both?"
)
CLARIFY_OPTIONS = ["retail", "sme", "both"]


def _fallback_plan_narrative(archetypes: list[str], n_locations: int) -> str:
    bits: list[str] = []
    if "diagnose" in archetypes:
        bits.append("flag under- and over-performing branches against a Huff baseline")
    if "expand" in archetypes:
        bits.append("score every 250 m cell in HK for uncovered demand and surface the top candidates")
    if "rationalise" in archetypes:
        bits.append("draw cannibalisation lines between own branches under 800 m apart")
    body = "; ".join(bits) if bits else "review the network and produce a storymap"
    return f"I'll process your {n_locations} locations and {body}."


@dataclass
class AgentEvent:
    kind: str            # 'thought' | 'plan' | 'tool_call' | 'tool_result' | 'clarify' | 'narrating' | 'storymap_ready' | 'done'
    payload: dict[str, Any]


class Orchestrator:
    def __init__(self) -> None:
        self.settings = get_settings()

    async def run(
        self,
        network: Network,
        user_intent: str | None = None,
        clarification_answer: str | None = None,
        archetypes: list[Archetype] | None = None,
    ) -> AsyncIterator[AgentEvent]:
        # Q1 — what is the network?
        yield AgentEvent("thought", {"text": f"Inspecting {len(network.locations)} locations."})

        # Q1.b — geocode any rows missing coordinates.
        missing = [loc for loc in network.locations if loc.lat is None or loc.lng is None]
        if missing:
            yield AgentEvent("tool_call", {"tool": "als_lookup", "n": len(missing)})
            await geocoding.als_lookup(missing)
            geocoded_ok = sum(1 for loc in missing if loc.geocoded)
            yield AgentEvent("tool_result", {
                "tool": "als_lookup",
                "geocoded": geocoded_ok,
                "of": len(missing),
            })

        # Q2 + Q3 — pick demand model and archetypes (rule-based; LLM clarifies only when needed).
        dm, default_archetypes, poi_type = pick_methodology(network, user_intent, clarification_answer)
        network.inferred_poi_type = poi_type
        yield AgentEvent("thought", {"text": f"POI type ≈ '{poi_type}'."})

        # If the user picked archetypes explicitly, honour them and skip the
        # clarify-on-banks heuristic — they already told us what they want.
        if archetypes:
            chosen_archetypes = list(archetypes)
            yield AgentEvent("thought", {
                "text": f"User-selected archetypes: {[a.value for a in chosen_archetypes]}.",
            })
        else:
            chosen_archetypes = default_archetypes

        if not archetypes and clarification_answer is None and needs_clarification(poi_type, user_intent):
            provider = get_llm().provider
            yield AgentEvent("tool_call", {"tool": "llm_clarify", "provider": provider})
            generated = await llm_clarify(network, poi_type=poi_type, options=CLARIFY_OPTIONS)
            question = generated or FALLBACK_CLARIFY
            yield AgentEvent("tool_result", {
                "tool": "llm_clarify",
                "source": provider if generated else "fallback",
            })
            yield AgentEvent("clarify", {
                "question": question,
                "options": CLARIFY_OPTIONS,
            })
            return  # client re-calls /analyze with clarification_answer

        yield AgentEvent("thought", {"text": f"Demand model: {dm}. Archetypes: {[a.value for a in chosen_archetypes]}."})

        # Q4 — data plan
        plan = [
            DataLayerPlan(layer="population_grid", source="csdi.population_distribution"),
            DataLayerPlan(layer="pedestrian_isochrones", source="mapbox.isochrone"),
            DataLayerPlan(layer="competitors_banks", source="osm.parsed"),
        ]
        request = AnalysisRequest(
            network_id=network.id,
            user_intent=user_intent,
            demand_model=dm,
            archetypes=chosen_archetypes,
            data_plan=plan,
        )
        yield AgentEvent("plan", {"plan": [p.model_dump() for p in plan]})

        # LLM-narrated plan — what's about to happen, in one sentence,
        # specific to the chosen archetype(s). Falls back to a hand-rolled
        # string when the LLM isn't available so the demo still reads as
        # agentic on stage.
        archetype_values = [a.value for a in chosen_archetypes]
        archetype_tool_map = {
            "diagnose":    ["isochrone_walk", "competitors_in_radius", "population_in_polygon",
                            "huff_model", "anomaly_detect"],
            "expand":      ["isochrone_walk", "competitors_in_radius", "population_in_polygon",
                            "huff_model", "opportunity_hexes"],
            "rationalise": ["isochrone_walk", "competitors_in_radius", "huff_model",
                            "cannibalisation_pairs"],
        }
        tool_names = sorted({t for a in archetype_values for t in archetype_tool_map.get(a, [])})
        narrated_plan = await llm_plan(network, archetypes=archetype_values, tool_names=tool_names)
        if not narrated_plan:
            narrated_plan = _fallback_plan_narrative(archetype_values, len(network.locations))
        yield AgentEvent("plan_narrative", {
            "text": narrated_plan,
            "archetypes": archetype_values,
            "tool_sequence": tool_names,
        })

        # ===== QWEN-AGENT-HOOK =====
        # In production, hand `network`, `request`, and the tool registry to
        # qwen_agent.Assistant and let it pick tools turn by turn. For the
        # skeleton, run a fixed sequence so the demo and tests are deterministic.

        # Emit the user-network layer immediately so the workspace can render
        # uploaded points before any analysis tool runs.
        yield AgentEvent("layer_added", {
            "layer": viz.build_user_network_layer(network).model_dump(),
        })

        yield AgentEvent("tool_call", {"tool": "isochrone_walk", "minutes": 10})
        isos = await reachability.isochrone_walk(network.locations, minutes=10)
        yield AgentEvent("tool_result", {"tool": "isochrone_walk", "n_polygons": len(isos)})
        yield AgentEvent("layer_added", {
            "layer": viz.build_isochrones_layer(isos).model_dump(),
        })

        yield AgentEvent("tool_call", {"tool": "competitors_in_radius", "radius_m": 500})
        comp = await competitors.competitors_in_radius(network.locations, radius_m=500)
        yield AgentEvent("tool_result", {"tool": "competitors_in_radius", "n": len(comp)})
        yield AgentEvent("layer_added", {
            "layer": viz.build_competitors_layer(comp).model_dump(),
        })

        yield AgentEvent("tool_call", {"tool": "population_in_polygon"})
        pop = await demand.population_in_polygon(isos)
        yield AgentEvent("tool_result", {"tool": "population_in_polygon", "total": pop.get("total_population")})

        yield AgentEvent("tool_call", {"tool": "huff_model"})
        scores = await modeling.huff_model(network.locations, comp, pop)
        yield AgentEvent("tool_result", {"tool": "huff_model", "n_scored": len(scores)})

        # ---- Archetype-specific branches ----------------------------------
        # Each archetype gets its own *additional* tool + layer on top of the
        # shared base (network, isochrones, competitors, population, huff).
        archetype_ids = {a.value for a in chosen_archetypes}
        anomalies: list[dict] = []

        # Diagnose -> anomaly detection on Huff baseline.
        if "diagnose" in archetype_ids:
            yield AgentEvent("tool_call", {"tool": "anomaly_detect"})
            anomalies = await modeling.anomaly_detect(scores)
            yield AgentEvent("tool_result", {"tool": "anomaly_detect", "outliers": len(anomalies)})
            yield AgentEvent("layer_added", {
                "layer": viz.build_anomalies_layer(anomalies, network).model_dump(),
            })

        # Expand -> opportunity hex grid (uncovered demand).
        if "expand" in archetype_ids:
            yield AgentEvent("tool_call", {"tool": "opportunity_hexes", "top_n": 60})
            opp_cells = await opportunity.opportunity_hexes(network.locations, top_n=60)
            yield AgentEvent("tool_result", {"tool": "opportunity_hexes", "n_cells": len(opp_cells)})
            yield AgentEvent("layer_added", {
                "layer": viz.build_opportunity_layer(opp_cells).model_dump(),
            })

        # Rationalise -> cannibalisation lines between own-network branches.
        if "rationalise" in archetype_ids:
            yield AgentEvent("tool_call", {"tool": "cannibalisation_pairs", "max_distance_m": 800})
            pairs = await rationalisation.cannibalisation_pairs(network.locations, max_distance_m=800)
            yield AgentEvent("tool_result", {"tool": "cannibalisation_pairs", "n_pairs": len(pairs)})
            yield AgentEvent("layer_added", {
                "layer": viz.build_cannibalisation_layer(pairs).model_dump(),
            })

        # If anomalies weren't computed for a non-diagnose flow, run a quick
        # one anyway so the storymap section that talks about anomalies has
        # real numbers — but skip emitting it as a layer.
        if not anomalies:
            anomalies = await modeling.anomaly_detect(scores)

        # Compose the storymap scaffold (layers + section structure + fallback prose).
        yield AgentEvent("tool_call", {"tool": "make_storymap_section"})
        storymap = await viz.compose_storymap(
            network=network,
            request=request,
            isochrones=isos,
            competitors=comp,
            population=pop,
            scores=scores,
            anomalies=anomalies,
        )
        storymap_id = str(uuid.uuid4())
        storymap.id = storymap_id

        # Rewrite each section's description via Qwen. Sequential — produces a
        # per-section progress beat in the agent log, which makes the demo read
        # as "the agent is writing this for you, live". Falls back to the
        # composed f-string when the LLM is unavailable.
        provider = get_llm().provider
        for section in storymap.sections:
            yield AgentEvent("narrating", {
                "section_id": section.id,
                "title": section.title,
                "provider": provider,
            })
            rewritten = await llm_narrate(
                section_id=section.id,
                section_title=section.title,
                fallback=section.description,
                kpis=section.kpis,
                callouts=section.callouts,
            )
            if rewritten:
                section.description = rewritten

        yield AgentEvent("storymap_ready", {
            "storymap_id": storymap_id,
            "storymap": storymap.model_dump(),
        })
        yield AgentEvent("done", {"storymap_id": storymap_id})
