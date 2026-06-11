"""Tests for the R8 spatial optimisation + similarity methods.

Synthetic HK-ish inputs keep these deterministic and offline. They verify
the solvers return well-shaped, sane answers (CBC optimal where expected,
greedy fallback otherwise) and that the decay kernels behave monotonically.
"""

from __future__ import annotations

import os

os.environ.setdefault("DEMO_MODE", "true")

import numpy as np  # noqa: E402

from app.tools import decay, geostatistics, optimization, siteselection  # noqa: E402


# Demand: a coarse cluster of weighted points around Kowloon.
DEMAND = [
    {"lat": 22.31 + 0.01 * (i % 4), "lng": 114.16 + 0.01 * (i // 4), "population": 1000 + 100 * i}
    for i in range(16)
]
# Candidate facility sites: a wider scatter.
CANDIDATES = [
    {"id": f"c{i}", "lat": 22.30 + 0.015 * (i % 5), "lng": 114.15 + 0.015 * (i // 5)}
    for i in range(15)
]


def test_p_median_returns_p_sites_and_accessibility():
    r = optimization.p_median(DEMAND, CANDIDATES, p=3)
    assert r.get("error") is None
    assert len(r["selected"]) == 3
    assert r["weighted_mean_distance_m"] > 0
    # All selected come from the candidate set.
    ids = {c["id"] for c in CANDIDATES}
    assert all(s["id"] in ids for s in r["selected"])


def test_mclp_covers_more_than_zero():
    r = optimization.mclp(DEMAND, CANDIDATES, p=3, radius_m=1500)
    assert r.get("error") is None
    assert len(r["selected"]) == 3
    assert 0 < r["demand_covered_pct"] <= 100


def test_lscp_minimises_facilities_and_covers_all_coverable():
    r = optimization.lscp(DEMAND, CANDIDATES, radius_m=2000)
    assert r.get("error") is None
    assert r["facilities_needed"] >= 1
    # With a generous radius the coverable demand should be ~fully covered.
    assert r["demand_covered_pct"] >= 90


def test_location_allocate_assigns_all_demand():
    r = optimization.location_allocate(DEMAND, CANDIDATES[:3])
    assert r.get("error") is None
    assigned = sum(a["assigned_points"] for a in r["allocation"])
    assert assigned == len(DEMAND)
    assert r["total_demand"] == sum(d["population"] for d in DEMAND)


def test_empty_inputs_are_safe():
    assert optimization.p_median([], CANDIDATES, p=2).get("error") == "empty_input"
    assert optimization.mclp(DEMAND, [], p=2, radius_m=500).get("error") == "empty_input"


def test_decay_kernels_are_monotonic_decreasing():
    d = np.array([0.0, 400.0, 800.0, 1600.0, 3200.0])
    for kernel in ("exponential", "gaussian", "power", "linear"):
        w = decay.decay_weight(d, kernel=kernel, scale=800.0)
        assert w[0] >= w[-1]               # closer ≥ farther
        assert np.all(w >= -1e-9)          # non-negative
        assert w[0] <= 1.0 + 1e-9          # bounded at 1


def test_huff_shares_rows_sum_to_one():
    # 3 demand points, 2 facilities
    dist = np.array([[100.0, 900.0], [500.0, 500.0], [2000.0, 300.0]])
    shares = decay.huff_shares([1.0, 1.0], dist, kernel="exponential", scale=800.0)
    row_sums = shares.sum(axis=1)
    assert np.allclose(row_sums, 1.0, atol=1e-6)
    # Nearer facility gets the larger share for the first demand point.
    assert shares[0, 0] > shares[0, 1]


# --- geostatistics ---

# A clearly clustered field: value rises smoothly with latitude on a 6x6 grid,
# so neighbours are alike → Moran's I should detect positive autocorrelation.
GRID = [
    {"id": f"g{r}_{c}", "lat": 22.25 + 0.01 * r, "lng": 114.12 + 0.01 * c,
     "value": float(r * 10 + c)}
    for r in range(6) for c in range(6)
]


def test_morans_i_detects_clustering():
    r = geostatistics.morans_i(GRID, "value", k=4)
    assert r.get("error") is None
    assert r["pattern"] == "clustered"
    assert r["morans_i"] > r["expected_i"]
    assert "interpretation" in r


def test_local_morans_labels_and_counts():
    r = geostatistics.local_morans(GRID, "value", k=4)
    assert r.get("error") is None
    assert len(r["locations"]) == len(GRID)
    assert sum(r["counts"].values()) == len(GRID)
    # the high-value corner should contain at least one High-High hot spot
    assert r["counts"]["HH"] >= 1


def test_getis_ord_finds_hot_and_cold():
    r = geostatistics.getis_ord_hotspots(GRID, "value", k=4)
    assert r.get("error") is None
    assert r["hot"] >= 1 and r["cold"] >= 1


def test_idw_interpolates_within_range():
    samples = GRID
    grid = [{"id": "q1", "lat": 22.28, "lng": 114.14}]
    r = geostatistics.idw_interpolate(samples, grid, "value")
    assert r.get("error") is None
    v = r["grid"][0]["idw_value"]
    vals = [g["value"] for g in GRID]
    assert min(vals) <= v <= max(vals)


def test_two_step_fca_runs():
    demand = [{"lat": 22.30 + 0.005 * i, "lng": 114.16, "population": 1000} for i in range(10)]
    facilities = [{"lat": 22.31, "lng": 114.16, "capacity": 100},
                  {"lat": 22.33, "lng": 114.16, "capacity": 100}]
    r = geostatistics.two_step_fca(demand, facilities, radius_m=1500)
    assert r.get("error") is None
    assert all("access_2sfca" in d for d in r["demand"])


# --- site selection ---

def test_rank_sites_with_explicit_criteria():
    cands = [
        {"id": "a", "pop": 9000, "comp": 1},
        {"id": "b", "pop": 3000, "comp": 8},
        {"id": "c", "pop": 6000, "comp": 3},
    ]
    crit = [("pop", 0.6, False), ("comp", 0.4, True)]
    r = siteselection.rank_sites(cands, criteria=crit, build_context=False)
    assert r.get("error") is None
    assert r["winner"]["id"] == "a"  # most pop, least competition
    assert r["results"][0]["suitability"] >= r["results"][-1]["suitability"]


def test_best_new_point_picks_highest_net_new():
    demand = [{"lat": 22.30 + 0.004 * i, "lng": 114.16, "population": 1000} for i in range(20)]
    existing = [{"lat": 22.30, "lng": 114.16}]          # covers the low end
    options = [{"id": "near", "lat": 22.305, "lng": 114.16},
               {"id": "far", "lat": 22.37, "lng": 114.16}]  # covers uncovered high end
    r = siteselection.best_new_point(options, existing, demand, radius_m=800)
    assert r.get("error") is None
    assert r["best"]["id"] == "far"


def test_whitespace_finds_gaps():
    demand = [{"lat": 22.30 + 0.01 * i, "lng": 114.16, "population": 1000 + 200 * i}
              for i in range(12)]
    facilities = [{"lat": 22.30, "lng": 114.16}]  # only near the low end
    r = siteselection.whitespace_gaps(demand, facilities, top_n=5, min_distance_m=600)
    assert r.get("error") is None
    assert len(r["gaps"]) >= 1
    assert r["gaps"][0]["distance_to_nearest_m"] >= 600
