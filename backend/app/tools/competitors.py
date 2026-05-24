"""Competitive-landscape tools — competitor banks, retail anchors.

Backed by DuckDB-spatial running against the pre-fetched OSM POI table
(see clients/ddb.py::ensure_osm_loaded). Falls back to canned data when
DEMO_MODE is on, the OSM file is missing, or the SQL execution fails.
"""

from __future__ import annotations

import logging

from app.clients.ddb import ensure_osm_loaded, get_duckdb, register_locations
from app.config import get_settings
from app.mock import canned
from app.models.network import Location

log = logging.getLogger(__name__)


async def competitors_in_radius(locations: list[Location], radius_m: int = 500,
                                categories: tuple[str, ...] = ("bank",)) -> list[dict]:
    """Competitor POIs within `radius_m` of each user location.

    SQL pattern:
        for each (user × poi) within ST_Distance_Spheroid <= radius_m,
        keep the nearest user per POI (ROW_NUMBER), filter by category.
    """
    s = get_settings()
    if s.demo_mode:
        return canned.competitors_in_radius(locations, radius_m)

    try:
        conn = get_duckdb()
        if not ensure_osm_loaded(conn):
            return canned.competitors_in_radius(locations, radius_m)
        users_table = register_locations(conn, locations)

        cat_placeholders = ", ".join(["?"] * len(categories))
        sql = f"""
        WITH pairs AS (
            SELECT
                o.id, o.name, o.brand, o.lat, o.lng, o.atm, o.district,
                u.id AS user_location_id,
                -- ST_Distance_Spheroid expects ST_Point(latitude, longitude)
                -- in this DuckDB spatial version, opposite of the GeoJSON convention.
                ST_Distance_Spheroid(
                    ST_Point(o.lat, o.lng),
                    ST_Point(u.lat, u.lng)
                ) AS distance_m,
                ROW_NUMBER() OVER (
                    PARTITION BY o.id
                    ORDER BY ST_Distance_Spheroid(
                        ST_Point(o.lat, o.lng),
                        ST_Point(u.lat, u.lng)
                    )
                ) AS rn
            FROM osm_pois o
            CROSS JOIN {users_table} u
            WHERE o.type IN ({cat_placeholders})
        )
        SELECT id, name, brand, lat, lng, atm, district,
               user_location_id AS nearest_user_location_id,
               ROUND(distance_m, 1) AS distance_m
        FROM pairs
        WHERE rn = 1 AND distance_m <= ?
        ORDER BY distance_m
        """
        params: list = list(categories) + [radius_m]
        rows = conn.execute(sql, params).fetchall()
        cols = [d[0] for d in conn.description]
        out = [dict(zip(cols, row, strict=False)) for row in rows]
        log.info("competitors_in_radius (DuckDB): %d POIs within %dm.", len(out), radius_m)
        return out
    except Exception as e:
        log.warning("competitors_in_radius DuckDB path failed (%s); using canned.", e)
        return canned.competitors_in_radius(locations, radius_m)


async def gmaps_poi_scrape(bbox: tuple[float, float, float, float],
                           category: str = "bank") -> list[dict]:
    """On-demand Google Maps POI extraction. Not wired; canned fallback."""
    if not get_settings().demo_mode:
        log.info("gmaps_poi_scrape not yet wired (SiteSense parser); using canned POIs.")
    return canned.gmaps_pois(bbox, category)
