"""Visualisation tools — assemble Layer + StorymapSection objects.

This file's job is *composition*: given the outputs of the other tools, build
a StorymapResult that the frontend renders. Cartographic styling lives here.
"""

from __future__ import annotations

import os
from typing import Any

from app.models.analysis import AnalysisRequest
from app.models.network import Network
from app.models.storymap import ChartSpec, Layer, MapLocation, StorymapResult, StorymapSection

# tochka palette — round 5.
# Primary purple is reserved for the user's own network. The 8-colour
# layer ramp (LAYER_PALETTE) supplies distinct hues for derived layers.
PRIMARY = "#4F35F8"
SECONDARY = "#FB3640"
INK = "#0A0903"
PAPER = "#FDFDFD"

# 8-colour layer ramp — index by layer type for visual diversity.
LAYER_PALETTE = [
    "#FAD037",  # 0 yellow
    "#FB3640",  # 1 red
    "#FA37B2",  # 2 pink
    "#C637FA",  # 3 magenta
    "#37B2FA",  # 4 sky blue
    "#37FADD",  # 5 mint
    "#37FA7E",  # 6 green
    "#FA8237",  # 7 orange
]

# Every layer gets its OWN hue (round-10 rule): network purple, competitors
# orange, isochrones mint, anomalies red, cannibalisation pink, opportunity
# yellow→magenta ramp, population grid sky blue, choropleth purple ramp.
PALETTE = {
    "user_network": PRIMARY,               # purple — reserved for the brand + own points
    "competitor":   LAYER_PALETTE[7],      # orange
    "isochrone":    LAYER_PALETTE[5],      # mint — catchments read apart from network
    "hex_low":      "#f6f4ef",
    "hex_high":     INK,
    "anomaly_under": SECONDARY,            # red
    "anomaly_over":  LAYER_PALETTE[6],     # green
    "cannibalisation": LAYER_PALETTE[2],   # pink — no longer collides with anomalies
    "opportunity_low":  LAYER_PALETTE[0],  # yellow — low score
    "opportunity_high": "#C637FA",         # magenta — high score
}

# Basemap style emitted into the storymap payload. Carto Positron is the
# working default. CSDI's vector style URL still 404s; any URL that
# resolves to that dead host is ignored so a stale .env can't poison it.
def _basemap_style() -> str:
    candidate = os.environ.get("NEXT_PUBLIC_BASEMAP_STYLE")
    if candidate and "mapapi.geodata.gov.hk" not in candidate:
        return candidate
    return "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json"


CSDI_VECTOR_STYLE = _basemap_style()


def make_layer(layer_id: str, kind: str, data: dict[str, Any] | None = None,
               paint: dict[str, Any] | None = None) -> Layer:
    """Build a Layer model. Thin wrapper; gives the LLM a single call shape."""
    return Layer(id=layer_id, kind=kind, data=data, paint=paint or {})


def _fc(features: list[dict]) -> dict:
    return {"type": "FeatureCollection", "features": features}


# ---------------------------------------------------------------------------
# Per-tool layer builders — used both for live SSE streaming during analyze
# and for the final storymap composition. Keeps the canvas styling consistent
# whether the user is watching the map fill in or reading the storymap later.
# ---------------------------------------------------------------------------

def build_user_network_layer(network: Network) -> Layer:
    features = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [loc.lng, loc.lat]},
            "properties": {
                "id": loc.id,
                "name": loc.name,
                "capacity": loc.capacity,
                "actual_volume": loc.actual_volume,
            },
        }
        for loc in network.locations
        if loc.lat is not None and loc.lng is not None
    ]
    return make_layer(
        "user-network", "geojson", _fc(features),
        paint={
            "circle-color": PALETTE["user_network"],
            "circle-radius": 7,
            "circle-stroke-color": PAPER,
            "circle-stroke-width": 2,
        },
    )


def build_isochrones_layer(isochrones: list[dict]) -> Layer:
    return make_layer(
        "isochrones", "geojson", _fc(isochrones),
        paint={
            "fill-color": PALETTE["isochrone"],
            "fill-opacity": 0.25,
            "line-color": "#0e9e85",        # darker mint edge for legibility
            "line-width": 1.5,
            "line-opacity": 0.8,
        },
    )


def build_competitors_layer(competitors: list[dict]) -> Layer:
    features = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [c["lng"], c["lat"]]},
            "properties": c,
        }
        for c in competitors
        if c.get("lat") is not None and c.get("lng") is not None
    ]
    return make_layer(
        "competitors", "geojson", _fc(features),
        paint={
            "circle-color": PALETTE["competitor"],
            "circle-radius": 4,
            "circle-opacity": 0.9,
            "circle-stroke-color": PAPER,
            "circle-stroke-width": 1.2,
        },
    )


def build_cannibalisation_layer(pairs: list[dict]) -> Layer:
    """Lines between own-network branches under the cannibalisation threshold."""
    return make_layer(
        "cannibalisation", "geojson", _fc(pairs),
        paint={
            "line-color": PALETTE["cannibalisation"],
            "line-width": 2.5,
            "line-opacity": 0.85,
        },
    )


