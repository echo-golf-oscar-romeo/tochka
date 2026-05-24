"""Spatial-join utilities backed by DuckDB-spatial + Shapely."""

from __future__ import annotations

from typing import Any

from app.config import get_settings
from app.mock import canned


async def points_in_polygon(points: list[dict], polygons: list[dict]) -> list[dict]:
    """For each polygon, list the points inside it.

    Returns: [{polygon_id, point_ids: [...]}, ...]
    """
    if get_settings().demo_mode:
        return canned.points_in_polygon(points, polygons)
    raise NotImplementedError("Wire DuckDB ST_Contains.")


async def nearest_neighbor(points_a: list[dict], points_b: list[dict], k: int = 1) -> list[dict]:
    """For each point in A, k nearest in B with distances (metres)."""
    if get_settings().demo_mode:
        return canned.nearest_neighbor(points_a, points_b, k)
    raise NotImplementedError("Wire DuckDB ST_Distance_Spheroid.")


async def spatial_sql(query: str) -> list[dict[str, Any]]:
    """Escape hatch — run arbitrary DuckDB-spatial SQL. The LLM may compose ad-hoc joins."""
    if get_settings().demo_mode:
        return canned.spatial_sql(query)
    raise NotImplementedError("Wire DuckDB connection.")
