"""Analysis-shaped models — what the orchestrator decides, what tools consume."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class DemandModel(str, Enum):
    PEOPLE_DRIVEN = "people_driven"        # banking, retail, F&B
    VISIT_DRIVEN = "visit_driven"          # clinics, day care
    FLOW_DRIVEN = "flow_driven"            # ATMs, vending
    CATCHMENT_FIXED = "catchment_fixed"    # schools, community centres


class Archetype(str, Enum):
    DIAGNOSE = "diagnose"          # how is my current network performing?
    EXPAND = "expand"              # where should I open next?
    RATIONALISE = "rationalise"    # which to close / merge / resize?


class DataLayerPlan(BaseModel):
    layer: str                     # e.g. "population_grid", "competitors_banks"
    source: str                    # e.g. "csdi.population_distribution", "gmaps.parsed"
    status: str = "requested"      # requested | cached | unavailable
    note: str | None = None


class AnalysisRequest(BaseModel):
    """Fixed by the orchestrator after answering its four questions."""

    network_id: str
    user_intent: str | None = None
    demand_model: DemandModel
    archetypes: list[Archetype]
    data_plan: list[DataLayerPlan]
    pilot_bbox: tuple[float, float, float, float] | None = None  # min_lng, min_lat, max_lng, max_lat
