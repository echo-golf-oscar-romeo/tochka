"""Canned tool returns for demo mode.

Deterministic. Never hits the network. Approximations only — the goal is to make
the orchestrator + UI loop runnable end-to-end before any real CSDI integration.
"""

from __future__ import annotations

import math
from typing import Any

from app.models.network import Location

# Approximate centre for HK pilot — Sham Shui Po-ish.
PILOT_CENTRE = (114.165, 22.330)


def _approx_offset(lat: float, lng: float, dx_m: float, dy_m: float) -> tuple[float, float]:
    """Approximate metre offset → lat/lng. Good enough for canned shapes."""
    return (lng + dx_m / (111_320 * math.cos(math.radians(lat))), lat + dy_m / 110_540)


def geocode(locations: list[Location]) -> None:
    """Fill in missing coords near the pilot centre. Mutates in place."""
    for i, loc in enumerate(locations):
        if loc.lat is None or loc.lng is None:
            lng, lat = _approx_offset(PILOT_CENTRE[1], PILOT_CENTRE[0],
                                      dx_m=(i % 7) * 300 - 900, dy_m=(i // 7) * 300 - 600)
            loc.lat = lat
            loc.lng = lng
        loc.geocoded = True
        loc.geocode_confidence = 0.92


def location_search(query: str) -> list[dict[str, Any]]:
    return [{"name": query, "lat": PILOT_CENTRE[1], "lng": PILOT_CENTRE[0], "confidence": 0.85}]


def isochrones_walk(locations: list[Location], minutes: int) -> list[dict[str, Any]]:
    """A rough circle around each point. Real implementation: alpha-shape on CSDI route nodes."""
    radius_m = minutes * 80    # ~80 m / min walking
    features: list[dict[str, Any]] = []
    for loc in locations:
        if loc.lat is None or loc.lng is None:
            continue
        ring: list[list[float]] = []
        for k in range(33):
            theta = (2 * math.pi * k) / 32
            lng, lat = _approx_offset(loc.lat, loc.lng,
                                      dx_m=radius_m * math.cos(theta),
                                      dy_m=radius_m * math.sin(theta))
            ring.append([lng, lat])
        features.append({
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [ring]},
            "properties": {"location_id": loc.id, "minutes": minutes},
        })
    return features


def competitors_in_radius(locations: list[Location], radius_m: int) -> list[dict[str, Any]]:
    """Two fake competitor banks near each user location."""
    out: list[dict[str, Any]] = []
    brands = ["HSBC", "Hang Seng", "Standard Chartered"]
    for i, loc in enumerate(locations):
        if loc.lat is None or loc.lng is None:
            continue
        for j in range(2):
            lng, lat = _approx_offset(loc.lat, loc.lng,
                                      dx_m=((i + j) % 5 - 2) * 150,
                                      dy_m=((i + j) % 3 - 1) * 200)
            out.append({
                "id": f"comp-{i}-{j}",
                "name": brands[(i + j) % len(brands)],
                "brand": brands[(i + j) % len(brands)],
                "lat": lat,
                "lng": lng,
                "distance_m": 150 + j * 80,
            })
    return out


def gmaps_pois(bbox: tuple[float, float, float, float], category: str) -> list[dict[str, Any]]:
    return [{"name": f"{category}-poi-{i}", "lat": bbox[1], "lng": bbox[0]} for i in range(3)]


def population_in_polygon(polygons: list[dict[str, Any]]) -> dict[str, Any]:
    """Pretend each isochrone covers 12k–45k residents."""
    per_polygon = []
    total = 0
    for i, p in enumerate(polygons):
        pop = 12_000 + (i * 4_600) % 33_000
        total += pop
        per_polygon.append({
            "polygon_id": p.get("properties", {}).get("location_id", f"poly-{i}"),
            "total": pop,
        })
    return {"per_polygon": per_polygon, "total_population": total}


def demographic_breakdown(polygons: list[dict[str, Any]], brackets: tuple[str, ...]) -> dict[str, Any]:
    base = population_in_polygon(polygons)
    for row in base["per_polygon"]:
        share = [0.18, 0.34, 0.28, 0.20][: len(brackets)]
        row["brackets"] = {b: int(row["total"] * s) for b, s in zip(brackets, share, strict=False)}
    return base


def points_in_polygon(points: list[dict], polygons: list[dict]) -> list[dict[str, Any]]:
    return [{"polygon_id": p.get("properties", {}).get("location_id", f"poly-{i}"),
             "point_ids": [pt.get("id") for pt in points[: max(1, i + 1)]]} for i, p in enumerate(polygons)]


def nearest_neighbor(a: list[dict], b: list[dict], k: int) -> list[dict[str, Any]]:
    return [{"id": pt.get("id"), "neighbors": [{"id": n.get("id"), "distance_m": 120 + 40 * i}
                                                for i, n in enumerate(b[:k])]} for pt in a]


def spatial_sql(query: str) -> list[dict[str, Any]]:
    return [{"note": "canned response", "query_preview": query[:80]}]


def h3_aggregate(points: list[dict], resolution: int, weight_field: str | None) -> dict[str, Any]:
    return {"resolution": resolution, "cells": [{"h3": f"h3-{i:04x}", "value": (i * 13) % 87} for i in range(40)]}


def hex_bin(bbox: tuple[float, float, float, float], resolution: int) -> list[dict[str, Any]]:
    return [{"h3": f"h3-{i:04x}", "centre": [bbox[0], bbox[1]]} for i in range(20)]


def huff_scores(locations: list[Location]) -> list[dict[str, Any]]:
    """Synthetic Huff-style expected-demand score per location, carrying
    capacity and actual_volume forward if the uploader provided them so
    anomaly detection can use a real ratio rather than a pure-rank proxy.
    """
    out: list[dict[str, Any]] = []
    for i, loc in enumerate(locations):
        score = 0.55 + 0.32 * math.sin(i * 0.7)
        out.append({
            "location_id": loc.id,
            "name": loc.name,
            "expected_demand": int(8_000 + 5_000 * score),
            "score": round(score, 3),
            "capacity": loc.capacity,
            "actual_volume": loc.actual_volume,
            "rationale": (
                f"{loc.name}: catchment of {int(15_000 + 9_000 * score):,} residents, "
                f"{(i % 3) + 1} competitor branch(es) nearby."
            ),
        })
    return out


def anomalies(scores: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """If actual_volume is provided on at least half the scores, run a real
    actual-vs-expected ratio test (z-score-ish). Otherwise fall back to the
    bottom-3 / top-2 by predicted-demand rank used in the original skeleton.
    """
    has_actual = [s for s in scores if s.get("actual_volume") is not None
                                       and s.get("expected_demand")]
    out: list[dict[str, Any]] = []
    if len(has_actual) >= max(2, len(scores) // 2):
        ratios = []
        for s in has_actual:
            r = float(s["actual_volume"]) / float(s["expected_demand"])
            ratios.append((s, r))
        # mean + stdev across the set with actuals
        vals = [r for _, r in ratios]
        mean = sum(vals) / len(vals)
        var = sum((v - mean) ** 2 for v in vals) / max(1, len(vals) - 1)
        sd = var ** 0.5
        thresh = max(0.10, 1.5 * sd)   # at least ±10% to flag
        for s, r in ratios:
            delta = r - mean
            if delta < -thresh:
                cap_clause = ""
                if s.get("capacity"):
                    util = float(s["actual_volume"]) / float(s["capacity"])
                    cap_clause = f" Capacity utilisation {util:.0%}."
                out.append({
                    "location_id": s["location_id"],
                    "kind": "under",
                    "delta": round(delta, 3),
                    "actual_over_expected": round(r, 3),
                    "rationale": (
                        f"{s['name']} actual demand {int(s['actual_volume']):,} vs expected "
                        f"{int(s['expected_demand']):,} — {(r - 1) * 100:+.0f}% off baseline.{cap_clause}"
                    ),
                })
            elif delta > thresh:
                cap_clause = ""
                if s.get("capacity"):
                    util = float(s["actual_volume"]) / float(s["capacity"])
                    cap_clause = f" Running at {util:.0%} of capacity."
                out.append({
                    "location_id": s["location_id"],
                    "kind": "over",
                    "delta": round(delta, 3),
                    "actual_over_expected": round(r, 3),
                    "rationale": (
                        f"{s['name']} actual demand {int(s['actual_volume']):,} vs expected "
                        f"{int(s['expected_demand']):,} — {(r - 1) * 100:+.0f}% above baseline.{cap_clause}"
                    ),
                })
        return out

    # Fallback path — no actuals, use rank as a proxy. Preserves the demo
    # storymap when uploaders haven't provided operational columns.
    sorted_scores = sorted(scores, key=lambda s: s["score"])
    for s in sorted_scores[:3]:
        out.append({
            "location_id": s["location_id"],
            "kind": "under",
            "delta": -0.28,
            "rationale": f"{s['name']} underperforming: {s['rationale']}",
        })
    for s in sorted_scores[-2:]:
        out.append({
            "location_id": s["location_id"],
            "kind": "over",
            "delta": 0.31,
            "rationale": f"{s['name']} overperforming: {s['rationale']}",
        })
    return out
