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
from app.orchestrator.prompts import CLARIFYING_QUESTION
from app.tools import (
    competitors,
    demand,
    geocoding,
    modeling,
    reachability,
    viz,
)


@dataclass
class AgentEvent:
    kind: str            # 'thought' | 'tool_call' | 'tool_result' | 'clarify' | 'storymap_ready' | 'done'
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
            summary = (
                f"{len(network.locations)} {poi_type or 'locations'} across "
                f"{len({loc.raw_fields.get('district', '?') for loc in network.locations})} districts."
            )
            # In production this hits Qwen; for the skeleton we hand back a static phrasing.
            question = (
                "These look like bank branches. Optimise for retail customer access, "
                "SME access, or both?"
            )
            yield AgentEvent("clarify", {
                "question": question,
                "options": ["retail", "sme", "both"],
                "prompt_used": CLARIFYING_QUESTION.format(summary=summary),
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

        # Compose the storymap.
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

        yield AgentEvent("storymap_ready", {
            "storymap_id": storymap_id,
            "storymap": storymap.model_dump(),
        })
        yield AgentEvent("done", {"storymap_id": storymap_id})
