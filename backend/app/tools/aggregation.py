"""Aggregation to hex grids — H3."""

from __future__ import annotations

from typing import Any

from app.config import get_settings
from app.mock import canned


async def h3_aggregate(points: list[dict], resolution: int = 9,
                       weight_field: str | None = None) -> dict[str, Any]:
    """Bin points to H3 cells at given resolution; sum a weight or count.

    Returns: {"cells": [{"h3": "...", "value": n}, ...], "resolution": resolution}
    """
    if get_settings().demo_mode:
        return canned.h3_aggregate(points, resolution, weight_field)
    raise NotImplementedError("Wire h3 binning.")


async def hex_bin(bbox: tuple[float, float, float, float], resolution: int = 9) -> list[dict]:
    """Enumerate H3 cells covering a bbox. Used for gap-analysis canvases."""
    if get_settings().demo_mode:
        return canned.hex_bin(bbox, resolution)
    raise NotImplementedError("Wire hex_bin.")
