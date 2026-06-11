"""Coverage & location-allocation optimisation.

Implements the classic facility-location models used in pre-project
geomarketing analysis:

  * p_median          — place P facilities to minimise total weighted
                        demand-to-nearest-facility distance.
  * lscp              — Location Set Covering Problem: fewest facilities so
                        every demand point is within `radius_m` of one.
  * mclp              — Maximal Coverage Location Problem: with P facilities,
                        cover the most demand within `radius_m`.
  * location_allocate — assign demand points to their nearest open facility
                        (with optional capacity), returning the allocation.

All MILPs are built with PuLP and solved by the bundled CBC solver (no
external solver, Windows-friendly). Distances are great-circle metres via a
vectorised haversine. Demand is capped (default 400 points) and the solver
gets a wall-clock limit so the live demo never hangs; when CBC can't prove
optimality in time it returns the best feasible solution, and MCLP/LSCP also
have a greedy fallback.

Inputs are plain lists of dicts so the chat router can assemble them from
DuckDB (Kontur population cells = demand; H3 candidate cells or user
locations = candidate facilities).
"""

from __future__ import annotations

import logging
import math
from typing import Any

import numpy as np

log = logging.getLogger(__name__)

_SOLVER_TIME_LIMIT_S = 12
_MAX_DEMAND = 400
_MAX_CANDIDATES = 200


# ---------------------------------------------------------------------------
# Distance
# ---------------------------------------------------------------------------

def _haversine_matrix(a_lat: np.ndarray, a_lng: np.ndarray,
                      b_lat: np.ndarray, b_lng: np.ndarray) -> np.ndarray:
    """Great-circle distance matrix in metres. Shape (len(a), len(b))."""
    R = 6_371_000.0
    a_lat_r = np.radians(a_lat)[:, None]
    b_lat_r = np.radians(b_lat)[None, :]
    dlat = b_lat_r - a_lat_r
    dlng = np.radians(b_lng)[None, :] - np.radians(a_lng)[:, None]
    h = np.sin(dlat / 2) ** 2 + np.cos(a_lat_r) * np.cos(b_lat_r) * np.sin(dlng / 2) ** 2
    return 2 * R * np.arcsin(np.sqrt(np.clip(h, 0, 1)))


def _coerce(points: list[dict], weight_key: str | None = None) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    lat = np.array([float(p["lat"]) for p in points], dtype=float)
    lng = np.array([float(p["lng"]) for p in points], dtype=float)
    if weight_key:
        w = np.array([float(p.get(weight_key) or 0.0) for p in points], dtype=float)
    else:
        w = np.ones(len(points), dtype=float)
    return lat, lng, w


