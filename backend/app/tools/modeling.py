"""Modelling tools — Huff, gravity, anomaly detection — backed by DuckDB SQL.

`huff_model` joins per-location catchment population (from
`population_in_polygon`) against competitor counts inside the catchment
(from `competitors_in_radius`) and computes each location's expected
share + demand via a simple Huff formulation:

    user_attractiveness     = (capacity or 1.0)
    competitor_attractiveness = competitors_in_catchment + 1
    expected_share           = user / (user + competitor)
    expected_demand          = catchment_pop * expected_share * CONVERSION_RATE

`anomaly_detect` runs a real actual-vs-expected ratio test using AVG and
STDDEV window aggregates when at least half the rows have actual_volume;
otherwise falls back to a rank-based bottom-3 / top-2 proxy.

Both fall back to canned outputs on any failure so the orchestrator stream
never crashes on a SQL hiccup.
"""

from __future__ import annotations

import logging
from typing import Any

from app.clients.ddb import get_duckdb, register_kv_table, register_locations
from app.config import get_settings
from app.mock import canned
from app.models.network import Location

log = logging.getLogger(__name__)

# Conversion rate — what fraction of catchment population is realistically
# served by *one* outlet per year. 10% is conservative for HK banking; the
# value mostly affects absolute scale, not anomaly relative ordering.
CONVERSION_RATE = 0.10


async def huff_model(locations: list[Location], competitors: list[dict],
                     population: dict[str, Any], beta: float = 1.5) -> list[dict]:
    """Huff probabilistic catchment per location, computed via DuckDB SQL.

    Returns list of {location_id, name, expected_demand, score, capacity?,
    actual_volume?, comp_count, catchment_pop, rationale}.
    """
    if get_settings().demo_mode:
        return canned.huff_scores(locations)
    try:
        conn = get_duckdb()
        # Locations table.
        register_locations(conn, locations)
        # Per-location catchment population (from population_in_polygon).
        register_kv_table(
            conn, "_pop_by_location",
            rows=[{"location_id": r.get("polygon_id"), "total_pop": int(r.get("total", 0))}
                  for r in (population or {}).get("per_polygon", [])],
            columns=[("location_id", "VARCHAR"), ("total_pop", "BIGINT")],
        )
        # Competitor counts within each user's catchment.
        register_kv_table(
            conn, "_competitors",
            rows=[{"user_location_id": c.get("nearest_user_location_id")} for c in (competitors or [])],
            columns=[("user_location_id", "VARCHAR")],
        )

        rows = conn.execute(
            """
            WITH comp_counts AS (
                SELECT user_location_id, COUNT(*) AS comp_count
                FROM _competitors
                WHERE user_location_id IS NOT NULL
                GROUP BY user_location_id
            ),
            joined AS (
                SELECT
                    u.id          AS location_id,
                    u.name        AS name,
                    u.capacity    AS capacity,
                    u.actual_volume AS actual_volume,
                    COALESCE(p.total_pop, 0)            AS catchment_pop,
                    COALESCE(cc.comp_count, 0)          AS comp_count,
                    COALESCE(u.capacity, 1.0)           AS user_attr,
                    (COALESCE(cc.comp_count, 0) + 1.0)  AS comp_attr
                FROM _user_locations u
                LEFT JOIN _pop_by_location p ON p.location_id = u.id
                LEFT JOIN comp_counts cc     ON cc.user_location_id = u.id
            )
            SELECT
                location_id, name, capacity, actual_volume,
                catchment_pop, comp_count,
                user_attr / (user_attr + comp_attr) AS share,
                CAST(catchment_pop * (user_attr / (user_attr + comp_attr)) * ? AS BIGINT)
                  AS expected_demand
            FROM joined
            ORDER BY expected_demand DESC
            """,
            [CONVERSION_RATE],
        ).fetchall()

        out = []
        for (loc_id, name, capacity, actual, pop, ccount, share, expected) in rows:
            out.append({
                "location_id": loc_id,
                "name": name,
                "capacity": capacity,
                "actual_volume": actual,
                "catchment_pop": int(pop or 0),
                "comp_count": int(ccount or 0),
                "share": round(float(share or 0), 3),
                "score": round(float(share or 0), 3),
                "expected_demand": int(expected or 0),
                "rationale": (
                    f"{name}: catchment {int(pop or 0):,} residents, "
                    f"{int(ccount or 0)} competitor branch(es) nearby — "
                    f"Huff share {float(share or 0):.0%}."
                ),
            })
        log.info("huff_model (DuckDB): %d locations scored.", len(out))
        return out
    except Exception as e:
        log.warning("huff_model DuckDB path failed (%s); using canned scores.", e)
        return canned.huff_scores(locations)


