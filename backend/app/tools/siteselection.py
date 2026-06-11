"""Site selection & whitespace analysis.

Answers the questions a network planner actually asks:

  * rank_sites          — multi-criteria suitability (MCDA / weighted
                          overlay): score every candidate on normalised
                          criteria (demand up, competition down, accessibility
                          up, …), rank, and name the winner + why.
  * best_new_point      — pick the single best site to ADD to the existing
                          network by marginal demand newly captured within a
                          catchment (greedy marginal coverage).
  * whitespace_gaps     — find under-served "white space": cells with high
                          demand that sit far from every existing facility.

Each returns a plain-English `interpretation` and a `quality` flag.
Distances are vectorised great-circle metres; criteria are min-max
normalised so weights are comparable.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

log = logging.getLogger(__name__)


def _coords(points: list[dict]) -> tuple[np.ndarray, np.ndarray]:
    return (np.array([float(p["lat"]) for p in points]),
            np.array([float(p["lng"]) for p in points]))


def _dmat(alat, alng, blat, blng) -> np.ndarray:
    R = 6_371_000.0
    la = np.radians(alat)[:, None]; lb = np.radians(blat)[None, :]
    dlat = lb - la
    dlng = np.radians(blng)[None, :] - np.radians(alng)[:, None]
    h = np.sin(dlat / 2) ** 2 + np.cos(la) * np.cos(lb) * np.sin(dlng / 2) ** 2
    return 2 * R * np.arcsin(np.sqrt(np.clip(h, 0, 1)))


def _minmax(a: np.ndarray, invert: bool = False) -> np.ndarray:
    a = np.asarray(a, dtype=float)
    lo, hi = a.min(), a.max()
    if hi - lo < 1e-12:
        norm = np.zeros_like(a)
    else:
        norm = (a - lo) / (hi - lo)
    return 1.0 - norm if invert else norm


# ---------------------------------------------------------------------------
# Multi-criteria suitability (MCDA / weighted overlay)
# ---------------------------------------------------------------------------

# Default criteria: (key, weight, invert?). invert=True means "less is better".
DEFAULT_CRITERIA = [
    ("population_800m", 0.40, False),
    ("competitor_banks_500m", 0.25, True),
    ("csdi_commercial_500m", 0.15, False),
    ("csdi_transport_500m", 0.20, False),
]


def rank_sites(candidates: list[dict],
               criteria: list[tuple[str, float, bool]] | None = None,
               build_context: bool = True) -> dict[str, Any]:
    """Score candidates by a weighted, normalised multi-criteria model.

    If `build_context`, spatial-context features (population, competitors,
    commercial/transport POIs around each candidate) are computed and used as
    the default criteria. Otherwise criteria must already be present as keys
    on each candidate dict. Returns candidates with `suitability` (0..100),
    ranked best-first, plus the winner and a contribution breakdown."""
    if not candidates:
        return {"method": "rank_sites", "error": "empty_input", "results": []}

    enriched = candidates
    crit = criteria or DEFAULT_CRITERIA
    if build_context:
        from app.tools.similarity import build_feature_vectors
        X, names = build_feature_vectors(candidates)
        idx = {n: i for i, n in enumerate(names)}
        enriched = []
        for r, cand in enumerate(candidates):
            q = dict(cand)
            for n in names:
                q.setdefault(n, float(X[r, idx[n]]))
            enriched.append(q)

    # keep only criteria whose key is present
    crit = [(k, w, inv) for (k, w, inv) in crit if any(k in c for c in enriched)]
    if not crit:
        return {"method": "rank_sites", "error": "no_usable_criteria", "results": []}
    wsum = sum(w for _, w, _ in crit) or 1.0

    contrib_cols = {}
    score = np.zeros(len(enriched))
    for key, weight, invert in crit:
        raw = np.array([float(c.get(key) or 0.0) for c in enriched])
        norm = _minmax(raw, invert=invert)
        contrib_cols[key] = norm * (weight / wsum)
        score += contrib_cols[key]
    score100 = (score * 100.0)

    results = []
    for i, c in enumerate(enriched):
        q = dict(c)
        q["suitability"] = round(float(score100[i]), 1)
        q["score_breakdown"] = {k: round(float(contrib_cols[k][i] * 100), 1) for k in contrib_cols}
        results.append(q)
    results.sort(key=lambda d: d["suitability"], reverse=True)
    winner = results[0]
    interp = (
        f"Ranked {len(results)} candidate sites on {len(crit)} weighted criteria. "
        f"Top site scores {winner['suitability']}/100"
        + (f" — '{winner.get('name')}'" if winner.get('name') else "")
        + ". Higher scores combine strong surrounding demand, light competition, and "
        "good commercial/transport context."
    )
    return {"method": "rank_sites", "criteria": [c[0] for c in crit],
            "results": results, "winner": winner, "interpretation": interp,
            "quality": "good" if len(results) >= 3 else "moderate"}


# ---------------------------------------------------------------------------
# Best new point to add (marginal coverage)
# ---------------------------------------------------------------------------

def best_new_point(options: list[dict], existing: list[dict], demand: list[dict],
                   radius_m: float = 800.0, demand_weight_key: str = "population") -> dict[str, Any]:
    """Of the candidate `options`, which single new site captures the most
    demand NOT already served by `existing` facilities within `radius_m`?
    Greedy marginal coverage — the classic 'where do I open next' answer."""
    if not options or not demand:
        return {"method": "best_new_point", "error": "empty_input", "ranked": []}
    dlat, dlng = _coords(demand)
    w = np.array([float(p.get(demand_weight_key) or 0.0) for p in demand])

    if existing:
        elat, elng = _coords(existing)
        already = (_dmat(dlat, dlng, elat, elng) <= radius_m).any(axis=1)
    else:
        already = np.zeros(len(demand), bool)
    uncovered = w.copy()
    uncovered[already] = 0.0  # demand existing network already reaches

    olat, olng = _coords(options)
    Do = _dmat(dlat, dlng, olat, olng) <= radius_m  # (demand, option)
    ranked = []
    for j, opt in enumerate(options):
        new_capture = float(uncovered[Do[:, j]].sum())
        total_capture = float(w[Do[:, j]].sum())
        q = dict(opt)
        q["new_demand_captured"] = int(new_capture)
        q["total_demand_in_catchment"] = int(total_capture)
        ranked.append(q)
    ranked.sort(key=lambda d: d["new_demand_captured"], reverse=True)
    best = ranked[0]
    interp = (
        f"Evaluated {len(options)} candidate sites for marginal coverage within "
        f"{int(radius_m)}m. The best addition"
        + (f", '{best.get('name')}', " if best.get('name') else " ")
        + f"reaches {best['new_demand_captured']:,} residents the current network "
        "doesn't already cover — the highest net-new catchment of the options."
    )
    return {"method": "best_new_point", "radius_m": radius_m, "ranked": ranked,
            "best": best, "interpretation": interp,
            "quality": "good" if len(demand) >= 50 else "moderate"}


# ---------------------------------------------------------------------------
# Whitespace / gap detection
# ---------------------------------------------------------------------------

def whitespace_gaps(demand: list[dict], facilities: list[dict], top_n: int = 25,
                    demand_weight_key: str = "population",
                    min_distance_m: float = 600.0) -> dict[str, Any]:
    """Under-served white space: demand cells that are both high-demand and
    far from every existing facility. Score = norm(demand) * norm(distance to
    nearest facility), only for cells beyond `min_distance_m`. Returns the
    top gaps — candidate areas for expansion."""
    if not demand:
        return {"method": "whitespace", "error": "empty_input", "gaps": []}
    dlat, dlng = _coords(demand)
    w = np.array([float(p.get(demand_weight_key) or 0.0) for p in demand])
    if facilities:
        flat, flng = _coords(facilities)
        nearest = _dmat(dlat, dlng, flat, flng).min(axis=1)
    else:
        nearest = np.full(len(demand), 1e9)
    eligible = nearest >= min_distance_m
    if not eligible.any():
        return {"method": "whitespace", "gaps": [],
                "interpretation": "No under-served gaps: every demand cell is already "
                                  f"within {int(min_distance_m)}m of a facility.",
                "quality": "good"}
    score = _minmax(np.where(eligible, w, 0.0)) * _minmax(np.where(eligible, nearest, 0.0))
    order = np.argsort(-score)
    gaps = []
    for i in order:
        if not eligible[i] or score[i] <= 0:
            continue
        q = dict(demand[int(i)])
        q["gap_score"] = round(float(score[i]), 4)
        q["distance_to_nearest_m"] = round(float(nearest[int(i)]), 0)
        gaps.append(q)
        if len(gaps) >= top_n:
            break
    interp = (
        f"Found {len(gaps)} under-served white-space cell(s): high residential demand "
        f"sitting >{int(min_distance_m)}m from any existing site. The top gap holds "
        f"~{int(gaps[0].get(demand_weight_key, 0)):,} residents "
        f"{int(gaps[0]['distance_to_nearest_m'])}m from the nearest branch — a clean "
        "expansion candidate."
    ) if gaps else "No significant white space found."
    return {"method": "whitespace", "gaps": gaps, "interpretation": interp,
            "quality": "good" if len(demand) >= 50 else "moderate"}
