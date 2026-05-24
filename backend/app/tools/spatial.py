"""Spatial-join utilities backed by DuckDB-spatial + Shapely.

Stubbed — fall back to canned outputs in any mode so the orchestrator can
complete. Real DuckDB implementations slot in here as the tool surface grows.
"""

from __future__ import annotations

import logging
from typing import Any

from app.config import get_settings
from app.mock import canned

log = logging.getLogger(__name__)


async def points_in_polygon(points: list[dict], polygons: list[dict]) -> list[dict]:
    """For each polygon, list the points inside it."""
    if not get_settings().demo_mode:
        log.info("points_in_polygon not yet wired to DuckDB ST_Contains; using canned.")
    return canned.points_in_polygon(points, polygons)


async def nearest_neighbor(points_a: list[dict], points_b: list[dict], k: int = 1) -> list[dict]:
    """For each point in A, k nearest in B with distances (metres)."""
    if not get_settings().demo_mode:
        log.info("nearest_neighbor not yet wired; using canned.")
    return canned.nearest_neighbor(points_a, points_b, k)


async def spatial_sql(query: str) -> list[dict[str, Any]]:
    """Escape hatch — run arbitrary DuckDB-spatial SQL. Canned response only."""
    if not get_settings().demo_mode:
        log.info("spatial_sql not yet wired; returning canned acknowledgement.")
    return canned.spatial_sql(query)
