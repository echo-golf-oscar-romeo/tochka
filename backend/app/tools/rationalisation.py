"""Rationalise-archetype tools — cannibalisation analysis.

`cannibalisation_pairs` returns LineString features between every pair of
the user's own branches that are within `max_distance_m` of each other.
That's the "are any of my branches eating each other's lunch?" picture.
Output is GeoJSON-ready so the orchestrator can emit it as a layer.
"""

from __future__ import annotations

import logging
from typing import Any

from app.clients.ddb import get_duckdb, register_locations
from app.config import get_settings
from app.models.network import Location

log = logging.getLogger(__name__)


async def cannibalisation_pairs(locations: list[Location],
                                max_distance_m: int = 800) -> list[dict]:
    """Pairs of own-network branches within `max_distance_m`. Returns
    one GeoJSON LineString feature per pair.
    """
    if get_settings().demo_mode:
        return _canned(locations, max_distance_m)
    if not locations:
        return []
    try:
        conn = get_duckdb()
        register_locations(conn, locations)
        rows = conn.execute(
            """
            SELECT a.id AS a_id, a.name AS a_name, a.lat AS a_lat, a.lng AS a_lng,
                   b.id AS b_id, b.name AS b_name, b.lat AS b_lat, b.lng AS b_lng,
                   ROUND(ST_Distance_Spheroid(
                       ST_Point(a.lat, a.lng),
                       ST_Point(b.lat, b.lng)
                   ), 0) AS distance_m
            FROM _user_locations a
            JOIN _user_locations b ON a.id < b.id
            WHERE ST_Distance_Spheroid(
                ST_Point(a.lat, a.lng),
                ST_Point(b.lat, b.lng)
            ) <= ?
            ORDER BY distance_m
            """,
            [max_distance_m],
        ).fetchall()
        features = []
        for (a_id, a_name, a_lat, a_lng, b_id, b_name, b_lat, b_lng, dist) in rows:
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[a_lng, a_lat], [b_lng, b_lat]],
                },
                "properties": {
                    "a_id": a_id, "a_name": a_name,
                    "b_id": b_id, "b_name": b_name,
                    "distance_m": dist,
                },
            })
        log.info("cannibalisation_pairs: %d pairs within %dm.", len(features), max_distance_m)
        return features
    except Exception as e:
        log.warning("cannibalisation_pairs failed (%s); falling back to canned.", e)
        return _canned(locations, max_distance_m)


def _canned(locations: list[Location], max_distance_m: int) -> list[dict]:
    """Linear distance scan without DuckDB, for demo mode / fallback."""
    import math

    def dist_m(a: Location, b: Location) -> float:
        if a.lat is None or a.lng is None or b.lat is None or b.lng is None:
            return float("inf")
        mlat = math.radians((a.lat + b.lat) / 2)
        dx = (a.lng - b.lng) * 111_320 * math.cos(mlat)
        dy = (a.lat - b.lat) * 110_540
        return math.hypot(dx, dy)

    out: list[dict] = []
    for i, a in enumerate(locations):
        for b in locations[i + 1:]:
            d = dist_m(a, b)
            if d <= max_distance_m:
                out.append({
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[b.lng, b.lat], [a.lng, a.lat]],
                    },
                    "properties": {
                        "a_id": a.id, "a_name": a.name,
                        "b_id": b.id, "b_name": b.name,
                        "distance_m": round(d, 0),
                    },
                })
    out.sort(key=lambda f: f["properties"]["distance_m"])
    return out
