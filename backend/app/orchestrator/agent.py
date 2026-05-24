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

from app.config import get_settings
from app.models.analysis import AnalysisRequest, DataLayerPlan
from app.models.network import Network
from app.orchestrator.decision import needs_clarification, pick_methodology
from app.orchestrator.llm import llm_clarify, llm_narrate
from app.tools import (
    competitors,
    demand,
    geocoding,
    modeling,
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
    ) -> AsyncIterator[AgentEvent]:
        # Q1 — what is the network?
        yield AgentEvent("thought", {"text": f"Inspecting {len(network.locations)} locations."})

        # Q1.b — geocode any rows missing coordinates.
        missing = [loc for loc in network.locations if loc.lat is None or loc.lng is None]
        if missing:
            yield AgentEvent("tool_call", {"tool": "als_lookup", "n": len(missing)})
            await geocoding.als_lookup(missing)
            yield AgentEvent("tool_result", {"tool": "als_lookup", "geocoded": len(missing)})

        # Q2 + Q3 — pick demand model and archetypes (rule-based; LLM clarifies only when needed).
        dm, archetypes, poi_type = pick_methodology(network, user_intent, clarification_answer)
        network.inferred_poi_type = poi_type
        yield AgentEvent("thought", {"text": f"POI type ≈ '{poi_type}'."})

        if clarification_answer is None and needs_clarification(poi_type, user_intent):
            yield AgentEvent("tool_call", {"tool": "llm_clarify"})
            generated = await llm_clarify(network, poi_type=poi_type, options=CLARIFY_OPTIONS)
            question = generated or FALLBACK_CLARIFY
            yield AgentEvent("tool_result", {
                "tool": "llm_clarify",
                "source": "qwen" if generated else "fallback",
            })
            yield AgentEvent("clarify", {
                "question": question,
                "options": CLARIFY_OPTIONS,
            })
            return  # client re-calls /analyze with clarification_answer

        yield AgentEvent("thought", {"text": f"Demand model: {dm}. Archetypes: {[a.value for a in archetypes]}."})

        # Q4 — data plan
        plan = [
            DataLayerPlan(layer="population_grid", source="csdi.population_distribution"),
            DataLayerPlan(layer="pedestrian_isochrones", source="csdi.pedestrian_route_search"),
            DataLayerPlan(layer="competitors_banks", source="gmaps.parsed"),
        ]
        request = AnalysisRequest(
            network_id=network.id,
            user_intent=user_intent,
            demand_model=dm,
            archetypes=archetypes,
            data_plan=plan,
        )
        yield AgentEvent("plan", {"plan": [p.model_dump() for p in plan]})

        # ===== QWEN-AGENT-HOOK =====
        # In production, hand `network`, `request`, and the tool registry to
        # qwen_agent.Assistant and let it pick tools turn by turn. For the
        # skeleton, run a fixed sequence so the demo and tests are deterministic.

        yield AgentEvent("tool_call", {"tool": "isochrone_walk", "minutes": 10})
        isos = await reachability.isochrone_walk(network.locations, minutes=10)
        yield AgentEvent("tool_result", {"tool": "isochrone_walk", "n_polygons": len(isos)})

        yield AgentEvent("tool_call", {"tool": "competitors_in_radius", "radius_m": 500})
        comp = await competitors.competitors_in_radius(network.locations, radius_m=500)
        yield AgentEvent("tool_result", {"tool": "competitors_in_radius", "n": len(comp)})

        yield AgentEvent("tool_call", {"tool": "population_in_polygon"})
        pop = await demand.population_in_polygon(isos)
        yield AgentEvent("tool_result", {"tool": "population_in_polygon", "total": pop.get("total_population")})

        yield AgentEvent("tool_call", {"tool": "huff_model"})
        scores = await modeling.huff_model(network.locations, comp, pop)
        yield AgentEvent("tool_result", {"tool": "huff_model", "n_scored": len(scores)})

        yield AgentEvent("tool_call", {"tool": "anomaly_detect"})
        anomalies = await modeling.anomaly_detect(scores)
        yield AgentEvent("tool_result", {"tool": "anomaly_detect", "outliers": len(anomalies)})

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
        for section in storymap.sections:
            yield AgentEvent("narrating", {
                "section_id": section.id,
                "title": section.title,
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
