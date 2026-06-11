"""Geostatistics & spatial-pattern analysis.

The toolkit an urban / retail-network analyst reaches for to ask "is this
pattern real or random, and where are the hot/cold spots?":

  * morans_i            — global spatial autocorrelation: is the metric
                          clustered, dispersed, or random across the network?
  * local_morans (LISA) — per-location cluster type: High-High hot spot,
                          Low-Low cold spot, or High-Low / Low-High outlier.
  * getis_ord_hotspots  — Getis-Ord Gi* z-scores: statistically significant
                          hot and cold spots of the value.
  * idw_interpolate     — inverse-distance-weighted surface: estimate the
                          value at unsampled cells (a light geostatistical
                          interpolation; kriging's pragmatic cousin).
  * two_step_fca        — 2SFCA spatial accessibility: supply-to-demand ratio
                          accessibility score per demand cell.

Spatial weights are k-nearest-neighbour, row-standardised. Significance uses
conditional permutation (199 shuffles) for honest pseudo p-values without a
PySAL dependency — pure numpy, Windows-friendly. Every function returns an
`interpretation` string and a `quality` flag so the agent can speak plainly
and flag when n is too small to trust.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

log = logging.getLogger(__name__)

_PERMUTATIONS = 199
_RNG = np.random.default_rng(42)  # fixed seed → reproducible pseudo p-values


# ---------------------------------------------------------------------------
# Spatial weights
# ---------------------------------------------------------------------------

def _coords(points: list[dict]) -> tuple[np.ndarray, np.ndarray]:
    lat = np.array([float(p["lat"]) for p in points], dtype=float)
    lng = np.array([float(p["lng"]) for p in points], dtype=float)
    return lat, lng


def _knn_weights(lat: np.ndarray, lng: np.ndarray, k: int = 8) -> np.ndarray:
    """Row-standardised KNN spatial weights (n x n). Self-weight is 0."""
    n = len(lat)
    k = max(1, min(k, n - 1))
    R = 6_371_000.0
    la = np.radians(lat)
    dlat = la[:, None] - la[None, :]
    dlng = np.radians(lng)[:, None] - np.radians(lng)[None, :]
    h = np.sin(dlat / 2) ** 2 + np.cos(la)[:, None] * np.cos(la)[None, :] * np.sin(dlng / 2) ** 2
    dist = 2 * R * np.arcsin(np.sqrt(np.clip(h, 0, 1)))
    np.fill_diagonal(dist, np.inf)
    W = np.zeros((n, n))
    for i in range(n):
        nn = np.argpartition(dist[i], k)[:k]
        W[i, nn] = 1.0
    rs = W.sum(axis=1, keepdims=True)
    with np.errstate(invalid="ignore", divide="ignore"):
        W = np.where(rs > 0, W / rs, 0.0)
    return W


def _values(points: list[dict], value_key: str) -> np.ndarray | None:
    try:
        v = np.array([float(p.get(value_key)) for p in points], dtype=float)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(v).all():
        return None
    return v


# ---------------------------------------------------------------------------
# Global Moran's I
# ---------------------------------------------------------------------------

def morans_i(points: list[dict], value_key: str, k: int = 8) -> dict[str, Any]:
    v = _values(points, value_key)
    if v is None or len(points) < 6:
        return {"method": "morans_i", "error": "insufficient_data",
                "note": f"Need >=6 locations with numeric '{value_key}'."}
    n = len(v)
    W = _knn_weights(*_coords(points), k=k)
    z = v - v.mean()
    denom = (z ** 2).sum()
    lag = W @ z
    I = (n / W.sum()) * float((z * lag).sum()) / denom if denom > 0 else 0.0

    # permutation inference
    perm = np.empty(_PERMUTATIONS)
    for p in range(_PERMUTATIONS):
        zp = _RNG.permutation(z)
        perm[p] = (n / W.sum()) * float((zp * (W @ zp)).sum()) / denom
    ge = (perm >= I).sum()
    pseudo_p = (min(ge, _PERMUTATIONS - ge) + 1) / (_PERMUTATIONS + 1)
    expected = -1.0 / (n - 1)

    if pseudo_p > 0.1:
        pat, interp = "random", (
            f"The spatial pattern of {value_key} is statistically indistinguishable "
            f"from random (Moran's I={I:.2f}, p={pseudo_p:.2f}). Location isn't the "
            "main driver of the differences you see."
        )
    elif I > expected:
        pat, interp = "clustered", (
            f"{value_key} is spatially **clustered** (Moran's I={I:.2f}, p={pseudo_p:.2f}): "
            "high-performing sites sit near other high performers and weak ones cluster "
            "together. Worth a hot-spot (LISA) breakdown."
        )
    else:
        pat, interp = "dispersed", (
            f"{value_key} is spatially **dispersed** (Moran's I={I:.2f}, p={pseudo_p:.2f}): "
            "neighbouring sites tend to differ — a competitive checkerboard."
        )
    return {
        "method": "morans_i", "value_key": value_key,
        "morans_i": round(I, 4), "expected_i": round(expected, 4),
        "pseudo_p": round(float(pseudo_p), 4), "n": n,
        "pattern": pat, "interpretation": interp,
        "quality": "good" if n >= 12 else "moderate",
    }


# ---------------------------------------------------------------------------
# Local Moran's I (LISA)
# ---------------------------------------------------------------------------

def local_morans(points: list[dict], value_key: str, k: int = 8) -> dict[str, Any]:
    v = _values(points, value_key)
    if v is None or len(points) < 6:
        return {"method": "lisa", "error": "insufficient_data",
                "note": f"Need >=6 locations with numeric '{value_key}'."}
    n = len(v)
    W = _knn_weights(*_coords(points), k=k)
    z = v - v.mean()
    m2 = (z ** 2).sum() / n
    lag = W @ z
    Ii = (z / m2) * lag

    # permutation p per observation
    pvals = np.empty(n)
    for i in range(n):
        wi = W[i]
        sims = np.empty(_PERMUTATIONS)
        for p in range(_PERMUTATIONS):
            others = np.delete(z, i)
            samp = _RNG.permutation(others)
            zlag = (np.delete(wi, i) * samp).sum()
            sims[p] = (z[i] / m2) * zlag
        ge = (sims >= Ii[i]).sum()
        pvals[i] = (min(ge, _PERMUTATIONS - ge) + 1) / (_PERMUTATIONS + 1)

    out = []
    counts = {"HH": 0, "LL": 0, "HL": 0, "LH": 0, "ns": 0}
    for i, pt in enumerate(points):
        if pvals[i] > 0.05:
            cat = "ns"
        elif z[i] > 0 and lag[i] > 0:
            cat = "HH"
        elif z[i] < 0 and lag[i] < 0:
            cat = "LL"
        elif z[i] > 0 and lag[i] < 0:
            cat = "HL"
        else:
            cat = "LH"
        counts[cat] += 1
        q = dict(pt)
        q.update({"lisa_i": round(float(Ii[i]), 3), "lisa_p": round(float(pvals[i]), 3),
                  "cluster": cat})
        out.append(q)
    interp = (
        f"LISA on {value_key}: {counts['HH']} High-High hot spots, {counts['LL']} "
        f"Low-Low cold spots, {counts['HL'] + counts['LH']} spatial outliers, "
        f"{counts['ns']} not significant. Hot spots are your strongholds; cold spots "
        "are clusters of weakness worth a coordinated intervention."
    )
    return {"method": "lisa", "value_key": value_key, "counts": counts,
            "locations": out, "interpretation": interp,
            "quality": "good" if n >= 12 else "moderate"}


# ---------------------------------------------------------------------------
# Getis-Ord Gi* hot-spot analysis
# ---------------------------------------------------------------------------

def getis_ord_hotspots(points: list[dict], value_key: str, k: int = 8) -> dict[str, Any]:
    v = _values(points, value_key)
    if v is None or len(points) < 6:
        return {"method": "getis_ord", "error": "insufficient_data",
                "note": f"Need >=6 locations with numeric '{value_key}'."}
    n = len(v)
    # binary KNN incl. self (Gi*), row counts
    lat, lng = _coords(points)
    Wb = (_knn_weights(lat, lng, k=k) > 0).astype(float)
    np.fill_diagonal(Wb, 1.0)  # Gi* includes the focal point
    xbar, S = v.mean(), v.std(ddof=0)
    out, hot, cold = [], 0, 0
    for i in range(n):
        wi = Wb[i]
        wsum = wi.sum()
        num = (wi * v).sum() - xbar * wsum
        den = S * np.sqrt((n * (wi ** 2).sum() - wsum ** 2) / (n - 1))
        gi = float(num / den) if den > 0 else 0.0
        if gi >= 1.96:
            cat = "hot"; hot += 1
        elif gi <= -1.96:
            cat = "cold"; cold += 1
        else:
            cat = "ns"
        q = dict(points[i]); q.update({"gi_z": round(gi, 2), "hotspot": cat})
        out.append(q)
    interp = (
        f"Getis-Ord Gi* on {value_key}: {hot} statistically significant hot spot(s) "
        f"(z>=1.96) and {cold} cold spot(s) (z<=-1.96). Hot spots mark contiguous "
        "high-value territory — prioritise defending them; cold spots flag clusters "
        "to fix or exit."
    )
    return {"method": "getis_ord", "value_key": value_key, "hot": hot, "cold": cold,
            "locations": out, "interpretation": interp,
            "quality": "good" if n >= 12 else "moderate"}


# ---------------------------------------------------------------------------
# IDW interpolation (geostatistical surface)
# ---------------------------------------------------------------------------

def idw_interpolate(samples: list[dict], grid: list[dict], value_key: str,
                    power: float = 2.0, k: int = 12) -> dict[str, Any]:
    """Estimate `value_key` at each `grid` point from `samples` via
    inverse-distance weighting (k nearest samples). Returns grid annotated
    with `idw_value`."""
    sv = _values(samples, value_key)
    if sv is None or not grid:
        return {"method": "idw", "error": "insufficient_data", "grid": []}
    slat, slng = _coords(samples)
    glat, glng = _coords(grid)
    R = 6_371_000.0
    out = []
    k = max(1, min(k, len(samples)))
    for gi in range(len(grid)):
        dlat = np.radians(slat) - np.radians(glat[gi])
        dlng = np.radians(slng) - np.radians(glng[gi])
        h = np.sin(dlat / 2) ** 2 + np.cos(np.radians(glat[gi])) * np.cos(np.radians(slat)) * np.sin(dlng / 2) ** 2
        d = 2 * R * np.arcsin(np.sqrt(np.clip(h, 0, 1)))
        nn = np.argpartition(d, k - 1)[:k]
        dn = d[nn]
        if (dn < 1e-6).any():
            val = float(sv[nn][dn < 1e-6][0])
        else:
            w = 1.0 / np.power(dn, power)
            val = float((w * sv[nn]).sum() / w.sum())
        q = dict(grid[gi]); q["idw_value"] = round(val, 2)
        out.append(q)
    return {"method": "idw", "value_key": value_key, "power": power, "grid": out,
            "interpretation": (
                f"Interpolated a continuous {value_key} surface from {len(samples)} "
                f"sampled points over {len(grid)} grid cells using IDW (power={power}). "
                "Peaks show where the metric is expected to be highest between your sites."
            ),
            "quality": "good" if len(samples) >= 10 else "moderate"}


# ---------------------------------------------------------------------------
# 2SFCA — two-step floating catchment area accessibility
# ---------------------------------------------------------------------------

def two_step_fca(demand: list[dict], facilities: list[dict], radius_m: float = 1000.0,
                 demand_weight_key: str = "population",
                 supply_key: str = "capacity") -> dict[str, Any]:
    """Two-Step Floating Catchment Area accessibility.

    Step 1: each facility's supply-to-demand ratio R_j = supply_j / (demand
    within radius). Step 2: each demand point's accessibility = sum of R_j of
    facilities within radius. High = well served, low = access-poor."""
    if not demand or not facilities:
        return {"method": "two_step_fca", "error": "empty_input", "demand": []}
    dlat, dlng = _coords(demand)
    flat, flng = _coords(facilities)
    w = np.array([float(p.get(demand_weight_key) or 1.0) for p in demand])
    supply = np.array([float(f.get(supply_key) or 1.0) for f in facilities])
    R = 6_371_000.0

    def dmat(alat, alng, blat, blng):
        la = np.radians(alat)[:, None]; lb = np.radians(blat)[None, :]
        dlat_ = lb - la
        dlng_ = np.radians(blng)[None, :] - np.radians(alng)[:, None]
        h = np.sin(dlat_ / 2) ** 2 + np.cos(la) * np.cos(lb) * np.sin(dlng_ / 2) ** 2
        return 2 * R * np.arcsin(np.sqrt(np.clip(h, 0, 1)))

    D = dmat(dlat, dlng, flat, flng)  # (demand, facility)
    within = D <= radius_m
    # Step 1
    Rj = np.zeros(len(facilities))
    for j in range(len(facilities)):
        served = w[within[:, j]].sum()
        Rj[j] = supply[j] / served if served > 0 else 0.0
    # Step 2
    out = []
    acc = within @ Rj
    for i, p in enumerate(demand):
        q = dict(p); q["access_2sfca"] = round(float(acc[i]), 4); out.append(q)
    amax = float(acc.max()) if len(acc) else 0.0
    underserved = int((acc < 0.25 * amax).sum()) if amax > 0 else 0
    return {"method": "two_step_fca", "radius_m": radius_m, "demand": out,
            "interpretation": (
                f"2SFCA accessibility computed for {len(demand)} demand cells against "
                f"{len(facilities)} facilities ({int(radius_m)}m catchment). "
                f"{underserved} cells fall below a quarter of peak access — these are "
                "the access-poor neighbourhoods an expansion should target."
            ),
            "quality": "good" if len(facilities) >= 5 else "moderate"}
