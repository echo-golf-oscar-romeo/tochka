"""Modelling tools — Huff, gravity, anomaly detection.

The LLM picks which model to apply. Each function returns a per-location score
with a short rationale string so the storymap can quote it.
"""

from __future__ import annotations

from typing import Any

from app.config import get_settings
from app.mock import canned
from app.models.network import Location


async def huff_model(locations: list[Location], competitors: list[dict],
                     population: dict[str, Any], beta: float = 1.5) -> list[dict]:
    """Huff probabilistic catchment.

    For each user location, estimate expected market share of nearby population
    given competitor attraction and distance decay. Returns one row per user location:
    {"location_id", "expected_demand", "rationale"}.
    """
    if get_settings().demo_mode:
        return canned.huff_scores(locations)
    raise NotImplementedError("Implement Huff model on population grid + competitor attractors.")


async def gravity_score(locations: list[Location], population: dict[str, Any]) -> list[dict]:
    """Simpler gravity score: sum(pop_i / distance_i^β). Lighter than Huff."""
    if get_settings().demo_mode:
        return canned.huff_scores(locations)
    raise NotImplementedError("Implement gravity score.")


async def anomaly_detect(scores: list[dict], k_sigma: float = 1.5) -> list[dict]:
    """Identify locations whose actual performance ≠ expected.

    For the skeleton without 'actual' columns, return the bottom-k and top-k by expected
    demand as a proxy. Output: [{"location_id", "kind": "under"|"over", "delta", "rationale"}].
    """
    if get_settings().demo_mode:
        return canned.anomalies(scores)
    raise NotImplementedError("Implement anomaly detection.")
