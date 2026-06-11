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

Intent = Literal["osm_fetch", "osm_freeform", "isochrone", "h3_aggregate", "buffer"]

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
    r"(?:find|fetch|load|download|show|get|list|map|add|plot|drop|include|import|put|place|render|display|pull)\s+"
    r"(?:all\s+|every\s+|some\s+)?"
    r"(?:the\s+)?"
    r"(?P<cat>[a-zA-Z][\w\- ]+?)"
    r"(?:\s+(?:in|near|around|across|throughout|of|on|to|onto|into)\s+(?:hong\s*kong|hk|the\s+region|the\s+map|the\s+territory|the\s+database))?"
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

# Buffer intent — two-pass matcher (more robust than one giant regex):
#   1. `_BUFFER_KEYWORD_RE` — the message must mention "buffer" / "buffer zone".
#   2. `_BUFFER_RADIUS_RE`  — extract a "<number><unit>" or "<number> <unit>"
#                            anywhere in the message (hyphenated form
#                            "250-metre" also accepted).
#   3. `_BUFFER_SUBJECT_RE` — capture the phrase after a directional
#                            preposition (from / around / of / for / on /
#                            across / surrounding) — only if it's adjacent
#                            to the word "buffer", to avoid grabbing the
#                            subject's tail when it sits inside e.g.
#                            "at 400 metres".
_UNIT = r"k?m|meters?|metres?|kilometers?|kilometres?"
_BUFFER_KEYWORD_RE = re.compile(r"\bbuffer(?:\s+zone)?s?\b", re.IGNORECASE)
_BUFFER_RADIUS_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*[-]?\s*(" + _UNIT + r")\b",
    re.IGNORECASE,
)
_BUFFER_SUBJECT_RE = re.compile(
    r"\b(?:from|around|of|for|on|across|surrounding)\s+(?P<subject>[^?.!]+?)"
    r"(?:\s+(?:at|with|=)\s+\d|\s*$|[?.!])",
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

    # Slash-prefixed commands take priority — they're explicit.
    free = _match_osm_freeform(msg)
    if free is not None:
        return free

    # Order matters: try the most specific first.
    iso = _match_isochrone(msg)
    if iso is not None:
        return iso

    buf = _match_buffer(msg)
    if buf is not None:
        return buf

    h3i = _match_h3(msg)
    if h3i is not None:
        return h3i

    osm = _match_osm_fetch(msg)
    if osm is not None:
        return osm

    return None


_OSM_SLASH_RE = re.compile(r"^\s*/osm\b[:\s]*(?P<query>.+)$", re.IGNORECASE | re.DOTALL)


def _match_osm_freeform(msg: str) -> ClassifiedIntent | None:
    """Match the explicit slash command `/osm <natural-language query>`.
    Free-form OSM lookups go through an LLM-translated Overpass call —
    not the preset-category path."""
    m = _OSM_SLASH_RE.match(msg)
    if not m:
        return None
    query = (m.group("query") or "").strip()
    if not query:
        return None
    return ClassifiedIntent("osm_freeform", {"query": query})


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


def _match_buffer(msg: str) -> ClassifiedIntent | None:
    if not _BUFFER_KEYWORD_RE.search(msg):
        return None
    radius_match = _BUFFER_RADIUS_RE.search(msg)
    if not radius_match:
        return None
    radius_m = float(radius_match.group(1))
    unit = radius_match.group(2).lower()
    if unit.startswith("k"):
        radius_m *= 1000
    if radius_m < 1 or radius_m > 50_000:
        return None

    subject_match = _BUFFER_SUBJECT_RE.search(msg)
    subject = ""
    if subject_match:
        subject = (subject_match.group("subject") or "").strip().rstrip(",.;")
        # Drop a trailing " at <number>…" or " with <number>…" if the
        # regex's anchor didn't already strip it.
        subject = re.sub(r"\s+(?:at|with|=)\s+\d.*$", "", subject, flags=re.IGNORECASE).strip()

    return ClassifiedIntent("buffer", {
        "radius_m": radius_m,
        "subject": subject or "user_network",
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

# Overpass-api.de's operators rate-limit / block requests that arrive with
# the default `python-httpx/X.Y` User-Agent (it gets the request a 406 with
# Apache's generic "Not Acceptable" page — nothing to do with the actual
# query). A real, identifiable UA gets through normally.
OVERPASS_HEADERS = {
    "User-Agent": "tochka/0.1 (https://github.com/echo-golf-oscar-romeo/tochka)",
}


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
    async with httpx.AsyncClient(timeout=30.0, headers=OVERPASS_HEADERS) as client:
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
            "fill-opacity": 0.20,
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
                    "WHERE LOWER(brand) LIKE ? OR LOWER(name) LIKE ? LIMIT 500",
                    [f"%{kw}%", f"%{kw}%"],
                ).fetchall()
                return [_loc_from_row(r) for r in rows]
            except Exception as e:
                log.info("Brand lookup failed: %s", e)
                return []

    # All competitor banks / atms.
    if "bank" in raw and "atm" not in raw:
        rows = conn.execute(
            "SELECT id, name, lat, lng FROM osm_pois WHERE type = 'bank' LIMIT 500"
        ).fetchall()
        return [_loc_from_row(r) for r in rows]
    if "atm" in raw:
        rows = conn.execute(
            "SELECT id, name, lat, lng FROM osm_pois WHERE type = 'atm' LIMIT 500"
        ).fetchall()
        return [_loc_from_row(r) for r in rows]

    # An on-demand osm_<category> table loaded earlier in the session.
    for category in OSM_CATEGORIES:
        if category[:-1] in raw or category in raw:
            try:
                rows = conn.execute(
                    f"SELECT id, name, lat, lng FROM osm_{category} LIMIT 500"
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
# Free-form OSM tool — `/osm <natural language>` → Overpass QL → map layer.
# ---------------------------------------------------------------------------

_OSM_TRANSLATOR_SYSTEM = """You translate natural-language requests into OpenStreetMap Overpass QL filter expressions for Hong Kong.

Respond with EXACTLY ONE JSON object — no prose, no markdown fences, no commentary. Schema:

{
  "name":    "<short snake_case label, e.g. 'cafes', 'parks', 'mtr_exits', 'bridges_kln'>",
  "filters": ["<filter1>", "<filter2>", ...]
}

Each filter is ONE Overpass query line of the form:
  node["amenity"="cafe"]
  way["leisure"="park"]
  relation["boundary"="administrative"]
  node["amenity"~"cafe|restaurant"]
  way["highway"="primary"]["name"~"Queen"]   (multiple bracketed AND filters)

Hard rules:
  - DO NOT include the bbox (the backend appends Hong Kong's bbox to each line).
  - DO NOT include `out`, `[out:json]`, `[timeout:N]`, `(` union wrappers, or `>;` recursion.
  - Each filter is a SINGLE statement — no semicolons inside it.
  - For most POI categories include BOTH `node` and `way` (people tag the same thing both ways).
  - For polygons/areas (parks, lakes, buildings, schools-as-area) include `way` and `relation`.
  - For roads or rivers include `way`.
  - Maximum 6 filters.

Examples:

  Query: "cafes"
  → {"name": "cafes", "filters": ["node[\\"amenity\\"=\\"cafe\\"]", "way[\\"amenity\\"=\\"cafe\\"]"]}

  Query: "parks and gardens"
  → {"name": "parks", "filters": ["way[\\"leisure\\"~\\"park|garden\\"]", "relation[\\"leisure\\"~\\"park|garden\\"]"]}

  Query: "MTR station exits"
  → {"name": "mtr_exits", "filters": ["node[\\"railway\\"=\\"subway_entrance\\"]"]}

  Query: "primary roads named Queen's Road"
  → {"name": "queens_rd", "filters": ["way[\\"highway\\"=\\"primary\\"][\\"name\\"~\\"Queen\\"]"]}

  Query: "every Starbucks"
  → {"name": "starbucks", "filters": ["node[\\"amenity\\"=\\"cafe\\"][\\"brand\\"~\\"Starbucks\\",i]", "node[\\"brand:wikidata\\"=\\"Q37158\\"]"]}
"""


_OVERPASS_FILTER_RE = re.compile(
    r"^\s*(?:node|way|relation|nwr)\s*"
    r"(?:\[[^\];]+\])+\s*$",
    re.IGNORECASE,
)


def _safe_overpass_filter(line: str) -> bool:
    """Belt-and-braces validation of one filter line. Reject anything that
    could escape into the surrounding query (semicolons, recursive ops,
    union wrappers, output directives)."""
    if ";" in line or ">" in line or "<" in line:
        return False
    if "out " in line.lower() or "out;" in line.lower():
        return False
    if "(" in line or ")" in line:
        # We add the (bbox) parens ourselves — filters shouldn't have them.
        return False
    return bool(_OVERPASS_FILTER_RE.match(line.strip()))


def _parse_translator_json(raw: str) -> dict | None:
    """Tolerate light wrapping (markdown fence, leading prose) and pull the
    first JSON object out of the LLM response."""
    import json as _json

    if not raw:
        return None
    # Strip ```json … ``` if present.
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
    if fence:
        raw = fence.group(1)
    # Fall back to first {...} block in the text.
    blob = re.search(r"\{[\s\S]*\}", raw)
    if not blob:
        return None
    try:
        obj = _json.loads(blob.group(0))
    except _json.JSONDecodeError:
        return None
    if not isinstance(obj, dict):
        return None
    name = obj.get("name")
    filters = obj.get("filters")
    if not isinstance(name, str) or not isinstance(filters, list):
        return None
    if not all(isinstance(f, str) for f in filters):
        return None
    return {"name": name, "filters": filters[:6]}


def _slugify(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9_]+", "_", s.strip().lower())
    return s.strip("_") or "freeform"


def _osm_element_to_feature(el: dict) -> dict | None:
    """Convert one Overpass element (with `out geom tags`) to a GeoJSON
    Feature — picking Point / LineString / Polygon based on shape."""
    t = el.get("type")
    tags = el.get("tags") or {}
    base_props: dict[str, Any] = {
        "id": f"{t}/{el.get('id')}",
        "name": tags.get("name") or tags.get("operator") or tags.get("brand") or "",
        "brand": tags.get("brand"),
    }
    # Copy a few useful tags onto top-level props for popup readability.
    for k in ("amenity", "shop", "tourism", "leisure", "highway", "railway", "natural"):
        v = tags.get(k)
        if v:
            base_props[k] = v

    if t == "node":
        lat, lng = el.get("lat"), el.get("lon")
        if lat is None or lng is None:
            return None
        base_props["lat"] = float(lat)
        base_props["lng"] = float(lng)
        return {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [float(lng), float(lat)]},
            "properties": base_props,
        }

    if t == "way":
        geom = el.get("geometry") or []
        if len(geom) < 2:
            # Way without expanded geometry — fall back to center.
            c = el.get("center") or {}
            if c.get("lat") is None or c.get("lon") is None:
                return None
            base_props["lat"] = float(c["lat"])
            base_props["lng"] = float(c["lon"])
            return {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [float(c["lon"]), float(c["lat"])]},
                "properties": base_props,
            }
        coords = [[float(p["lon"]), float(p["lat"])] for p in geom]
        closed = len(coords) >= 4 and coords[0] == coords[-1]
        if closed:
            return {
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [coords]},
                "properties": base_props,
            }
        return {
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": coords},
            "properties": base_props,
        }

    if t == "relation":
        # Overpass with `out geom` for relations returns each member's
        # geometry — stitch outer rings only. For complex relations the
        # result is approximate; precise multipolygon reassembly is out
        # of scope here. Skip if we can't get an obvious centroid.
        members = el.get("members") or []
        outer_rings: list[list[list[float]]] = []
        for m in members:
            if m.get("role") != "outer":
                continue
            mg = m.get("geometry") or []
            if len(mg) < 4:
                continue
            ring = [[float(p["lon"]), float(p["lat"])] for p in mg]
            if ring[0] != ring[-1]:
                ring.append(ring[0])
            outer_rings.append(ring)
        if outer_rings:
            geom_type = "Polygon" if len(outer_rings) == 1 else "MultiPolygon"
            geom_obj = (
                {"type": "Polygon", "coordinates": [outer_rings[0]]}
                if geom_type == "Polygon"
                else {"type": "MultiPolygon", "coordinates": [[r] for r in outer_rings]}
            )
            return {"type": "Feature", "geometry": geom_obj, "properties": base_props}
        return None

    return None