def _downsample(points: list[dict], cap: int, weight_key: str | None = None) -> list[dict]:
    """Keep the `cap` heaviest points (by weight) for tractability."""
    if len(points) <= cap:
        return points
    if weight_key:
        return sorted(points, key=lambda p: float(p.get(weight_key) or 0.0), reverse=True)[:cap]
    # Even stride sample to preserve spatial spread.
    step = max(1, len(points) // cap)
    return points[::step][:cap]


# ---------------------------------------------------------------------------
# P-Median
# ---------------------------------------------------------------------------

def p_median(demand: list[dict], candidates: list[dict], p: int,
             demand_weight_key: str = "population") -> dict[str, Any]:
    """Choose `p` facilities from `candidates` minimising total weighted
    demand-to-nearest distance. Returns selected sites + objective + the
    mean weighted distance (accessibility KPI)."""
    import pulp

    demand = _downsample(demand, _MAX_DEMAND, demand_weight_key)
    candidates = _downsample(candidates, _MAX_CANDIDATES)
    if not demand or not candidates:
        return {"error": "empty_input", "selected": []}
    p = max(1, min(p, len(candidates)))

    dlat, dlng, w = _coerce(demand, demand_weight_key)
    clat, clng, _ = _coerce(candidates)
    dist = _haversine_matrix(dlat, dlng, clat, clng)  # (I, J) metres
    nI, nJ = dist.shape

    prob = pulp.LpProblem("p_median", pulp.LpMinimize)
    x = [pulp.LpVariable(f"x_{j}", cat="Binary") for j in range(nJ)]
    y = {(i, j): pulp.LpVariable(f"y_{i}_{j}", cat="Binary")
         for i in range(nI) for j in range(nJ)}

    prob += pulp.lpSum(w[i] * dist[i, j] * y[(i, j)] for i in range(nI) for j in range(nJ))
    prob += pulp.lpSum(x) == p
    for i in range(nI):
        prob += pulp.lpSum(y[(i, j)] for j in range(nJ)) == 1
        for j in range(nJ):
            prob += y[(i, j)] <= x[j]
    prob.solve(pulp.PULP_CBC_CMD(msg=0, timeLimit=_SOLVER_TIME_LIMIT_S))

    chosen = [j for j in range(nJ) if x[j].value() and x[j].value() > 0.5]
    if not chosen:  # solver failed → fall back to greedy p-median
        chosen = _greedy_pmedian(dist, w, p)
    # Accessibility: weighted mean distance to nearest chosen facility.
    nearest = dist[:, chosen].min(axis=1)
    wmean = float((nearest * w).sum() / max(w.sum(), 1e-9))
    selected = [candidates[j] for j in chosen]
    return {
        "method": "p_median",
        "selected": selected,
        "p": p,
        "weighted_mean_distance_m": round(wmean, 1),
        "demand_points": nI,
        "candidate_points": nJ,
        "status": pulp.LpStatus[prob.status],
    }


def _greedy_pmedian(dist: np.ndarray, w: np.ndarray, p: int) -> list[int]:
    chosen: list[int] = []
    best = np.full(dist.shape[0], np.inf)
    for _ in range(p):
        # pick the candidate that most reduces total weighted nearest distance
        gains = []
        for j in range(dist.shape[1]):
            if j in chosen:
                gains.append(np.inf)
                continue
            cand = np.minimum(best, dist[:, j])
            gains.append(float((cand * w).sum()))
        j = int(np.argmin(gains))
        chosen.append(j)
        best = np.minimum(best, dist[:, j])
    return chosen


# ---------------------------------------------------------------------------
# LSCP — minimum facilities to cover all demand within radius
# ---------------------------------------------------------------------------

def lscp(demand: list[dict], candidates: list[dict], radius_m: float,
         demand_weight_key: str = "population") -> dict[str, Any]:
    import pulp

    demand = _downsample(demand, _MAX_DEMAND, demand_weight_key)
    candidates = _downsample(candidates, _MAX_CANDIDATES)
    if not demand or not candidates:
        return {"error": "empty_input", "selected": []}

    dlat, dlng, w = _coerce(demand, demand_weight_key)
    clat, clng, _ = _coerce(candidates)
    cover = (_haversine_matrix(dlat, dlng, clat, clng) <= radius_m).astype(int)  # (I,J)
    nI, nJ = cover.shape
    coverable = cover.sum(axis=1) > 0  # demand points that ANY candidate can cover

    prob = pulp.LpProblem("lscp", pulp.LpMinimize)
    x = [pulp.LpVariable(f"x_{j}", cat="Binary") for j in range(nJ)]
    prob += pulp.lpSum(x)
    for i in range(nI):
        if coverable[i]:
            prob += pulp.lpSum(cover[i, j] * x[j] for j in range(nJ)) >= 1
    prob.solve(pulp.PULP_CBC_CMD(msg=0, timeLimit=_SOLVER_TIME_LIMIT_S))

    chosen = [j for j in range(nJ) if x[j].value() and x[j].value() > 0.5]
    if not chosen:
        chosen = _greedy_cover(cover, w, k=None)
    covered_mask = cover[:, chosen].sum(axis=1) > 0 if chosen else np.zeros(nI, bool)
    return {
        "method": "lscp",
        "selected": [candidates[j] for j in chosen],
        "facilities_needed": len(chosen),
        "radius_m": radius_m,
        "demand_covered_pct": round(100.0 * w[covered_mask].sum() / max(w.sum(), 1e-9), 1),
        "uncoverable_demand_points": int((~coverable).sum()),
        "status": pulp.LpStatus[prob.status],
    }


# ---------------------------------------------------------------------------
# MCLP — maximise covered demand with P facilities
# ---------------------------------------------------------------------------

def mclp(demand: list[dict], candidates: list[dict], p: int, radius_m: float,
         demand_weight_key: str = "population") -> dict[str, Any]:
    import pulp

    demand = _downsample(demand, _MAX_DEMAND, demand_weight_key)
    candidates = _downsample(candidates, _MAX_CANDIDATES)
    if not demand or not candidates:
        return {"error": "empty_input", "selected": []}
    p = max(1, min(p, len(candidates)))

    dlat, dlng, w = _coerce(demand, demand_weight_key)
    clat, clng, _ = _coerce(candidates)
    cover = (_haversine_matrix(dlat, dlng, clat, clng) <= radius_m).astype(int)
    nI, nJ = cover.shape

    prob = pulp.LpProblem("mclp", pulp.LpMaximize)
    x = [pulp.LpVariable(f"x_{j}", cat="Binary") for j in range(nJ)]
    z = [pulp.LpVariable(f"z_{i}", cat="Binary") for i in range(nI)]
    prob += pulp.lpSum(w[i] * z[i] for i in range(nI))
    prob += pulp.lpSum(x) == p
    for i in range(nI):
        prob += z[i] <= pulp.lpSum(cover[i, j] * x[j] for j in range(nJ))
    prob.solve(pulp.PULP_CBC_CMD(msg=0, timeLimit=_SOLVER_TIME_LIMIT_S))

    chosen = [j for j in range(nJ) if x[j].value() and x[j].value() > 0.5]
    if not chosen:
        chosen = _greedy_cover(cover, w, k=p)
    covered_mask = cover[:, chosen].sum(axis=1) > 0 if chosen else np.zeros(nI, bool)
    return {
        "method": "mclp",
        "selected": [candidates[j] for j in chosen],
        "p": p,
        "radius_m": radius_m,
        "demand_covered_pct": round(100.0 * w[covered_mask].sum() / max(w.sum(), 1e-9), 1),
        "demand_covered_abs": int(w[covered_mask].sum()),
        "demand_total": int(w.sum()),
        "status": pulp.LpStatus[prob.status],
    }


def _greedy_cover(cover: np.ndarray, w: np.ndarray, k: int | None) -> list[int]:
    """Greedy max-coverage: repeatedly add the candidate covering the most
    still-uncovered weighted demand. k=None → cover everything (LSCP)."""
    nI, nJ = cover.shape
    uncovered = np.ones(nI, bool)
    chosen: list[int] = []
    while True:
        if k is not None and len(chosen) >= k:
            break
        if not uncovered.any():
            break
        best_j, best_gain = -1, -1.0
        for j in range(nJ):
            if j in chosen:
                continue
            gain = float(w[uncovered & (cover[:, j] > 0)].sum())
            if gain > best_gain:
                best_gain, best_j = gain, j
        if best_j < 0 or best_gain <= 0:
            break
        chosen.append(best_j)
        uncovered &= ~(cover[:, best_j] > 0)
    return chosen


# ---------------------------------------------------------------------------
# Location-allocation: assign demand → nearest open facility
# ---------------------------------------------------------------------------

def location_allocate(demand: list[dict], facilities: list[dict],
                      demand_weight_key: str = "population") -> dict[str, Any]:
    """Assign each demand point to its nearest facility; report per-facility
    captured demand + the average distance. Pure nearest-assignment (no
    capacity) — fast, used to visualise catchment allocation."""
    if not demand or not facilities:
        return {"error": "empty_input", "allocation": []}
    dlat, dlng, w = _coerce(demand, demand_weight_key)
    flat, flng, _ = _coerce(facilities)
    dist = _haversine_matrix(dlat, dlng, flat, flng)
    nearest = dist.argmin(axis=1)
    out = []
    for j, f in enumerate(facilities):
        mask = nearest == j
        out.append({
            **f,
            "captured_demand": int(w[mask].sum()),
            "assigned_points": int(mask.sum()),
            "avg_distance_m": round(float(dist[mask, j].mean()), 1) if mask.any() else None,
        })
    return {
        "method": "location_allocate",
        "allocation": out,
        "total_demand": int(w.sum()),
    }
