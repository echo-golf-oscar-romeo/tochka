"""Visualisation tools — assemble Layer + StorymapSection objects.

This file's job is *composition*: given the outputs of the other tools, build
a StorymapResult that the frontend renders. Cartographic styling lives here.
"""

from __future__ import annotations

import os
from typing import Any

from app.models.analysis import AnalysisRequest
from app.models.network import Network
from app.models.storymap import Layer, MapLocation, StorymapResult, StorymapSection

# Aino-inspired palette. Soft greys for basemap context, two strong accents for data.
PALETTE = {
    "user_network": "#0f5ea8",     # deep blue — your locations
    "competitor":    "#e07a5f",    # terracotta — competitors
    "isochrone":     "#0f5ea8",    # match user network, low opacity
    "hex_low":       "#f6f4ef",    # near-paper
    "hex_high":      "#1a1a1a",    # near-black for density peaks
    "anomaly_under": "#c44536",    # warning red
    "anomaly_over":  "#3a7d44",    # validating green
}

# Basemap style emitted into the storymap payload. Carto Positron is the
# working default; CSDI's vector style URL currently returns 404.
CSDI_VECTOR_STYLE = (
    os.environ.get("NEXT_PUBLIC_BASEMAP_STYLE")
    or os.environ.get("NEXT_PUBLIC_CSDI_VECTOR_STYLE")
    or "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json"
)


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
            "circle-stroke-color": "#ffffff",
            "circle-stroke-width": 1.5,
        },
    )


def build_isochrones_layer(isochrones: list[dict]) -> Layer:
    return make_layer(
        "isochrones", "geojson", _fc(isochrones),
        paint={
            "fill-color": PALETTE["isochrone"],
            "fill-opacity": 0.13,
            "line-color": PALETTE["isochrone"],
            "line-width": 1,
            "line-opacity": 0.6,
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
            "circle-opacity": 0.85,
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
            "circle-stroke-color": "#ffffff",
            "circle-stroke-width": 2,
            "circle-opacity": 0.85,
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
            # TODO: add opportunity hex layer in a follow-up tool call once `h3_aggregate`
            # is wired to real population data.
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

    return StorymapResult(
        id="pending",  # filled in by the orchestrator
        network_id=network.id,
        style_url=CSDI_VECTOR_STYLE,
        layers=[layer_user, layer_iso, layer_comp, layer_anom],
        sections=sections,
        summary=(
            f"Tochka analysed {n_loc} locations using a {request.demand_model.value} demand model "
            f"and the {', '.join(a.value for a in request.archetypes)} archetype(s)."
        ),
    )
