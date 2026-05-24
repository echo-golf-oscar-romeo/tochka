"""Modelling tools — Huff, gravity, anomaly detection.

The synthetic implementations in `app/mock/canned` are deterministic and
calibrated to produce a sensible storymap. Real implementations slot in here
once the demand-side data (CSDI Population Distribution) is wired through.
Until then, both demo-mode and non-demo paths use the canned implementations
so the orchestrator can complete end-to-end.
"""

from __future__ import annotations

import logging
from typing import Any

from app.config import get_settings
from app.mock import canned
from app.models.network import Location

log = logging.getLogger(__name__)


async def huff_model(locations: list[Location], competitors: list[dict],
                     population: dict[str, Any], beta: float = 1.5) -> list[dict]:
    """Huff probabilistic catchment per location.

    Output rows: {"location_id", "name", "expected_demand", "score",
                  "capacity"?, "actual_volume"?, "rationale"}.
    """
    if not get_settings().demo_mode:
        log.info("huff_model not yet wired to real population/competitor weights; "
                 "using canned scores.")
    return canned.huff_scores(locations)


async def gravity_score(locations: list[Location], population: dict[str, Any]) -> list[dict]:
    """Simpler gravity score: sum(pop_i / distance_i^β). Falls back to canned."""
    if not get_settings().demo_mode:
        log.info("gravity_score not yet wired; using canned scores.")
    return canned.huff_scores(locations)


async def anomaly_detect(scores: list[dict], k_sigma: float = 1.5) -> list[dict]:
    """Identify under/over-performing locations.

    When the underlying scores carry `actual_volume`, the canned implementation
    runs a real ratio + stdev test. Otherwise it falls back to bottom-3 / top-2
    by predicted demand.
    """
    if not get_settings().demo_mode:
        log.info("anomaly_detect using canned implementation (deterministic; switches "
                 "to real ratio test when actual_volume is present on scores).")
    return canned.anomalies(scores)