def _layer_paint_for_geometry(geom_types: set[str]) -> dict[str, Any]:
    """Choose paint based on dominant geometry type in the result set."""
    if "Polygon" in geom_types or "MultiPolygon" in geom_types:
        return {
            "fill-color": "#37B2FA",
            "fill-opacity": 0.20,
            "line-color": "#37B2FA",
            "line-width": 1.2,
            "line-opacity": 0.7,
        }
    if "LineString" in geom_types or "MultiLineString" in geom_types:
        return {
            "line-color": "#FA8237",
            "line-width": 2.0,
            "line-opacity": 0.85,
        }
    return {
        "circle-color": "#FA37B2",
        "circle-radius": 5,
        "circle-stroke-color": "#FDFDFD",
        "circle-stroke-width": 1.5,
    }


async def run_osm_freeform(*, query: str) -> dict[str, Any]:
    """Translate the user's natural-language query into Overpass QL via
    LLM, validate, fetch, and return a layer."""
    from app.clients.llm import get_llm

    llm = get_llm()
    if not llm.has_key:
        return {
            "answer": "LLM provider isn't configured (no API key), so I can't translate "
                      "the OSM query. Set DEEPSEEK_API_KEY or DASHSCOPE_API_KEY and retry.",
            "rows": [], "columns": [], "layer": None, "sql": None,
            "error": "no_api_key",
        }

    raw = await llm.chat(
        messages=[
            {"role": "system", "content": _OSM_TRANSLATOR_SYSTEM},
            {"role": "user", "content": f"Query: {query}\n\nReturn the JSON object only."},
        ],
        temperature=0.1,
        max_tokens=400,
    )
    parsed = _parse_translator_json(raw or "")
    if not parsed:
        return {
            "answer": "I couldn't translate that into Overpass QL. Try a more concrete "
                      "phrasing — e.g. `/osm parks and gardens`, `/osm Starbucks branches`, "
                      "or `/osm primary roads named Queen`.",
            "rows": [], "columns": [], "layer": None, "sql": None,
            "error": "translator_failed",
        }

    filters = [f for f in parsed["filters"] if _safe_overpass_filter(f)]
    if not filters:
        log.info("OSM translator produced no safe filters. Raw: %s", raw[:300] if raw else "")
        return {
            "answer": "The translation came back with no usable filter lines. Try rephrasing.",
            "rows": [], "columns": [], "layer": None, "sql": None,
            "error": "no_safe_filters",
        }

    name = _slugify(parsed["name"])
    body = "\n  ".join(f"{f}({HK_BBOX});" for f in filters)
    # `out geom;` == `out body geom;` — returns ids + tags + members +
    # expanded geometry. Note: `out geom tags;` is INVALID syntax because
    # `tags` is itself an output-type specifier that conflicts with `body`.
    overpass_query = f"[out:json][timeout:30];\n(\n  {body}\n);\nout geom;"

    async with httpx.AsyncClient(timeout=45.0, headers=OVERPASS_HEADERS) as client:
        try:
            r = await client.post(OVERPASS_URL, data={"data": overpass_query})
            if r.status_code >= 400:
                log.warning(
                    "Overpass freeform HTTP %s for %r. Body: %s | Query: %s",
                    r.status_code, query, r.text[:300], overpass_query[:300],
                )
                return {
                    "answer": f"Overpass {r.status_code}: {r.text[:200] if r.text else '(no body)'}",
                    "rows": [], "columns": [], "layer": None, "sql": None,
                    "error": "overpass_http",
                }
            data = r.json()
        except Exception as e:
            log.warning("Overpass freeform fetch failed for %r: %s", query, e)
            return {
                "answer": f"Couldn't reach Overpass: {e}",
                "rows": [], "columns": [], "layer": None, "sql": None,
                "error": "overpass_failed",
            }

    features: list[dict] = []
    geom_types: set[str] = set()
    for el in data.get("elements", []):
        feat = _osm_element_to_feature(el)
        if not feat:
            continue
        features.append(feat)
        geom_types.add(feat["geometry"]["type"])

    if not features:
        return {
            "answer": f"Overpass returned 0 features for /osm `{query}`. "
                      f"Filter line(s) tried: `{'`, `'.join(filters)}`. "
                      "Try a simpler phrasing.",
            "rows": [], "columns": [], "layer": None, "sql": None,
            "error": "no_results",
        }

    # Register point-shaped rows as a DuckDB table so SQL follow-ups work
    # (only points carry lat/lng cleanly — way/relation geoms are too rich
    # for a flat table). Polygons/lines are still on the map as the layer.
    point_rows = [
        {
            "id": f["properties"]["id"],
            "name": f["properties"]["name"] or "",
            "brand": f["properties"].get("brand"),
            "lat": f["properties"].get("lat"),
            "lng": f["properties"].get("lng"),
        }
        for f in features
        if f["geometry"]["type"] == "Point" and f["properties"].get("lat") is not None
    ]
    table_name = f"osm_{name}"
    if point_rows:
        conn = get_duckdb()
        register_kv_table(
            conn, table_name, point_rows,
            [("id", "VARCHAR"), ("name", "VARCHAR"), ("brand", "VARCHAR"),
             ("lat", "DOUBLE"), ("lng", "DOUBLE")],
        )

    layer_id = f"osm-free-{name}-{abs(hash(query)) % 1000:03d}"
    layer = {
        "id": layer_id,
        "kind": "geojson",
        "data": {"type": "FeatureCollection", "features": features},
        "paint": _layer_paint_for_geometry(geom_types),
        "label": f"OSM · {name} ({len(features)})",
    }

    geom_summary = ", ".join(sorted(geom_types))
    table_note = (
        f" SQL: `SELECT name, lat, lng FROM {table_name} LIMIT 10;`"
        if point_rows else " (Polygons/lines not registered as a SQL table — query OSM again to refine.)"
    )
    answer = (
        f"Loaded {len(features):,} OSM features for `{query}` ({geom_summary}). "
        f"Filters used: `{'`, `'.join(filters)}`.{table_note}"
    )
    rows_preview = [
        {"id": f["properties"]["id"], "name": f["properties"]["name"] or "",
         "lat": f["properties"].get("lat"), "lng": f["properties"].get("lng")}
        for f in features[:50]
    ]
    return {
        "answer": answer,
        "rows": rows_preview,
        "columns": ["id", "name", "lat", "lng"],
        "sql": None,
        "layer": layer,
        "provider": "osm_freeform",
    }


