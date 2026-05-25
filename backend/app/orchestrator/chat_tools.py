"""Chat tool router — non-SQL chat intents.

The main chat path is the SQL agent in `geosql.py`. But some user prompts
clearly want one of three deterministic tools instead:

  1. OSM-fetch        — "find all <category> in hong kong"
  2. Mapbox isochrone — "show 15-min walking isochrone for HSBC banks"
  3. H3 aggregate     — "aggregate the user network on H3 r9 with population"

This module:

  * classifies the user message into an intent (regex-based, deterministic,
    fast — no extra LLM call);
  * runs the matching tool;
  * returns a chat-response-shaped dict ({answer, layer, rows?, sql?, ...}).

When no intent matches, classification returns None and the caller falls
through to the SQL agent unchanged.

The intent classifier is intentionally narrow. Anything ambiguous goes to
the SQL agent — which can still answer simple "where are the banks near
Central?" questions perfectly.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from typing import Any, Literal

import httpx

from app.clients.ddb import get_duckdb, register_kv_table
from app.clients.mapbox import get_mapbox
from app.models.network import Location, Network

log = logging.getLogger(__name__)

LAYER_PALETTE = [
    "#FAD037", "#FB3640", "#FA37B2", "#C637FA",
    "#37B2FA", "#37FADD", "#37FA7E", "#FA8237",
]


# ---------------------------------------------------------------------------
# Intent classification
# ---------------------------------------------------------------------------

Intent = Literal["osm_fetch", "isochrone", "h3_aggregate"]

# OSM category → Overpass amenity / shop / tourism tag. Aliases on the right
# of the colon get normalised to the canonical category on the left.
OSM_CATEGORIES: dict[str, dict[str, Any]] = {
    "schools":      {"overpass": '["amenity"~"school|kindergarten|college|university"]', "aliases": ["school", "kindergartens", "universities", "colleges"]},
    "hospitals":    {"overpass": '["amenity"~"hospital|clinic|doctors"]', "aliases": ["hospital", "clinics"]},
    "pharmacies":   {"overpass": '["amenity"="pharmacy"]', "aliases": ["pharmacy", "drugstores"]},
    "restaurants":  {"overpass": '["amenity"~"restaurant|cafe|fast_food"]', "aliases": ["restaurant", "cafes", "eateries"]},
    "supermarkets": {"overpass": '["shop"~"supermarket|convenience"]', "aliases": ["supermarket", "convenience stores"]},
    "mtr":          {"overpass": '["railway"="station"]["station"="subway"]', "aliases": ["mtr stations", "metro", "subway", "stations"]},
    "parks":        {"overpass": '["leisure"~"park|garden"]', "aliases": ["park", "gardens"]},
    "hotels":       {"overpass": '["tourism"~"hotel|hostel|guest_house"]', "aliases": ["hotel", "hostels"]},
    "museums":      {"overpass": '["tourism"="museum"]', "aliases": ["museum", "galleries"]},
    "atms":         {"overpass": '["amenity"="atm"]', "aliases": ["atm"]},
}

# Map an alias → canonical category for normalisation.
_ALIAS_TO_CATEGORY: dict[str, str] = {}
for canonical, spec in OSM_CATEGORIES.items():
    _ALIAS_TO_CATEGORY[canonical] = canonical
    for a in spec["aliases"]:
        _ALIAS_TO_CATEGORY[a.lower()] = canonical

_OSM_FETCH_RE = re.compile(
    r"(?:find|fetch|load|download|show|get|list|map)\s+"
    r"(?:all\s+|every\s+)?"
    r"(?:the\s+)?"
    r"(?P<cat>[a-zA-Z][\w\- ]+?)"
    r"(?:\s+(?:in|near|around|across|throughout|of|on)\s+(?:hong\s*kong|hk|the\s+region|the\s+map|the\s+territory))?"
    r"\b",
    re.IGNORECASE,
)

_ISOCHRONE_RE = re.compile(
    r"(?P<minutes>\d{1,2})\s*[- ]?(?:minute|min)\b[^.?]*?"
    r"(?:walking|walk|driving|drive|cycling|bike|bicycle)?"
    r"[^.?]*?(?:isochrone|catchment|reach|reachable area)"
    r"|"
    r"(?:isochrone|catchment)\s+(?:layer\s+)?"
    r"(?:for|of|around)\s+(?P<subject>[\w\s,]+)",
    re.IGNORECASE,
)

_H3_RE = re.compile(
    r"\b(?:h3|hex(?:agon)?s?|hexagonal)\b",
    re.IGNORECASE,
)
# Resolution is extracted with a separate, greedier pattern so it works
# regardless of where the resolution token appears relative to the h3 keyword.
_H3_RES_RE = re.compile(
    r"\b(?:r(?:es)?(?:olution)?)\s*(\d{1,2})\b",
    re.IGNORECASE,
)


@dataclass
class ClassifiedIntent:
    kind: Intent
    params: dict[str, Any]


def classify(message: str) -> ClassifiedIntent | None:
    """Return the recognised intent + extracted params, or None."""
    msg = message.strip()

    # Order matters: try the most specific first.
    iso = _match_isochrone(msg)
    if iso is not None:
        return iso

    h3i = _match_h3(msg)
    if h3i is not None:
        return h3i

    osm = _match_osm_fetch(msg)
    if osm is not None:
        return osm

    return None


def _match_osm_fetch(msg: str) -> ClassifiedIntent | None:
    m = _OSM_FETCH_RE.search(msg)
    if not m:
        return None
    raw_cat = m.group("cat").lower().strip()
    # Normalise: try whole match, then last word, then check aliases substring.
    canonical = _ALIAS_TO_CATEGORY.get(raw_cat)
    if canonical is None:
        # Strip plural / extra words: "elementary schools" → check "schools"
        last = raw_cat.split()[-1]
        canonical = _ALIAS_TO_CATEGORY.get(last)
    if canonical is None:
        # Last resort: substring match against all aliases.
        for alias, cat in _ALIAS_TO_CATEGORY.items():
            if alias in raw_cat:
                canonical = cat
                break
    if canonical is None:
        return None
    return ClassifiedIntent("osm_fetch", {"category": canonical, "raw": raw_cat})


def _match_isochrone(msg: str) -> ClassifiedIntent | None:
    m = _ISOCHRONE_RE.search(msg)
    if not m:
        return None
    minutes = m.group("minutes")
    subject = m.group("subject")
    profile = "walking"
    if re.search(r"drive|driving|car", msg, re.IGNORECASE):
        profile = "driving"
    return ClassifiedIntent("isochrone", {
        "minutes": int(minutes) if minutes else 15,
        "subject": (subject or "").strip() or "user_network",
        "profile": profile,
    })


def _match_h3(msg: str) -> ClassifiedIntent | None:
    if not _H3_RE.search(msg):
        return None
    res = None
    res_match = _H3_RES_RE.search(msg)
    if res_match:
        try:
            res = int(res_match.group(1))
        except ValueError:
            res = None
    return ClassifiedIntent("h3_aggregate", {
        "resolution": res if res is not None else 8,
    })


# ---------------------------------------------------------------------------
# OSM-fetch tool
# ---------------------------------------------------------------------------

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
HK_BBOX = "22.15,113.83,22.57,114.45"   # S,W,N,E


async def run_osm_fetch(category: str, raw: str | None = None) -> dict[str, Any]:
    """Hit Overpass for the category, register the result as `osm_<category>`
    in DuckDB, and return a chat-response dict with a GeoJSON layer payload.
    """
    spec = OSM_CATEGORIES.get(category)
    if not spec:
        return {
            "answer": f"I don't have an OSM mapping for '{raw or category}' yet. Try: {', '.join(sorted(OSM_CATEGORIES))}.",
            "rows": [], "columns": [], "layer": None, "sql": None,
            "error": "unknown_osm_category",
        }

    query = f"""
        [out:json][timeout:30];
        (
          node{spec["overpass"]}({HK_BBOX});
          way{spec["overpass"]}({HK_BBOX});
        );
        out center tags;
    """.strip()

    rows: list[dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            r = await client.post(OVERPASS_URL, data={"data": query})
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            log.warning("Overpass fetch failed for %s: %s", category, e)
            return {
                "answer": f"Couldn't reach Overpass to load `{category}` — {e}.",
                "rows": [], "columns": [], "layer": None, "sql": None,
                "error": "overpass_failed",
            }
        for el in data.get("elements", []):
            if el.get("type") == "node":
                lat, lng = el.get("lat"), el.get("lon")
            else:
                centre = el.get("center") or {}
                lat, lng = centre.get("lat"), centre.get("lon")
            if lat is None or lng is None:
                continue
            tags = el.get("tags", {})
            rows.append({
                "id": f"{el['type']}/{el['id']}",
                "name": tags.get("name") or tags.get("operator") or category,
                "brand": tags.get("brand"),
                "lat": float(lat),
                "lng": float(lng),
                "tags": tags,
            })

    if not rows:
        return {
            "answer": f"OSM returned 0 features for `{category}` in Hong Kong. Try a different category.",
            "rows": [], "columns": [], "layer": None, "sql": None,
            "error": "no_results",
        }

    # Register as a DuckDB table for follow-up SQL questions.
    conn = get_duckdb()
    table_name = f"osm_{category}"
    register_kv_table(
        conn,
        table_name,
        rows,
        [("id", "VARCHAR"), ("name", "VARCHAR"), ("brand", "VARCHAR"),
         ("lat", "DOUBLE"), ("lng", "DOUBLE")],
    )

    # Pick a colour from the palette (stable per category by hash).
    colour = LAYER_PALETTE[abs(hash(category)) % len(LAYER_PALETTE)]
    layer = _points_layer(
        layer_id=f"osm-{category}",
        label=f"OSM · {category} ({len(rows)})",
        rows=rows,
        colour=colour,
    )
    answer = (
        f"Loaded {len(rows):,} `{category}` features from OpenStreetMap into "
        f"`{table_name}`. They're on the map now — and you can SQL them: "
        f"`SELECT name, lat, lng FROM {table_name} LIMIT 10;`"
    )
    return {
        "answer": answer,
        "rows": [{"id": r["id"], "name": r["name"], "lat": r["lat"], "lng": r["lng"]} for r in rows[:50]],
        "columns": ["id", "name", "lat", "lng"],
        "sql": None,
        "layer": layer,
        "provider": "osm_overpass",
    }


# ---------------------------------------------------------------------------
# Mapbox-isochrone tool
# ---------------------------------------------------------------------------

async def run_isochrone(
    *,
    network: Network,
    subject: str,
    minutes: int,
    profile: str = "walking",
) -> dict[str, Any]:
    """Resolve `subject` to a point list and request a Mapbox isochrone per
    point, returning a polygon layer. Subjects we know how to resolve:

      - 'user_network' / empty               → all uploaded locations
      - 'hsbc'/'hang seng'/'boc'/…           → matching brand in osm_pois
      - 'banks' / 'atms'                     → all rows of that type in osm_pois
      - 'osm_<category>'                     → any previously-loaded OSM table
    """
    mb = get_mapbox()
    if not mb.has_token:
        return {
            "answer": "Can't run Mapbox isochrones — MAPBOX_ACCESS_TOKEN is not set.",
            "rows": [], "columns": [], "layer": None, "sql": None,
            "error": "no_mapbox_token",
        }

    points: list[Location] = _resolve_subject_points(network, subject)
    if not points:
        return {
            "answer": f"I couldn't resolve '{subject}' to any points. Try 'HSBC banks', "
                      f"'the user network', or 'all banks within 1 km of Central'.",
            "rows": [], "columns": [], "layer": None, "sql": None,
            "error": "subject_unresolved",
        }

    # Cap to keep the demo snappy (and stay polite to Mapbox).
    MAX_POINTS = 25
    if len(points) > MAX_POINTS:
        log.info("Capping isochrone subject from %d → %d points", len(points), MAX_POINTS)
        points = points[:MAX_POINTS]

    async def _one(loc: Location) -> dict | None:
        try:
            if profile == "driving":
                f = await mb.driving_isochrone(loc.lat, loc.lng, minutes)
            else:
                f = await mb.walking_isochrone(loc.lat, loc.lng, minutes)
        except Exception as e:
            log.info("Mapbox isochrone failed for %s: %s", loc.name, e)
            return None
        f.setdefault("properties", {})["location_id"] = loc.id
        f["properties"]["location_name"] = loc.name
        f["properties"]["minutes"] = minutes
        f["properties"]["profile"] = profile
        return f

    features = [f for f in await asyncio.gather(*[_one(p) for p in points]) if f]
    if not features:
        return {
            "answer": f"Mapbox isochrones came back empty for all {len(points)} candidate points. "
                      f"Check that the points are inside Mapbox's coverage area for {profile}.",
            "rows": [], "columns": [], "layer": None, "sql": None,
            "error": "isochrone_empty",
        }

    layer = {
        "id": f"isochrone-chat-{minutes}min-{profile}",
        "kind": "geojson",
        "data": {"type": "FeatureCollection", "features": features},
        "paint": {
            "fill-color": "#4F35F8",
            "fill-opacity": 0.30,
            "line-color": "#4F35F8",
            "line-width": 1.5,
            "line-opacity": 0.7,
        },
        "label": f"{minutes}-min {profile} isochrone · {subject}",
    }
    answer = (
        f"Computed {len(features)} {minutes}-minute {profile} isochrones around "
        f"the {subject!r} subject. Polygons are on the map at 30 % fill."
    )
    return {
        "answer": answer,
        "rows": [], "columns": [],
        "sql": None,
        "layer": layer,
        "provider": "mapbox_isochrone",
    }


def _resolve_subject_points(network: Network, subject: str) -> list[Location]:
    """Turn a string subject into a Location list using the live DuckDB."""
    raw = (subject or "").lower().strip()
    if not raw or raw in ("user network", "user_network", "the user network",
                          "your network", "my network", "the network"):
        return [loc for loc in network.locations if loc.lat is not None and loc.lng is not None]

    conn = get_duckdb()

    # Direct brand match in osm_pois.
    brand_keywords = ["hsbc", "hang seng", "bank of china", "boc", "citi", "citibank",
                       "standard chartered", "dbs", "icbc"]
    for kw in brand_keywords:
        if kw in raw:
            try:
                rows = conn.execute(
                    "SELECT id, name, lat, lng FROM osm_pois "
                    "WHERE LOWER(brand) LIKE ? OR LOWER(name) LIKE ? LIMIT 40",
                    [f"%{kw}%", f"%{kw}%"],
                ).fetchall()
                return [_loc_from_row(r) for r in rows]
            except Exception as e:
                log.info("Brand lookup failed: %s", e)
                return []

    # All competitor banks / atms.
    if "bank" in raw and "atm" not in raw:
        rows = conn.execute(
            "SELECT id, name, lat, lng FROM osm_pois WHERE type = 'bank' LIMIT 40"
        ).fetchall()
        return [_loc_from_row(r) for r in rows]
    if "atm" in raw:
        rows = conn.execute(
            "SELECT id, name, lat, lng FROM osm_pois WHERE type = 'atm' LIMIT 40"
        ).fetchall()
        return [_loc_from_row(r) for r in rows]

    # An on-demand osm_<category> table loaded earlier in the session.
    for category in OSM_CATEGORIES:
        if category[:-1] in raw or category in raw:
            try:
                rows = conn.execute(
                    f"SELECT id, name, lat, lng FROM osm_{category} LIMIT 40"
                ).fetchall()
                return [_loc_from_row(r) for r in rows]
            except duckdb_error_t():
                continue
    return []


def duckdb_error_t() -> tuple:
    """Helper to keep the broad-except contained without `pyright` whining."""
    import duckdb  # local import; cheap.
    return (duckdb.Error, Exception)


def _loc_from_row(r: tuple) -> Location:
    """row is (id, name, lat, lng)."""
    return Location(id=str(r[0]), name=str(r[1] or ""), lat=float(r[2]), lng=float(r[3]),
                    raw_fields={})


# ---------------------------------------------------------------------------
# H3-aggregate tool
# ---------------------------------------------------------------------------

async def run_h3_aggregate(*, network: Network, resolution: int) -> dict[str, Any]:
    """Aggregate the user-network points + competitor banks to H3 cells, join
    each cell to Kontur population, return a polygon layer that visualises
    competitive intensity per cell.
    """
    import h3  # local — cheap, already a dep.

    resolution = max(5, min(11, resolution))
    conn = get_duckdb()

    # Aggregate user + competitor counts per H3 cell, then join to population.
    cell_counts: dict[str, dict[str, Any]] = {}

    for loc in network.locations:
        if loc.lat is None or loc.lng is None:
            continue
        cell = h3.latlng_to_cell(loc.lat, loc.lng, resolution)
        e = cell_counts.setdefault(cell, {"user": 0, "competitor": 0})
        e["user"] += 1

    try:
        comp_rows = conn.execute(
            "SELECT lat, lng FROM osm_pois WHERE type = 'bank' AND lat IS NOT NULL"
        ).fetchall()
    except Exception:
        comp_rows = []
    for lat, lng in comp_rows:
        cell = h3.latlng_to_cell(float(lat), float(lng), resolution)
        e = cell_counts.setdefault(cell, {"user": 0, "competitor": 0})
        e["competitor"] += 1

    # Join population (sum kontur_pop_hex cells whose centroid falls into our cell).
    try:
        pop_rows = conn.execute("SELECT lat, lng, population FROM kontur_pop_hex").fetchall()
    except Exception:
        pop_rows = []
    for lat, lng, pop in pop_rows:
        cell = h3.latlng_to_cell(float(lat), float(lng), resolution)
        if cell not in cell_counts:
            continue  # only enrich cells we already care about
        e = cell_counts[cell]
        e["population"] = e.get("population", 0.0) + float(pop)

    if not cell_counts:
        return {
            "answer": "No points to aggregate. Upload a CSV first.",
            "rows": [], "columns": [], "layer": None, "sql": None,
            "error": "empty",
        }

    # Build the polygon FeatureCollection.
    features = []
    for cell, e in cell_counts.items():
        boundary = h3.cell_to_boundary(cell)  # list[(lat, lng)]
        ring = [[lng, lat] for (lat, lng) in boundary]
        if ring and ring[0] != ring[-1]:
            ring.append(ring[0])
        features.append({
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [ring]},
            "properties": {
                "h3": cell,
                "user_count": e.get("user", 0),
                "competitor_count": e.get("competitor", 0),
                "population": int(e.get("population", 0)),
                # A simple "intensity" score for paint: competitor pressure
                # divided by user-network share, normalised.
                "intensity": (e.get("competitor", 0) + 1) / (e.get("user", 0) + 1),
            },
        })

    layer = {
        "id": f"h3-r{resolution}-chat",
        "kind": "geojson",
        "data": {"type": "FeatureCollection", "features": features},
        "paint": {
            "fill-color": [
                "interpolate", ["linear"], ["get", "intensity"],
                0.5, "#37FA7E",
                1.0, "#FAD037",
                3.0, "#FB3640",
                10.0, "#C637FA",
            ],
            "fill-opacity": 0.30,
            "line-color": "#0A0903",
            "line-width": 0.4,
            "line-opacity": 0.5,
        },
        "label": f"H3 r{resolution} · competitive intensity",
    }

    total_user = sum(e.get("user", 0) for e in cell_counts.values())
    total_comp = sum(e.get("competitor", 0) for e in cell_counts.values())
    total_pop = sum(e.get("population", 0) for e in cell_counts.values())
    answer = (
        f"Aggregated to {len(cell_counts):,} H3 r{resolution} cells: {total_user} "
        f"of your branches + {total_comp} competitor banks, covering "
        f"{int(total_pop):,} residents (Kontur). Cells are coloured by "
        f"competitor-to-own-network ratio: green = friendly, red/purple = crowded."
    )
    return {
        "answer": answer,
        "rows": [{"h3": k, **v} for k, v in list(cell_counts.items())[:50]],
        "columns": ["h3", "user", "competitor", "population"],
        "sql": None,
        "layer": layer,
        "provider": "h3_aggregate",
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _points_layer(*, layer_id: str, label: str, rows: list[dict],
                  colour: str) -> dict[str, Any]:
    features = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [r["lng"], r["lat"]]},
            "properties": {
                "id": r.get("id"),
                "name": r.get("name") or "",
                "brand": r.get("brand"),
            },
        }
        for r in rows if r.get("lat") is not None and r.get("lng") is not None
    ]
    return {
        "id": layer_id,
        "kind": "geojson",
        "data": {"type": "FeatureCollection", "features": features},
        "paint": {
            "circle-color": colour,
            "circle-radius": 5,
            "circle-stroke-color": "#FDFDFD",
            "circle-stroke-width": 1.5,
        },
        "label": label,
    }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def maybe_run_tool(*, network: Network, message: str) -> dict[str, Any] | None:
    """Return a chat-response dict if `message` triggers a non-SQL tool,
    else None — caller falls through to the SQL agent."""
    intent = classify(message)
    if intent is None:
        return None
    log.info("chat tool intent: %s params=%s", intent.kind, intent.params)
    if intent.kind == "osm_fetch":
        return await run_osm_fetch(intent.params["category"], intent.params.get("raw"))
    if intent.kind == "isochrone":
        return await run_isochrone(
            network=network,
            subject=intent.params["subject"],
            minutes=intent.params["minutes"],
            profile=intent.params["profile"],
        )
    if intent.kind == "h3_aggregate":
        return await run_h3_aggregate(network=network, resolution=intent.params["resolution"])
    return None