async def gravity_score(locations: list[Location], population: dict[str, Any]) -> list[dict]:
    """Gravity score — lighter alternative to Huff. Canned for now."""
    if not get_settings().demo_mode:
        log.info("gravity_score not yet wired with full attractor weights; using canned.")
    return canned.huff_scores(locations)


async def anomaly_detect(scores: list[dict], k_sigma: float = 1.5) -> list[dict]:
    """Identify under/over-performing locations via SQL.

    When at least half the scores have actual_volume + expected_demand > 0,
    runs a real actual/expected ratio test against the dataset mean ± k_sigma σ
    (with a 10% floor). Otherwise falls back to rank-based bottom-3 / top-2
    on score for parity with the original skeleton.
    """
    if get_settings().demo_mode:
        return canned.anomalies(scores)
    if not scores:
        return []

    actual_count = sum(
        1 for s in scores
        if s.get("actual_volume") is not None and s.get("expected_demand", 0) > 0
    )
    if actual_count < max(2, len(scores) // 2):
        log.info("anomaly_detect: only %d/%d scores have actuals; "
                 "using rank-based fallback.", actual_count, len(scores))
        return canned.anomalies(scores)

    try:
        conn = get_duckdb()
        register_kv_table(
            conn, "_scores",
            rows=[{
                "location_id": s.get("location_id"),
                "name": s.get("name"),
                "expected_demand": s.get("expected_demand"),
                "actual_volume": s.get("actual_volume"),
                "capacity": s.get("capacity"),
            } for s in scores],
            columns=[
                ("location_id", "VARCHAR"),
                ("name", "VARCHAR"),
                ("expected_demand", "BIGINT"),
                ("actual_volume", "DOUBLE"),
                ("capacity", "DOUBLE"),
            ],
        )
        rows = conn.execute(
            """
            WITH valid AS (
                SELECT *,
                       CAST(actual_volume AS DOUBLE) / NULLIF(expected_demand, 0) AS ratio
                FROM _scores
                WHERE actual_volume IS NOT NULL AND expected_demand > 0
            ),
            stats AS (
                SELECT AVG(ratio) AS mean_r,
                       COALESCE(STDDEV_SAMP(ratio), 0) AS sd_r
                FROM valid
            )
            SELECT v.location_id, v.name, v.expected_demand, v.actual_volume,
                   v.capacity, v.ratio, v.ratio - s.mean_r AS delta,
                   GREATEST(0.10, ? * s.sd_r) AS threshold
            FROM valid v CROSS JOIN stats s
            """,
            [k_sigma],
        ).fetchall()

        out: list[dict] = []
        for (loc_id, name, expected, actual, capacity, ratio, delta, threshold) in rows:
            ratio = float(ratio or 0)
            delta = float(delta or 0)
            threshold = float(threshold or 0)
            cap_clause = ""
            if capacity is not None and capacity > 0 and actual is not None:
                util = float(actual) / float(capacity)
                cap_clause = (f" Running at {util:.0%} of capacity."
                              if delta > 0 else f" Capacity utilisation {util:.0%}.")
            pct_off = (ratio - (ratio - delta)) * 0 + (ratio / max(ratio - delta, 1e-9) - 1) * 100  # roughly
            # Simpler narrative metric: just report % of dataset mean.
            mean_r = ratio - delta
            pct_off = ((ratio / mean_r) - 1) * 100 if mean_r > 0 else 0
            if delta < -threshold:
                out.append({
                    "location_id": loc_id,
                    "kind": "under",
                    "delta": round(delta, 3),
                    "actual_over_expected": round(ratio, 3),
                    "rationale": (
                        f"{name} actual demand {int(actual):,} vs expected "
                        f"{int(expected):,} — {pct_off:+.0f}% off baseline.{cap_clause}"
                    ),
                })
            elif delta > threshold:
                out.append({
                    "location_id": loc_id,
                    "kind": "over",
                    "delta": round(delta, 3),
                    "actual_over_expected": round(ratio, 3),
                    "rationale": (
                        f"{name} actual demand {int(actual):,} vs expected "
                        f"{int(expected):,} — {pct_off:+.0f}% above baseline.{cap_clause}"
                    ),
                })
        log.info("anomaly_detect (DuckDB): %d outliers from %d scored locations.",
                 len(out), len(rows))
        return out
    except Exception as e:
        log.warning("anomaly_detect DuckDB path failed (%s); using canned.", e)
        return canned.anomalies(scores)