# ---------------------------------------------------------------------------
# Buffer tool — DuckDB ST_Buffer producing real polygons.
# ---------------------------------------------------------------------------

async def run_buffer(*, network: Network, subject: str, radius_m: float) -> dict[str, Any]:
    """Resolve `subject` to a point list, ST_Buffer each one in EPSG:3857
    with always_xy=true (critical — without it the geometry comes back
    empty), transform back to WGS84, and return a polygon layer.
    """
    points = _resolve_subject_points(network, subject)
    if not points:
        return {
            "answer": f"I couldn't resolve '{subject}' to any points. Try 'every bank', "
                      f"'HSBC banks', 'the user network', or load a category first "
                      f"('add all the schools in hong kong').",
            "rows": [], "columns": [], "layer": None, "sql": None,
            "error": "subject_unresolved",
        }

    # Cap to keep the demo snappy.
    MAX_POINTS = 200
    if len(points) > MAX_POINTS:
        log.info("Capping buffer subject from %d → %d points", len(points), MAX_POINTS)
        points = points[:MAX_POINTS]

    conn = get_duckdb()
    # Build a transient values list and let DuckDB-spatial buffer it in
    # one SQL call. EPSG:3857 metres → buffer → back to EPSG:4326, with
    # `always_xy=true` on BOTH transforms so the lng/lat axis order is
    # honoured (otherwise the polygon coordinates come back empty).
    rows_values = ",".join(
        f"('{loc.id.replace(chr(39), chr(39)+chr(39))}', "
        f"'{(loc.name or '').replace(chr(39), chr(39)+chr(39))}', "
        f"{loc.lng}, {loc.lat})"
        for loc in points
    )
    try:
        result = conn.execute(f"""
            WITH src(id, name, lng, lat) AS (VALUES {rows_values})
            SELECT
                id,
                name,
                lng,
                lat,
                ST_AsGeoJSON(
                    ST_Transform(
                        ST_Buffer(
                            ST_Transform(ST_Point(lng, lat),
                                         'EPSG:4326', 'EPSG:3857', true),
                            {radius_m}
                        ),
                        'EPSG:3857', 'EPSG:4326', true
                    )
                ) AS geojson
            FROM src
        """).fetchall()
    except Exception as e:
        log.warning("Buffer SQL failed: %s", e)
        return {
            "answer": f"Buffer computation failed in DuckDB: {e}",
            "rows": [], "columns": [], "layer": None, "sql": None,
            "error": "buffer_sql_failed",
        }

    features = []
    import json as _json
    for (id_, name, lng, lat, geojson) in result:
        if not geojson:
            continue
        try:
            geom = _json.loads(geojson)
        except Exception:
            continue
        if not geom.get("coordinates"):
            continue
        features.append({
            "type": "Feature",
            "geometry": geom,
            "properties": {
                "id": id_,
                "name": name,
                "radius_m": radius_m,
                "centre_lng": lng,
                "centre_lat": lat,
            },
        })

    if not features:
        return {
            "answer": f"Buffer produced no polygons for '{subject}'. "
                      f"This usually means the coordinate transform failed silently — "
                      f"check that the subject points have valid lat/lng.",
            "rows": [], "columns": [], "layer": None, "sql": None,
            "error": "buffer_empty",
        }

    label_subject = subject if subject and subject != "user_network" else "your network"
    radius_label = f"{int(radius_m)} m" if radius_m < 1000 else f"{radius_m / 1000:g} km"
    layer = {
        "id": f"buffer-chat-{int(radius_m)}m-{abs(hash(subject)) % 1000:03d}",
        "kind": "geojson",
        "data": {"type": "FeatureCollection", "features": features},
        "paint": {
            "fill-color": "#4F35F8",
            "fill-opacity": 0.20,
            "line-color": "#4F35F8",
            "line-width": 1.4,
            "line-opacity": 0.7,
        },
        "label": f"{radius_label} buffer · {label_subject}",
    }
    answer = (
        f"Built {len(features)} {radius_label} buffer polygon(s) around "
        f"{label_subject}. Layer is on the map at 20 % fill opacity — "
        f"drag it up or down in the right-hand panel to change stacking."
    )
    return {
        "answer": answer,
        "rows": [
            {"id": f["properties"]["id"], "name": f["properties"]["name"],
             "centre_lat": f["properties"]["centre_lat"], "centre_lng": f["properties"]["centre_lng"]}
            for f in features[:50]
        ],
        "columns": ["id", "name", "centre_lat", "centre_lng"],
        "sql": None,
        "layer": layer,
        "provider": "duckdb_st_buffer",
    }


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
            "fill-opacity": 0.20,
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
        # No data-fetch / geometry intent — try the advanced-method router
        # (coverage optimisation, hot-spots, find-similar, whitespace, …).
        from app.orchestrator.method_tools import maybe_run_method
        return await maybe_run_method(network=network, message=message)
    log.info("chat tool intent: %s params=%s", intent.kind, intent.params)
    if intent.kind == "osm_fetch":
        return await run_osm_fetch(intent.params["category"], intent.params.get("raw"))
    if intent.kind == "osm_freeform":
        return await run_osm_freeform(query=intent.params["query"])
    if intent.kind == "isochrone":
        return await run_isochrone(
            network=network,
            subject=intent.params["subject"],
            minutes=intent.params["minutes"],
            profile=intent.params["profile"],
        )
    if intent.kind == "h3_aggregate":
        return await run_h3_aggregate(network=network, resolution=intent.params["resolution"])
    if intent.kind == "buffer":
        return await run_buffer(
            network=network,
            subject=intent.params["subject"],
            radius_m=intent.params["radius_m"],
        )
    return None
