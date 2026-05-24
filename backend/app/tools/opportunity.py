"""Expand-archetype tool — opportunity scoring on a hex grid.

For each user location we have an isochrone polygon and a catchment-population
estimate from earlier tools. The opportunity score is "where is there
population that's NOT inside any of those isochrones?" — i.e. uncovered demand.

Without a real HK population grid (CSDI FSDT not yet wired) we produce a
synthetic but plausible H3 cell layout: scatter cells across a HK bbox,
weight each by distance to the nearest user location (closer-to-nothing
= higher score). The top N cells are the candidate areas to expand into.
"""

from __future__ import annotations

import logging
import math
from typing import Any

from app.config import get_settings
from app.models.network import Location

log = logging.getLogger(__name__)


# Approximate Hong Kong bbox (West, South, East, North)
_HK_BBOX = (114.10, 22.18, 114.31, 22.42)


def _approx_hex_grid(bbox: tuple[float, float, float, float], step_deg: float = 0.005):
    """Generate cell centers on a regular grid covering the bbox. Not strictly
    H3 but visually close at city scale and avoids the h3 dependency in the
    hot path."""
    w, s, e, n = bbox
    lng = w
    while lng <= e:
        lat = s
        while lat <= n:
            yield (lng, lat)
            lat += step_deg
        lng += step_deg


def _approx_distance_m(lat_a: float, lng_a: float, lat_b: float, lng_b: float) -> float:
    mlat = math.radians((lat_a + lat_b) / 2)
    dx = (lng_a - lng_b) * 111_320 * math.cos(mlat)
    dy = (lat_a - lat_b) * 110_540
    return math.hypot(dx, dy)


async def opportunity_hexes(locations: list[Location], top_n: int = 60) -> list[dict]:
    """Hex-ish polygons across HK scored by distance to the nearest user
    location. Returns the top N cells as small square polygons (degree-aligned)
    with a `score` 0..1 where 1 = most underserved.
    """
    centers = list(_approx_hex_grid(_HK_BBOX, step_deg=0.005))
    user_pts = [(loc.lat, loc.lng) for loc in locations if loc.lat is not None and loc.lng is not None]
    if not user_pts:
        return []

    scored: list[tuple[float, float, float]] = []
    for (lng, lat) in centers:
        nearest = min(_approx_distance_m(lat, lng, ulat, ulng) for (ulat, ulng) in user_pts)
        scored.append((lng, lat, nearest))

    scored.sort(key=lambda r: -r[2])    # furthest from any user location first
    picked = scored[: max(top_n, 1)]
    max_dist = picked[0][2] if picked else 1.0

    features: list[dict] = []
    side = 0.0024    # ~250 m on a side at HK latitude
    for (lng, lat, dist) in picked:
        score = round(dist / max_dist, 3) if max_dist else 0.0
        ring = [
            [lng - side / 2, lat - side / 2],
            [lng + side / 2, lat - side / 2],
            [lng + side / 2, lat + side / 2],
            [lng - side / 2, lat + side / 2],
            [lng - side / 2, lat - side / 2],
        ]
        features.append({
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [ring]},
            "properties": {
                "score": score,
                "distance_to_nearest_branch_m": round(dist, 0),
            },
        })
    log.info("opportunity_hexes: returned %d cells (top %d of %d).", len(features), top_n, len(centers))
    return features


# When called via the LLM, even outside demo mode, this is "real enough" for
# the demo — once CSDI Population Distribution is wired, the same call site
# can swap in real population-weighted scoring without changing the contract.
__all__ = ["opportunity_hexes"]
