"""Spatial-join utilities backed by DuckDB-spatial.

Real SQL implementations of the three escape-hatch operations the LLM may
compose in ad-hoc plans. Each falls back to canned outputs on failure so a
broken query never crashes the orchestrator stream.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.clients.ddb import get_duckdb, register_kv_table
from app.config import get_settings
from app.mock import canned

log = logging.getLogger(__name__)


async def points_in_polygon(points: list[dict], polygons: list[dict]) -> list[dict]:
    """For each polygon, list IDs of the points inside it.

    Inputs:
      points   — list of dicts with at least `id`, `lat`, `lng`.
      polygons — list of GeoJSON Feature dicts with Polygon/MultiPolygon
                 geometry. The polygon id is taken from
                 `properties.location_id` falling back to `properties.id`.
    """
    if get_settings().demo_mode:
        return canned.points_in_polygon(points, polygons)
    if not points or not polygons:
        return []
    try:
        conn = get_duckdb()
        # Points: temp table.
        register_kv_table(
            conn, "_pip_points",
            rows=[{"id": p.get("id"), "lat": float(p.get("lat", 0)), "lng": float(p.get("lng", 0))}
                  for p in points if p.get("lat") is not None and p.get("lng") is not None],
            columns=[("id", "VARCHAR"), ("lat", "DOUBLE"), ("lng", "DOUBLE")],
        )
        # Polygons: store the GeoJSON geometry as JSON text; parse with ST_GeomFromGeoJSON.
        poly_rows = []
        for p in polygons:
            props = p.get("properties") or {}
            pid = props.get("location_id") or props.get("id") or p.get("id")
            geom = p.get("geometry") or {}
            if not pid or not geom:
                continue
            poly_rows.append({"id": str(pid), "geojson": json.dumps(geom)})
        register_kv_table(
            conn, "_pip_polygons",
            rows=poly_rows,
            columns=[("id", "VARCHAR"), ("geojson", "VARCHAR")],
        )
        rows = conn.execute(
            """
            SELECT poly.id AS polygon_id,
                   LIST(pt.id) AS point_ids
            FROM _pip_polygons poly
            JOIN _pip_points pt
              ON ST_Contains(ST_GeomFromGeoJSON(poly.geojson), ST_Point(pt.lng, pt.lat))
            GROUP BY poly.id
            """
        ).fetchall()
        return [{"polygon_id": r[0], "point_ids": list(r[1] or [])} for r in rows]
    except Exception as e:
        log.warning("points_in_polygon DuckDB path failed (%s); using canned.", e)
        return canned.points_in_polygon(points, polygons)


async def nearest_neighbor(points_a: list[dict], points_b: list[dict], k: int = 1) -> list[dict]:
    """For each point in A, return k nearest in B with distances (metres).

    Inputs: lists of dicts with `id`, `lat`, `lng`. Output rows:
        {id, neighbors: [{id, distance_m}, ...]}.
    """
    if get_settings().demo_mode:
        return canned.nearest_neighbor(points_a, points_b, k)
    if not points_a or not points_b:
        return []
    try:
        conn = get_duckdb()
        register_kv_table(
            conn, "_nn_a",
            rows=[{"id": p["id"], "lat": float(p["lat"]), "lng": float(p["lng"])}
                  for p in points_a if p.get("lat") is not None and p.get("lng") is not None],
            columns=[("id", "VARCHAR"), ("lat", "DOUBLE"), ("lng", "DOUBLE")],
        )
        register_kv_table(
            conn, "_nn_b",
            rows=[{"id": p["id"], "lat": float(p["lat"]), "lng": float(p["lng"])}
                  for p in points_b if p.get("lat") is not None and p.get("lng") is not None],
            columns=[("id", "VARCHAR"), ("lat", "DOUBLE"), ("lng", "DOUBLE")],
        )
        rows = conn.execute(
            """
            WITH pairs AS (
                -- ST_Distance_Spheroid takes ST_Point(lat, lng) in this version.
                SELECT a.id AS a_id, b.id AS b_id,
                       ST_Distance_Spheroid(
                           ST_Point(a.lat, a.lng),
                           ST_Point(b.lat, b.lng)
                       ) AS distance_m,
                       ROW_NUMBER() OVER (
                           PARTITION BY a.id
                           ORDER BY ST_Distance_Spheroid(
                               ST_Point(a.lat, a.lng),
                               ST_Point(b.lat, b.lng)
                           )
                       ) AS rn
                FROM _nn_a a CROSS JOIN _nn_b b
            )
            SELECT a_id, LIST({'id': b_id, 'distance_m': ROUND(distance_m, 1)} ORDER BY distance_m) AS neighbors
            FROM pairs
            WHERE rn <= ?
            GROUP BY a_id
            """,
            [k],
        ).fetchall()
        return [{"id": r[0], "neighbors": list(r[1] or [])} for r in rows]
    except Exception as e:
        log.warning("nearest_neighbor DuckDB path failed (%s); using canned.", e)
        return canned.nearest_neighbor(points_a, points_b, k)


async def spatial_sql(query: str) -> list[dict[str, Any]]:
    """Escape hatch — run arbitrary DuckDB-spatial SQL.

    Read-only by convention; we don't enforce it. The LLM may call this when
    it wants to compose a join we haven't pre-packaged. Returns row dicts.
    """
    if get_settings().demo_mode:
        return canned.spatial_sql(query)
    try:
        conn = get_duckdb()
        rows = conn.execute(query).fetchall()
        cols = [d[0] for d in conn.description]
        return [dict(zip(cols, row, strict=False)) for row in rows]
    except Exception as e:
        log.warning("spatial_sql failed (%s); returning canned acknowledgement.", e)
        return canned.spatial_sql(query)