def build_opportunity_layer(cells: list[dict]) -> Layer:
    """Hex-grid cells coloured by uncovered-demand score (yellow → magenta)."""
    return make_layer(
        "opportunity", "geojson", _fc(cells),
        paint={
            "fill-color": [
                "interpolate", ["linear"], ["get", "score"],
                0.0, PALETTE["opportunity_low"],   # yellow
                0.5, "#FA37B2",                    # pink
                1.0, PALETTE["opportunity_high"],  # magenta
            ],
            "fill-opacity": 0.20,                  # 70 % transparent — polygon rule
            "line-color": PALETTE["opportunity_high"],
            "line-width": 0.5,
            "line-opacity": 0.4,
        },
    )


def build_anomalies_layer(anomalies: list[dict], network: Network) -> Layer:
    """Big red rings on under-performers."""
    under_ids = {a["location_id"] for a in anomalies if a.get("kind") == "under"}
    features = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [loc.lng, loc.lat]},
            "properties": {"id": loc.id, "name": loc.name},
        }
        for loc in network.locations
        if loc.id in under_ids and loc.lat is not None and loc.lng is not None
    ]
    return make_layer(
        "anomalies-under", "geojson", _fc(features),
        paint={
            "circle-color": PALETTE["anomaly_under"],
            "circle-radius": 11,
            "circle-stroke-color": PAPER,
            "circle-stroke-width": 2.5,
            "circle-opacity": 0.9,
        },
    )


async def compose_storymap(
    *,
    network: Network,
    request: AnalysisRequest,
    isochrones: list[dict],
    competitors: list[dict],
    population: dict[str, Any],
    scores: list[dict],
    anomalies: list[dict],
    findings: list[tuple[str, str]] | None = None,
) -> StorymapResult:
    """Assemble the 5-section storymap from tool outputs.

    Uses the same per-tool layer builders the orchestrator emits live during
    /analyze, so the storymap and the live canvas show identical geometries.
    """
    layer_user = build_user_network_layer(network)
    layer_iso = build_isochrones_layer(isochrones)
    layer_comp = build_competitors_layer(competitors)
    layer_anom = build_anomalies_layer(anomalies, network)

    # Centre/zoom — derive from network bbox.
    user_features = layer_user.data["features"] if layer_user.data else []
    lats = [f["geometry"]["coordinates"][1] for f in user_features] or [22.31]
    lngs = [f["geometry"]["coordinates"][0] for f in user_features] or [114.17]
    centre = (sum(lngs) / len(lngs), sum(lats) / len(lats))
    map_loc = MapLocation(center=centre, zoom=12)

    total_pop = population.get("total_population", 0)
    n_loc = len(network.locations)
    n_comp = len(competitors)
    charts = _build_section_charts(scores, competitors)

    sections = [
        StorymapSection(
            id="network-glance",
            title="Your network at a glance",
            description=(
                f"You operate **{n_loc} locations** across Hong Kong. "
                f"This is the map of where they are today."
            ),
            location=map_loc,
            on_enter=[{"layer": "user-network", "opacity": 1.0}],
            kpis={"Locations": str(n_loc), "Districts": str(len({loc.raw_fields.get("district", "?") for loc in network.locations}))},
            charts=charts.get("network-glance", []),
        ),
        StorymapSection(
            id="who-you-reach",
            title="Who you reach today",
            description=(
                f"Within a 10-minute walk, your network is in front of "
                f"**{total_pop:,} residents**. The {n_comp} nearby competitor branches share "
                f"some of that catchment."
            ),
            location=map_loc,
            on_enter=[{"layer": "isochrones", "opacity": 0.6},
                      {"layer": "competitors", "opacity": 1.0}],
            kpis={"Population in catchment": f"{total_pop:,}", "Competitors nearby": str(n_comp)},
            charts=charts.get("who-you-reach", []),
        ),
        StorymapSection(
            id="whats-working",
            title="What's working, what's not",
            description=(
                f"**{len([a for a in anomalies if a['kind'] == 'under'])} locations** are "
                f"underperforming relative to the demand around them. Lowest-performing flagged in red."
            ),
            location=map_loc,
            on_enter=[{"layer": "anomalies-under", "opacity": 1.0}],
            callouts=[a.get("rationale", "") for a in anomalies[:3]],
            charts=charts.get("whats-working", []),
        ),
        StorymapSection(
            id="opportunity",
            title="Where the opportunity is",
            description=(
                "The hex map below ranks every 250m cell in Hong Kong by uncovered demand. "
                "The top five candidate areas are highlighted."
            ),
            location=map_loc,
            on_enter=[{"layer": "user-network", "opacity": 0.4}],
            charts=charts.get("opportunity", []),
        ),
        StorymapSection(
            id="next-steps",
            title="Next steps",
            description=(
                "Three concrete actions: open in the top-ranked gap, restaff the bottom three "
                "branches, evaluate one candidate for closure / merge."
            ),
            location=map_loc,
        ),
    ]

    # Dynamic-methodology findings (whitespace, coverage optimisation, LISA,
    # look-alikes, …): each specialised analysis becomes its OWN report
    # section before next-steps, so the second half of every report shows
    # the results of THAT methodology instead of one stock story.
    if findings:
        for i, (f_title, f_text) in enumerate(findings[:6]):
            sections.insert(4 + i, StorymapSection(
                id=f"finding-{i}",
                title=f_title,
                description=f_text,
                location=map_loc,
            ))

    return StorymapResult(
        id="pending",  # filled in by the orchestrator
        network_id=network.id,
        style_url=CSDI_VECTOR_STYLE,
        layers=[layer_user, layer_iso, layer_comp, layer_anom],
        sections=sections,
        summary=(
            f"tochka analysed {n_loc} locations using a {request.demand_model.value} demand model "
            f"and the {', '.join(a.value for a in request.archetypes)} archetype(s)."
        ),
    )


