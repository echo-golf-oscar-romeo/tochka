"""Aggregation to hex grids — H3.

Not yet wired against real population data; falls back to canned synthetic
cells when called in non-demo mode so the pipeline can complete.
"""

from __future__ import annotations

import logging
from typing import Any

from app.config import get_settings
from app.mock import canned

log = logging.getLogger(__name__)


async def h3_aggregate(points: list[dict], resolution: int = 9,
                       weight_field: str | None = None) -> dict[str, Any]:
    """Bin points to H3 cells; sum a weight or count.

    Returns: {"cells": [{"h3": "...", "value": n}, ...], "resolution": resolution}
    """
    if not get_settings().demo_mode:
        log.info("h3_aggregate not yet wired; using canned cells.")
    return canned.h3_aggregate(points, resolution, weight_field)


async def hex_bin(bbox: tuple[float, float, float, float], resolution: int = 9) -> list[dict]:
    """Enumerate H3 cells covering a bbox. Canned skeleton."""
    if not get_settings().demo_mode:
        log.info("hex_bin not yet wired; using canned cells.")
    return canned.hex_bin(bbox, resolution)
