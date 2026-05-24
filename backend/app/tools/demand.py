"""Demand-surface tools — population, demographics, spending proxies.

Neither endpoint is wired against CSDI Population Distribution FSDT yet. Until
that's in place the tools always return canned data and log a warning when in
non-demo mode, so the orchestrator can still complete and produce a storymap
with synthetic numbers. Crashing the SSE stream because one tool isn't wired
is worse than the alternative.
"""

from __future__ import annotations

import logging
from typing import Any

from app.config import get_settings
from app.mock import canned

log = logging.getLogger(__name__)


async def population_in_polygon(polygons: list[dict]) -> dict[str, Any]:
    """Sum population inside each polygon.

    Returns: {"per_polygon": [{polygon_id, total, age_brackets?}, ...],
              "total_population": int}
    """
    if not get_settings().demo_mode:
        log.info("population_in_polygon not yet wired to CSDI FSDT; using canned figures.")
    return canned.population_in_polygon(polygons)


async def demographic_breakdown(polygons: list[dict],
                                brackets: tuple[str, ...] = ("0_17", "18_44", "45_64", "65_plus")) -> dict[str, Any]:
    """Age brackets per polygon."""
    if not get_settings().demo_mode:
        log.info("demographic_breakdown not yet wired to CSDI FSDT; using canned figures.")
    return canned.demographic_breakdown(polygons, brackets)