def _build_section_charts(scores: list[dict], competitors: list[dict]) -> dict[str, list[ChartSpec]]:
    """Deterministic per-section chart data from the Huff/competitor outputs.

    Chart-selection follows SKILL_report.md: bar for entity comparison,
    scatter for actual-vs-expected, rank for ordered shortlists, donut for
    share-of-whole. Every spec carries its data source. Defensive against
    missing keys — a section simply gets fewer charts."""
    out: dict[str, list[ChartSpec]] = {}

    def _num(row: dict, key: str) -> float | None:
        v = row.get(key)
        try:
            return float(v) if v is not None else None
        except (TypeError, ValueError):
            return None

    rows = [r for r in (scores or []) if r.get("name")]

    # who-you-reach: catchment population per branch (top 8, sorted desc).
    pops = [(r["name"], _num(r, "catchment_pop")) for r in rows]
    pops = [(n, v) for n, v in pops if v is not None and v > 0]
    if len(pops) >= 3:
        pops.sort(key=lambda t: t[1], reverse=True)
        out.setdefault("who-you-reach", []).append(ChartSpec(
            kind="bar",
            title="Where your catchments hold the most residents",
            unit="residents",
            data=[{"label": n, "value": round(v)} for n, v in pops[:8]],
            source="Kontur population · 10-min walking catchments",
        ))

    # whats-working: actual vs expected scatter + lowest Huff shares rank.
    sc = [(r["name"], _num(r, "expected_demand"), _num(r, "actual_volume")) for r in rows]
    sc = [(n, x, y) for n, x, y in sc if x is not None and y is not None]
    if len(sc) >= 4:
        out.setdefault("whats-working", []).append(ChartSpec(
            kind="scatter",
            title="Who beats their context — actual vs expected demand",
            subtitle="Above the diagonal = over-performing",
            data=[{"label": n, "value": round(x), "value2": round(y)} for n, x, y in sc],
            source="Huff model · network MIS",
        ))
    shares = [(r["name"], _num(r, "share")) for r in rows]
    shares = [(n, v) for n, v in shares if v is not None]
    if len(shares) >= 3:
        shares.sort(key=lambda t: t[1])
        out.setdefault("whats-working", []).append(ChartSpec(
            kind="rank",
            title="Weakest market shares need attention first",
            unit="%",
            data=[{"label": n, "value": round(v * 100, 1)} for n, v in shares[:5]],
            source="Huff share model",
        ))

    # who-you-reach extra: competitor share of brands (donut, top 5 + other).
    brands: dict[str, int] = {}
    for c in competitors or []:
        b = (c.get("brand") or "other").strip() or "other"
        brands[b] = brands.get(b, 0) + 1
    if sum(brands.values()) >= 5:
        top = sorted(brands.items(), key=lambda t: t[1], reverse=True)
        head, tail = top[:5], top[5:]
        data = [{"label": b, "value": v} for b, v in head]
        if tail:
            data.append({"label": "other", "value": sum(v for _, v in tail)})
        out.setdefault("who-you-reach", []).append(ChartSpec(
            kind="donut",
            title="Who you compete with nearby",
            unit="branches",
            data=data,
            source="OpenStreetMap competitor banks",
        ))

    # opportunity: most contested catchments (bar of competitor counts).
    comps = [(r["name"], _num(r, "comp_count")) for r in rows]
    comps = [(n, v) for n, v in comps if v is not None]
    if len(comps) >= 3:
        comps.sort(key=lambda t: t[1], reverse=True)
        out.setdefault("opportunity", []).append(ChartSpec(
            kind="bar",
            title="The most contested catchments",
            unit="competitors within 500 m",
            data=[{"label": n, "value": round(v)} for n, v in comps[:8]],
            source="OpenStreetMap · CSDI",
        ))

    # network-glance: recorded volume by branch when available.
    vols = [(r["name"], _num(r, "actual_volume")) for r in rows]
    vols = [(n, v) for n, v in vols if v is not None and v > 0]
    if len(vols) >= 3:
        vols.sort(key=lambda t: t[1], reverse=True)
        out.setdefault("network-glance", []).append(ChartSpec(
            kind="bar",
            title="Your largest branches by recorded volume",
            unit="visits",
            data=[{"label": n, "value": round(v)} for n, v in vols[:8]],
            source="Uploaded network MIS",
        ))

    return out
