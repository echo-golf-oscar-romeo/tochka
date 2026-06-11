"""Location embeddings, similarity search & clustering.

The "find similar locations" workflow from geomarketing practice: describe
every location by a feature vector built from its *spatial context* — how
much population, how many competitors, how many POIs of each kind sit
around it, how central it is — then use cosine similarity to find the
locations most like a chosen successful one, or KMeans to segment the
network into types.

Feature vector per point (the embedding):
  - population within 800m  (Kontur hexes)
  - competitor banks within 500m  (osm_pois)
  - CSDI POIs within 500m, by category  (school, medical, transport,
    commercial, government, recreation)
  - distance to the CBD (Central)

Vectors are z-scored (StandardScaler) before cosine similarity so no single
big-magnitude feature dominates. Pure scikit-learn; Windows-friendly.
"""

from __future__ import annotations

import logging
import math
from typing import Any

import numpy as np

from app.clients.ddb import (
    ensure_csdi_pois_loaded,
    ensure_kontur_loaded,
    ensure_osm_loaded,
    get_duckdb,
)

log = logging.getLogger(__name__)

CBD_LAT, CBD_LNG = 22.2819, 114.1582  # Central, HK
_CSDI_CATS = ["school", "medical", "transport", "commercial", "government", "recreation"]
FEATURE_NAMES = (
    ["population_800m", "competitor_banks_500m"]
    + [f"csdi_{c}_500m" for c in _CSDI_CATS]
    + ["dist_to_cbd_km"]
)


def _haversine_km(lat1, lng1, lat2, lng2) -> float:
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlng / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def build_feature_vectors(points: list[dict]) -> tuple[np.ndarray, list[str]]:
    """Return (matrix [n_points, n_features], feature_names).

    Each row is the spatial-context embedding of one point. Uses the loaded
    DuckDB tables; counts are computed per point with spheroid distance."""
    conn = get_duckdb()
    ensure_kontur_loaded(conn)
    ensure_osm_loaded(conn)
    have_csdi = ensure_csdi_pois_loaded(conn)

    def _scalar(sql: str, params: list) -> float:
        try:
            v = conn.execute(sql, params).fetchone()[0]
            return float(v or 0.0)
        except Exception:  # noqa: BLE001 — missing/unloaded table → 0
            return 0.0

    rows = []
    for p in points:
        lat, lng = float(p["lat"]), float(p["lng"])
        pop = _scalar(
            "SELECT COALESCE(SUM(population),0) FROM kontur_pop_hex "
            "WHERE ST_Distance_Spheroid(ST_Point(lat,lng), ST_Point(?,?)) <= 800",
            [lat, lng],
        )
        comp = _scalar(
            "SELECT COUNT(*) FROM osm_pois WHERE type='bank' "
            "AND ST_Distance_Spheroid(ST_Point(lat,lng), ST_Point(?,?)) <= 500",
            [lat, lng],
        )
        cat_counts = []
        for c in _CSDI_CATS:
            n = _scalar(
                "SELECT COUNT(*) FROM csdi_pois WHERE category=? "
                "AND ST_Distance_Spheroid(ST_Point(lat,lng), ST_Point(?,?)) <= 500",
                [c, lat, lng],
            ) if have_csdi else 0.0
            cat_counts.append(n)
        dist_cbd = _haversine_km(lat, lng, CBD_LAT, CBD_LNG)
        rows.append([pop, comp, *cat_counts, dist_cbd])
    return np.array(rows, dtype=float), list(FEATURE_NAMES)


def find_similar(target: dict, candidates: list[dict], top_n: int = 10) -> dict[str, Any]:
    """Rank `candidates` by spatial-context similarity to `target`.

    Returns candidates sorted by cosine similarity (0..1, higher = more
    alike), each annotated with `similarity`."""
    from sklearn.metrics.pairwise import cosine_similarity
    from sklearn.preprocessing import StandardScaler

    if not candidates:
        return {"method": "find_similar", "results": []}
    all_pts = [target] + candidates
    X, names = build_feature_vectors(all_pts)
    # z-score across the whole set so cosine isn't dominated by population scale
    Xz = StandardScaler().fit_transform(X)
    sims = cosine_similarity(Xz[0:1], Xz[1:])[0]  # vs each candidate
    order = np.argsort(-sims)
    results = []
    for idx in order[:top_n]:
        c = dict(candidates[int(idx)])
        c["similarity"] = round(float(sims[int(idx)]), 4)
        results.append(c)
    return {
        "method": "find_similar",
        "target": target,
        "features": names,
        "results": results,
    }


def cluster_locations(points: list[dict], k: int = 4) -> dict[str, Any]:
    """KMeans-segment points by their spatial-context embedding.

    Returns points annotated with `cluster` (0..k-1) plus per-cluster
    feature centroids (the 'profile' of each segment)."""
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler

    if len(points) < 2:
        return {"method": "cluster", "clusters": [], "points": points}
    k = max(2, min(k, len(points)))
    X, names = build_feature_vectors(points)
    Xz = StandardScaler().fit_transform(X)
    km = KMeans(n_clusters=k, n_init=10, random_state=42).fit(Xz)
    labels = km.labels_.tolist()
    out_points = []
    for p, lab in zip(points, labels, strict=False):
        q = dict(p)
        q["cluster"] = int(lab)
        out_points.append(q)
    # Profile each cluster by its mean RAW feature values (interpretable).
    profiles = []
    for c in range(k):
        mask = np.array(labels) == c
        mean = X[mask].mean(axis=0) if mask.any() else np.zeros(X.shape[1])
        profiles.append({
            "cluster": c,
            "size": int(mask.sum()),
            "profile": {names[i]: round(float(mean[i]), 1) for i in range(len(names))},
        })
    return {"method": "cluster", "k": k, "clusters": profiles, "points": out_points}
