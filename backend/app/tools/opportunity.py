"""Expand-archetype tool — opportunity scoring on the real population grid.

Opportunity = residents the current network doesn't reach. For every Kontur
H3 r8 cell (real population, ~0.74 km² hexes) we compute

    score = norm(population) × norm(min(distance to nearest branch, cap))

so a cell scores high only when it BOTH holds people AND sits far from every
existing location. Distance is capped (default 3 km) so outlying islands
don't dominate, and empty cells are skipped entirely — the old synthetic
version scored bare distance on a bbox grid and kept "finding" opportunity
in the harbour.

Returns the top-N cells as true H3 hexagon polygons with population,
distance, and a 0..1 score.
"""

from __future__ import annotations

import logging
import math

import h3

from app.clients.ddb import ensure_kontur_loaded, get_duckdb
from app.models.network import Location

log = logging.getLogger(__name__)

_DIST_CAP_M = 3_000.0
_MIN_POP = 200.0          # ignore near-empty cells


def _approx_distance_m(lat_a: float, lng_a: float, lat_b: float, lng_b: float) -> float:
    mlat = math.radians((lat_a + lat_b) / 2)
    dx = (lng_a - lng_b) * 111_320 * math.cos(mlat)
    dy = (lat_a - lat_b) * 110_540
    return math.hypot(dx, dy)


async def opportunity_hexes(locations: list[Location], top_n: int = 60) -> list[dict]:
    """Top-N uncovered-demand cells as H3 hexagon GeoJSON features.

    Properties: score (0..1), population, distance_to_nearest_branch_m, h3.
    """
    user_pts = [(loc.lat, loc.lng) for loc in locations
                if loc.lat is not None and loc.lng is not None]
    if not user_pts:
        return []

    conn = get_duckdb()
    ensure_kontur_loaded(conn)
    try:
        rows = conn.execute(
            "SELECT h3, lat, lng, population FROM kontur_pop_hex WHERE population >= ?",
            [_MIN_POP],
        ).fetchall()
    except Exception as e:  # noqa: BLE001
        log.warning("opportunity_hexes: kontur unavailable (%s) — returning nothing.", e)
        return []
    if not rows:
        return []

    max_pop = max(float(r[3]) for r in rows)
    scored: list[tuple[str, float, float, float, float, float]] = []
    for cell, lat, lng, pop in rows:
        nearest = min(_approx_distance_m(lat, lng, ulat, ulng) for (ulat, ulng) in user_pts)
        d = min(nearest, _DIST_CAP_M)
        score = (float(pop) / max_pop) * (d / _DIST_CAP_M)
        if score <= 0:
            continue
        scored.append((cell, lat, lng, float(pop), nearest, score))

    scored.sort(key=lambda r: -r[5])
    picked = scored[: max(top_n, 1)]
    if not picked:
        return []
    top_score = picked[0][5]

    features: list[dict] = []
    for cell, lat, lng, pop, nearest, score in picked:
        try:
            boundary = h3.cell_to_boundary(cell)          # [(lat, lng), ...]
            ring = [[bl, bb] for (bb, bl) in boundary]    # → [lng, lat]
            if ring and ring[0] != ring[-1]:
                ring.append(ring[0])
        except Exception:  # noqa: BLE001 — bad cell id → skip
            continue
        features.append({
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [ring]},
            "properties": {
                "h3": cell,
                "score": round(score / top_score, 3),
                "population": int(pop),
                "distance_to_nearest_branch_m": round(nearest, 0),
            },
        })
    log.info("opportunity_hexes: %d real population cells (top %d).", len(features), top_n)
    return features


__all__ = ["opportunity_hexes"]
