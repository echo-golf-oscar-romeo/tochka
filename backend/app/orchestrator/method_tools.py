"""Chat router for the advanced spatial-analysis methods.

Sits alongside chat_tools.py: when the deterministic OSM/isochrone/buffer/H3
classifier finds nothing, we try to match a *method* intent — coverage
optimisation, best-next-site, whitespace, hot-spots (Moran/LISA/Gi*),
find-similar, clustering, drivers regression, accessibility (2SFCA) — and run
the matching function from app/tools/*, returning a map layer + the method's
plain-English interpretation.

Inputs (demand cells, candidate sites, network points) are assembled from the
loaded DuckDB tables (kontur_pop_hex = demand + candidate centroids;
_user_locations / network = existing facilities).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

import h3

from app.clients.ddb import (
    ensure_csdi_pois_loaded,
    ensure_kontur_loaded,
    ensure_osm_loaded,
    get_duckdb,
)
from app.models.network import Network
from app.tools import geostatistics, optimization, regression, similarity, siteselection

log = logging.getLogger(__name__)

_DEMAND_CAP = 400
_CANDIDATE_CAP = 120

# Map paint helpers ----------------------------------------------------------
PAPER = "#FDFDFD"
ACCENT = "#4F35F8"
CLUSTER_COLOURS = ["#4F35F8", "#FB3640", "#FA8237", "#37B2FA", "#37FA7E", "#C637FA", "#FAD037", "#FA37B2"]
LISA_COLOURS = {"HH": "#FB3640", "LL": "#37B2FA", "HL": "#FA8237", "LH": "#C637FA", "ns": "#9a9890"}

# Single-hue sequential ramps (light tint → project colour → dark shade).
# Project rule: graded layers use ONE hue from the palette, never rainbows.
RAMP = {
    "purple": ["#EFECFF", "#7560fb", "#321bb8"],
    "red":    ["#FFE6E8", "#FB3640", "#8C1118"],
    "pink":   ["#FFE3F3", "#FA37B2", "#8F1B64"],
    "yellow": ["#FEF6D8", "#FAD037", "#8F7400"],
    "green":  ["#DEFCEB", "#37FA7E", "#0E8C44"],
    "blue":   ["#E5F4FF", "#37B2FA", "#155C8F"],
    "orange": ["#FFEEDF", "#FA8237", "#8F4513"],
}


def ramp_expr(prop: str, vmin: float, vmax: float, hue: str) -> list:
    """MapLibre interpolate expression: single-hue light→dark over a value."""
    lo, mid, hi = RAMP[hue]
    if vmax <= vmin:
        vmax = vmin + 1.0
    vmid = vmin + (vmax - vmin) / 2
    return ["interpolate", ["linear"], ["get", prop], vmin, lo, vmid, mid, vmax, hi]


# ---------------------------------------------------------------------------
# Intent classification
# ---------------------------------------------------------------------------

@dataclass
class MethodIntent:
    kind: str
    params: dict[str, Any]


_RE = {
    "optimize_coverage": re.compile(
        r"\b(optimi[sz]e\s+coverage|coverage\s+optimi|p-?median|location[- ]allocation|"
        r"cover\s+(all\s+)?(the\s+)?demand|maximi[sz]e\s+coverage|mclp|lscp|set\s+covering|"
        r"minimi[sz]e\s+.*distance|where\s+(should|to)\s+(i\s+)?(put|place|open)\s+\d+)\b",
        re.IGNORECASE),
    "best_new_point": re.compile(
        r"\b(best\s+(new\s+|next\s+)?(site|location|place|branch|spot|point)|"
        r"where\s+(should|to)\s+(i\s+)?open\s+(next|a\s+new)|best\s+place\s+to\s+open|"
        r"single\s+best|which\s+(site|location)\s+should)\b", re.IGNORECASE),
    "whitespace": re.compile(
        r"\b(white\s?space|gaps?|under-?served|uncovered\s+(demand|areas?)|coverage\s+gaps?|"
        r"where\s+(am\s+i|are\s+we)\s+missing)\b", re.IGNORECASE),
    "hexgrid_lisa": re.compile(
        r"\b(?:hex|h3|grid)\b[^.?!]*\b(?:lisa|moran|hot|cold)|"
        r"\b(?:lisa|moran|hot\s?spots?|cold\s?spots?)\b[^.?!]*\b(?:hex|h3|grid)\b",
        re.IGNORECASE),
    "hotspots": re.compile(
        r"\b(hot\s?spots?|cold\s?spots?|moran|lisa|getis|gi\*|spatial\s+autocorrelation|"
        r"spatially\s+clustered|clusters?\s+of\s+(high|low)|where\s+do\s+.*cluster)\b",
        re.IGNORECASE),
    "find_similar": re.compile(
        r"\b(similar\s+(locations?|sites?|areas?|branches?)|locations?\s+like|"
        r"look-?alike|comparable\s+(sites?|locations?)|find\s+.*\bsimilar\b|"
        r"(areas?|locations?|sites?|places?)\s+(that\s+)?look\s+like|look\s+like\s+my)\b",
        re.IGNORECASE),
    "cluster": re.compile(
        r"\b(cluster|segment|typolog|group\s+(my\s+)?(branches|network|locations|sites))\b",
        re.IGNORECASE),
    "drivers": re.compile(
        r"\b(what\s+drives|drivers?\s+of|what\s+(makes|factors)|which\s+factors|"
        r"explain\s+(the\s+)?(volume|performance|success)|run\s+a\s+regression|"
        r"what\s+predicts)\b", re.IGNORECASE),
    "accessibility": re.compile(
        r"\b(accessibilit|2sfca|two[- ]step|floating\s+catchment|access[-\s]?poor)\b",
        re.IGNORECASE),
}


def classify_method(message: str) -> MethodIntent | None:
    msg = message.strip()
    # Most specific first. find_similar precedes best_new_point because
    # phrases like "areas that look like my best branch" contain "best
    # branch" and would otherwise be stolen by the best-new-point regex.
    for kind in ("find_similar", "best_new_point", "whitespace", "optimize_coverage",
                 "hexgrid_lisa", "hotspots", "cluster", "drivers", "accessibility"):
        if _RE[kind].search(msg):
            params: dict[str, Any] = {}
            n = re.search(r"\b(\d{1,3})\b", msg)
            if n:
                params["count"] = int(n.group(1))
            rad = re.search(r"(\d{2,5})\s*(m|metre|meter)", msg, re.IGNORECASE)
            if rad:
                params["radius_m"] = float(rad.group(1))
            km = re.search(r"(\d+(?:\.\d+)?)\s*km", msg, re.IGNORECASE)
            if km:
                params["radius_m"] = float(km.group(1)) * 1000
            # find_similar: capture the target name after "like"/"similar to"
            m = re.search(r"(?:like|similar\s+to)\s+([A-Za-z][\w\s']{1,40})", msg, re.IGNORECASE)
            if m:
                params["target_name"] = m.group(1).strip().rstrip("?.!,")
            return MethodIntent(kind, params)
    return None


# ---------------------------------------------------------------------------
# Input assembly from DuckDB
# ---------------------------------------------------------------------------

def _demand_cells(cap: int = _DEMAND_CAP) -> list[dict]:
    conn = get_duckdb()
    ensure_kontur_loaded(conn)
    try:
        rows = conn.execute(
            "SELECT lat, lng, population FROM kontur_pop_hex "
            "WHERE population > 0 ORDER BY population DESC LIMIT ?", [cap]
        ).fetchall()
    except Exception:
        return []
    return [{"lat": r[0], "lng": r[1], "population": float(r[2])} for r in rows]


def _candidate_cells(cap: int = _CANDIDATE_CAP) -> list[dict]:
    """Candidate facility sites = a spatially-spread sample of populated
    Kontur cell centroids (places where people actually are)."""
    cells = _demand_cells(cap=_DEMAND_CAP)
    if len(cells) <= cap:
        return [{"id": f"cand{i}", **c} for i, c in enumerate(cells)]
    step = max(1, len(cells) // cap)
    return [{"id": f"cand{i}", **c} for i, c in enumerate(cells[::step][:cap])]


def _network_points(network: Network) -> list[dict]:
    return [
        {"id": loc.id, "name": loc.name, "lat": float(loc.lat), "lng": float(loc.lng),
         "actual_volume": loc.actual_volume, "capacity": loc.capacity}
        for loc in network.locations if loc.lat is not None and loc.lng is not None
    ]


def _point_features(rows: list[dict], colour_key: str | None = None,
                    colour_map=None, fixed_colour: str | None = None) -> list[dict]:
    feats = []
    for r in rows:
        if r.get("lat") is None or r.get("lng") is None:
            continue
        props = {k: v for k, v in r.items() if k not in ("lat", "lng")}
        feats.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [r["lng"], r["lat"]]},
            "properties": props,
        })
    return feats


def _circle_layer(layer_id: str, label: str, rows: list[dict], paint: dict) -> dict:
    return {
        "id": layer_id, "kind": "geojson",
        "data": {"type": "FeatureCollection", "features": _point_features(rows)},
        "paint": paint, "label": label,
    }


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

async def run_optimize_coverage(network: Network, params: dict) -> dict[str, Any]:
    demand = _demand_cells()
    if not demand:
        return _err("No Kontur demand data loaded — can't optimise coverage.")
    # P is the number of NEW sites to open — a strategic handful, never the
    # size of the network. (A 105-branch upload once produced 105 "optimal
    # sites" because the default was max(3, len(network)).) Clamp 1..10.
    p = max(1, min(int(params.get("count") or 5), 10))
    radius = float(params.get("radius_m") or 800.0)
    # Candidates come from the WHITESPACE first: high-demand cells far from
    # the existing network. Optimising over generic populated cells would
    # happily "open" next to branches that already cover the demand.
    existing = _network_points(network)
    gaps = siteselection.whitespace_gaps(demand, existing, top_n=40,
                                         min_distance_m=600.0).get("gaps", [])
    candidates = [{"id": f"gap{i}", **g} for i, g in enumerate(gaps)]
    if len(candidates) < p:
        candidates = _candidate_cells(cap=60)
    res = optimization.mclp(demand, candidates, p=p, radius_m=radius)
    if res.get("error"):
        return _err("Coverage optimisation had no candidates to work with.")
    selected = res["selected"]
    layer = {
        "id": f"mclp-{p}-{int(radius)}m", "kind": "geojson",
        "data": {"type": "FeatureCollection", "features": _point_features(
            [{**s, "rank": i + 1} for i, s in enumerate(selected)])},
        # Pink — instantly distinct from the purple network + orange competitors.
        "paint": {"circle-color": "#FA37B2", "circle-radius": 9,
                  "circle-stroke-color": PAPER, "circle-stroke-width": 2.5},
        "label": f"MCLP · {len(selected)} optimal new sites ({int(radius)}m)",
    }
    answer = (
        f"Maximal-coverage optimisation (MCLP) over the white-space candidates: "
        f"{len(selected)} new sites with a {int(radius)}m catchment cover "
        f"{res['demand_covered_pct']}% of the uncovered modelled demand "
        f"({res['demand_covered_abs']:,} of {res['demand_total']:,} people). "
        f"The pink points are the chosen sites."
    )
    return _ok(answer, layer, rows=selected, columns=["lat", "lng", "population"],
               provider="mclp")


async def run_best_new_point(network: Network, params: dict) -> dict[str, Any]:
    demand = _demand_cells()
    existing = _network_points(network)
    options = _candidate_cells(cap=60)
    if not demand or not options:
        return _err("No demand/candidate data to evaluate new sites.")
    radius = float(params.get("radius_m") or 800.0)
    res = siteselection.best_new_point(options, existing, demand, radius_m=radius)
    if res.get("error"):
        return _err("Couldn't evaluate candidate sites.")
    ranked = res["ranked"][:30]
    feats = _point_features([{**r, "rank": i + 1} for i, r in enumerate(ranked)])
    layer = {
        "id": f"best-new-{int(radius)}m", "kind": "geojson",
        "data": {"type": "FeatureCollection", "features": feats},
        "paint": {
            # Single-hue green: darker = more net-new demand captured.
            "circle-color": ramp_expr("new_demand_captured", 0,
                                      max((r["new_demand_captured"] for r in ranked), default=1),
                                      "green"),
            "circle-radius": ["interpolate", ["linear"], ["get", "rank"], 1, 11, 30, 4],
            "circle-stroke-color": PAPER, "circle-stroke-width": 2,
        },
        "label": f"Best new site · marginal coverage ({int(radius)}m)",
    }
    return _ok(res["interpretation"], layer, rows=ranked[:20],
               columns=["lat", "lng", "new_demand_captured", "total_demand_in_catchment"],
               provider="best_new_point")


async def run_whitespace(network: Network, params: dict) -> dict[str, Any]:
    demand = _demand_cells()
    facilities = _network_points(network)
    res = siteselection.whitespace_gaps(demand, facilities, top_n=30,
                                        min_distance_m=float(params.get("radius_m") or 600.0))
    if res.get("error"):
        return _err("No demand data to find white space.")
    gaps = res["gaps"]
    feats = _point_features(gaps)
    layer = {
        "id": "whitespace-gaps", "kind": "geojson",
        "data": {"type": "FeatureCollection", "features": feats},
        "paint": {
            # Single-hue red: darker = bigger gap.
            "circle-color": ramp_expr("gap_score", 0.0, 1.0, "red"),
            "circle-radius": 8, "circle-stroke-color": PAPER, "circle-stroke-width": 1.5,
            "circle-opacity": 0.9,
        },
        "label": f"White-space gaps ({len(gaps)})",
    }
    return _ok(res["interpretation"], layer, rows=gaps[:20],
               columns=["lat", "lng", "population", "distance_to_nearest_m", "gap_score"],
               provider="whitespace")


async def run_hotspots(network: Network, params: dict) -> dict[str, Any]:
    pts = _network_points(network)
    value_key = "actual_volume" if any(p.get("actual_volume") is not None for p in pts) else None
    if value_key is None:
        return _err("Hot-spot analysis needs a performance value (e.g. actual_volume) "
                    "on your locations. Upload a CSV with a volume column.")
    res = geostatistics.local_morans(pts, value_key)
    if res.get("error"):
        return _err(f"LISA needs at least 6 locations with {value_key}.")
    locs = res["locations"]
    feats = _point_features(locs)
    # colour by cluster category via a match expression
    match_expr: list[Any] = ["match", ["get", "cluster"]]
    for cat, col in LISA_COLOURS.items():
        match_expr += [cat, col]
    match_expr += ["#9a9890"]
    layer = {
        "id": "lisa-hotspots", "kind": "geojson",
        "data": {"type": "FeatureCollection", "features": feats},
        "paint": {"circle-color": match_expr, "circle-radius": 8,
                  "circle-stroke-color": PAPER, "circle-stroke-width": 2},
        "label": f"LISA hot/cold spots · {value_key}",
    }
    glob = geostatistics.morans_i(pts, value_key)
    answer = res["interpretation"]
    if not glob.get("error"):
        answer = glob["interpretation"] + " " + answer
    return _ok(answer, layer, rows=locs[:20],
               columns=["name", "cluster", "lisa_i", "lisa_p"], provider="lisa")


async def run_hexgrid_lisa(network: Network, params: dict) -> dict[str, Any]:
    """LISA on BANK-BRANCH COUNTS per H3 r8 cell across Hong Kong.

    Frame = the inhabited Kontur cells (so empty harbour cells don't dilute
    the statistic); value = competitor banks (+ the user's own branches) in
    each cell. Hot spots (HH) red, cold spots (LL) blue, outliers orange/
    purple, not-significant gray — rendered as FILLED hexagons."""
    import h3 as _h3

    conn = get_duckdb()
    ensure_kontur_loaded(conn)
    ensure_osm_loaded(conn)
    try:
        cells = conn.execute(
            "SELECT h3, lat, lng, population FROM kontur_pop_hex "
            "WHERE population > 0 ORDER BY population DESC LIMIT 800"
        ).fetchall()
        banks = conn.execute(
            "SELECT lat, lng FROM osm_pois WHERE type='bank' AND lat IS NOT NULL"
        ).fetchall()
    except Exception as e:  # noqa: BLE001
        return _err(f"Hex-grid LISA needs the Kontur + OSM tables: {e}")
    if len(cells) < 20:
        return _err("Not enough populated cells for a hex-grid LISA.")

    counts: dict[str, int] = {c[0]: 0 for c in cells}
    for lat, lng in banks:
        cell = _h3.latlng_to_cell(float(lat), float(lng), 8)
        if cell in counts:
            counts[cell] += 1
    for loc in network.locations:
        if loc.lat is None or loc.lng is None:
            continue
        cell = _h3.latlng_to_cell(loc.lat, loc.lng, 8)
        if cell in counts:
            counts[cell] += 1

    pts = [{"h3": c[0], "lat": c[1], "lng": c[2], "branches": counts[c[0]]} for c in cells]
    res = geostatistics.local_morans(pts, "branches", k=6)
    if res.get("error"):
        return _err("LISA failed on the hex grid.")

    features = []
    for p in res["locations"]:
        try:
            boundary = _h3.cell_to_boundary(p["h3"])
            ring = [[lng_, lat_] for (lat_, lng_) in boundary]
            if ring and ring[0] != ring[-1]:
                ring.append(ring[0])
        except Exception:  # noqa: BLE001
            continue
        features.append({
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [ring]},
            "properties": {"h3": p["h3"], "branches": p["branches"],
                           "cluster": p["cluster"], "lisa_p": p["lisa_p"]},
        })
    match_expr: list[Any] = ["match", ["get", "cluster"]]
    for cat, col in LISA_COLOURS.items():
        match_expr += [cat, col]
    match_expr += ["#9a9890"]
    layer = {
        "id": "hexgrid-lisa-branches", "kind": "geojson",
        "data": {"type": "FeatureCollection", "features": features},
        "paint": {
            "fill-color": match_expr,
            "fill-opacity": ["case", ["==", ["get", "cluster"], "ns"], 0.10, 0.55],
            "line-color": "#FDFDFD", "line-width": 0.4, "line-opacity": 0.5,
        },
        "label": "LISA · branch density hot/cold spots (H3 r8)",
    }
    c = res["counts"]
    answer = (
        f"LISA on branch counts per H3 r8 cell ({len(pts)} inhabited cells): "
        f"{c['HH']} hot-spot cells (red — banking clusters like Central/TST), "
        f"{c['LL']} cold spots (blue — populated but bank-sparse), "
        f"{c['HL'] + c['LH']} spatial outliers. Cold spots adjacent to hot ones "
        "are natural expansion candidates."
    )
    return _ok(answer, layer,
               rows=[{"h3": p["h3"], "branches": p["branches"], "cluster": p["cluster"]}
                     for p in res["locations"] if p["cluster"] != "ns"][:30],
               columns=["h3", "branches", "cluster"], provider="hexgrid_lisa")


async def run_find_similar(network: Network, params: dict) -> dict[str, Any]:
    pts = _network_points(network)
    if len(pts) < 2:
        return _err("Need at least two locations to compare similarity.")
    target_name = params.get("target_name", "")
    target = None
    if target_name:
        target = next((p for p in pts if target_name.lower() in (p.get("name") or "").lower()), None)
    if target is None:
        # default: the top performer (or first)
        with_vol = [p for p in pts if p.get("actual_volume") is not None]
        target = max(with_vol, key=lambda p: p["actual_volume"]) if with_vol else pts[0]
    candidates = [p for p in pts if p["id"] != target["id"]]
    res = similarity.find_similar(target, candidates, top_n=len(candidates))
    results = res["results"]
    feats = _point_features(results)
    layer = {
        "id": "find-similar", "kind": "geojson",
        "data": {"type": "FeatureCollection", "features": feats},
        "paint": {
            # Single-hue purple: darker = more similar to the target.
            "circle-color": ramp_expr("similarity", -0.2, 1.0, "purple"),
            "circle-radius": 8, "circle-stroke-color": PAPER, "circle-stroke-width": 2,
        },
        "label": f"Similarity to {target.get('name') or 'target'}",
    }
    top = results[0] if results else None
    answer = (
        f"Ranked locations by spatial-context similarity to "
        f"**{target.get('name') or 'the target'}** (population, competition, and "
        f"surrounding POI mix). "
        + (f"Most alike: **{top.get('name')}** (cosine {top['similarity']:.2f}). "
           if top else "")
        + "Brighter purple = more similar — good look-alike expansion targets."
    )
    return _ok(answer, layer, rows=results[:20], columns=["name", "similarity"],
               provider="find_similar")


async def run_cluster(network: Network, params: dict) -> dict[str, Any]:
    pts = _network_points(network)
    if len(pts) < 3:
        return _err("Need at least three locations to cluster.")
    k = int(params.get("count") or 3)
    res = similarity.cluster_locations(pts, k=k)
    locs = res["points"]
    feats = _point_features(locs)
    match_expr: list[Any] = ["match", ["get", "cluster"]]
    for i in range(res["k"]):
        match_expr += [i, CLUSTER_COLOURS[i % len(CLUSTER_COLOURS)]]
    match_expr += ["#9a9890"]
    layer = {
        "id": f"cluster-k{res['k']}", "kind": "geojson",
        "data": {"type": "FeatureCollection", "features": feats},
        "paint": {"circle-color": match_expr, "circle-radius": 8,
                  "circle-stroke-color": PAPER, "circle-stroke-width": 2},
        "label": f"Network segments (k={res['k']})",
    }
    sizes = ", ".join(f"segment {c['cluster']}: {c['size']}" for c in res["clusters"])
    answer = (
        f"Segmented your {len(pts)} locations into {res['k']} types by spatial context "
        f"({sizes}). Each colour is a location 'type' sharing similar surrounding "
        "population, competition and POI mix — useful for tailoring strategy per segment."
    )
    return _ok(answer, layer, rows=[{"name": p.get("name"), "cluster": p["cluster"]} for p in locs[:20]],
               columns=["name", "cluster"], provider="cluster")


async def run_drivers(network: Network, params: dict) -> dict[str, Any]:
    pts = _network_points(network)
    res = regression.fit_drivers(pts, target_key="actual_volume")
    if res.get("error"):
        return _err(res.get("note") or "Not enough data with a volume column to fit drivers.")
    locs = res["locations"]
    feats = _point_features(locs)
    layer = {
        "id": "perf-residuals", "kind": "geojson",
        "data": {"type": "FeatureCollection", "features": feats},
        "paint": {
            "circle-color": ["match", ["get", "performance"], "over", "#37FA7E", "under", "#FB3640", "#9a9890"],
            "circle-radius": 8, "circle-stroke-color": PAPER, "circle-stroke-width": 2,
        },
        "label": "Performance vs. context (green=over, red=under)",
    }
    top = res["drivers"][:3]
    driver_txt = "; ".join(f"{d['feature']} ({'+' if d['beta'] >= 0 else ''}{d['beta']})" for d in top)
    answer = (
        f"Fitted a model of actual_volume on spatial context (R²={res['r2']}, n={res['n']}, "
        f"reliability: {res['reliability']}). Strongest drivers: {driver_txt}. "
        f"{res['reliability_note']} Green points over-perform their context, red under-perform."
    )
    return _ok(answer, layer, rows=res["drivers"], columns=["feature", "beta"], provider="regression")


async def run_accessibility(network: Network, params: dict) -> dict[str, Any]:
    demand = _demand_cells()
    facilities = _network_points(network)
    if not demand or not facilities:
        return _err("Need demand cells + facilities for accessibility.")
    radius = float(params.get("radius_m") or 1000.0)
    res = geostatistics.two_step_fca(demand, facilities, radius_m=radius)
    if res.get("error"):
        return _err("Accessibility computation failed.")
    cells = res["demand"]
    feats = _point_features(cells)
    layer = {
        "id": f"access-2sfca-{int(radius)}m", "kind": "geojson",
        "data": {"type": "FeatureCollection", "features": feats},
        "paint": {
            # Single-hue green: darker = better served. Pale cells are the
            # access-poor neighbourhoods the narrative calls out.
            "circle-color": ramp_expr("access_2sfca", 0.0, 0.05, "green"),
            "circle-radius": 5, "circle-opacity": 0.8,
        },
        "label": f"2SFCA accessibility ({int(radius)}m)",
    }
    return _ok(res["interpretation"], layer, rows=cells[:20],
               columns=["lat", "lng", "population", "access_2sfca"], provider="two_step_fca")


# ---------------------------------------------------------------------------
# Result helpers + entry point
# ---------------------------------------------------------------------------

def _ok(answer: str, layer: dict, rows=None, columns=None, provider="method") -> dict[str, Any]:
    return {"answer": answer, "layer": layer, "rows": rows or [],
            "columns": columns or [], "sql": None, "provider": provider}


def _err(msg: str) -> dict[str, Any]:
    return {"answer": msg, "layer": None, "rows": [], "columns": [], "sql": None,
            "error": "method_error"}


_HANDLERS = {
    "optimize_coverage": run_optimize_coverage,
    "best_new_point": run_best_new_point,
    "whitespace": run_whitespace,
    "hexgrid_lisa": run_hexgrid_lisa,
    "hotspots": run_hotspots,
    "find_similar": run_find_similar,
    "cluster": run_cluster,
    "drivers": run_drivers,
    "accessibility": run_accessibility,
}


async def maybe_run_method(*, network: Network, message: str) -> dict[str, Any] | None:
    """Return a chat-response dict if `message` matches an advanced-method
    intent, else None. Loads the context tables first."""
    intent = classify_method(message)
    if intent is None:
        return None
    log.info("method intent: %s params=%s", intent.kind, intent.params)
    try:
        conn = get_duckdb()
        ensure_kontur_loaded(conn)
        ensure_osm_loaded(conn)
        ensure_csdi_pois_loaded(conn)
    except Exception as e:  # noqa: BLE001
        log.warning("method table prep failed: %s", e)
    handler = _HANDLERS.get(intent.kind)
    if handler is None:
        return None
    return await handler(network, intent.params)
