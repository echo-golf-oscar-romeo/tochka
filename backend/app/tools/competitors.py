"""Competitive-landscape tools — competitor banks, retail anchors."""

from __future__ import annotations

import json
import logging
import math
from functools import lru_cache
from pathlib import Path

from app.config import get_settings
from app.mock import canned
from app.models.network import Location

log = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _load_osm_pois() -> tuple[dict, ...]:
    """Read the pre-fetched OSM banks/ATMs JSON. Returns an immutable tuple
    cached for the lifetime of the process. Empty tuple if the file is
    missing — callers fall back to canned data.
    """
    path = Path(get_settings().osm_banks_path)
    if not path.is_absolute():
        # Resolve relative to the repo root (parent of backend/).
        path = (Path(__file__).resolve().parents[3] / path).resolve()
    if not path.exists():
        log.warning("OSM banks file not found at %s — competitor tool will use canned data. "
                    "Run: uv run python scripts/fetch_osm_banks.py", path)
        return ()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        log.warning("Failed to read %s: %s", path, e)
        return ()
    return tuple(data)


def _approx_distance_m(lat_a: float, lng_a: float, lat_b: float, lng_b: float) -> float:
    """Equirectangular approximation — good enough at HK scale (~1% error)."""
    mean_lat = math.radians((lat_a + lat_b) / 2.0)
    dx = (lng_a - lng_b) * 111_320 * math.cos(mean_lat)
    dy = (lat_a - lat_b) * 110_540
    return math.hypot(dx, dy)


async def competitors_in_radius(locations: list[Location], radius_m: int = 500,
                                categories: tuple[str, ...] = ("bank",)) -> list[dict]:
    """Find competitor POIs within `radius_m` of each user location.

    Source: pre-fetched OSM banks + ATMs at data/osm/banks_atms_hk.json
    (generate via backend/scripts/fetch_osm_banks.py).
    """
    s = get_settings()
    if s.demo_mode:
        return canned.competitors_in_radius(locations, radius_m)

    pois = _load_osm_pois()
    if not pois:
        return canned.competitors_in_radius(locations, radius_m)

    # Filter by category.
    cat_set = set(categories)
    pool = [p for p in pois if p.get("type") in cat_set]
    if not pool:
        return []

    out: list[dict] = []
    seen: set[str] = set()
    for loc in locations:
        if loc.lat is None or loc.lng is None:
            continue
        for poi in pool:
            d = _approx_distance_m(loc.lat, loc.lng, poi["lat"], poi["lng"])
            if d > radius_m:
                continue
            # Same-building same-id: skip; otherwise dedupe by POI id across user locations.
            pid = poi["id"]
            if pid in seen:
                continue
            seen.add(pid)
            out.append({
                "id": pid,
                "name": poi.get("name"),
                "brand": poi.get("brand"),
                "lat": poi["lat"],
                "lng": poi["lng"],
                "distance_m": round(d, 1),
                "atm": bool(poi.get("atm")),
                "district": poi.get("addr_district"),
                "nearest_user_location_id": loc.id,
            })
    log.info("competitors_in_radius: %d POIs within %dm of %d user locations.",
             len(out), radius_m, len(locations))
    return out


async def gmaps_poi_scrape(bbox: tuple[float, float, float, float],
                           category: str = "bank") -> list[dict]:
    """On-demand Google Maps POI extraction. Heavy; not wired yet."""
    if get_settings().demo_mode:
        return canned.gmaps_pois(bbox, category)
    raise NotImplementedError("Wire the SiteSense-derived gmaps parser.")
