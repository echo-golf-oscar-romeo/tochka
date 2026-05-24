"""Demand-surface tools — population, demographics, spending proxies."""

from __future__ import annotations

from typing import Any

from app.config import get_settings
from app.mock import canned


async def population_in_polygon(polygons: list[dict]) -> dict[str, Any]:
    """Sum population from CSDI Population Distribution FSDT inside each polygon.

    Returns: {"per_polygon": [{polygon_id, total, age_brackets?}, ...], "total_population": int}
    """
    if get_settings().demo_mode:
        return canned.population_in_polygon(polygons)
    raise NotImplementedError("Wire CSDI Population Distribution FSDT.")


async def demographic_breakdown(polygons: list[dict],
                                brackets: tuple[str, ...] = ("0_17", "18_44", "45_64", "65_plus")) -> dict[str, Any]:
    """Age/income brackets per polygon. Same FSDT, richer query."""
    if get_settings().demo_mode:
        return canned.demographic_breakdown(polygons, brackets)
    raise NotImplementedError("Wire demographic breakdown.")
