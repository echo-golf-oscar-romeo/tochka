"""Reachability tools — isochrone polygons by walking, driving, transit."""

from __future__ import annotations

import asyncio
import logging

from app.clients.mapbox import get_mapbox
from app.config import get_settings
from app.mock import canned
from app.models.network import Location

log = logging.getLogger(__name__)


async def _mapbox_one(loc: Location, minutes: int, profile: str) -> dict | None:
    if loc.lat is None or loc.lng is None:
        return None
    mb = get_mapbox()
    try:
        if profile == "walking":
            feat = await mb.walking_isochrone(loc.lat, loc.lng, minutes)
        else:
            feat = await mb.driving_isochrone(loc.lat, loc.lng, minutes)
    except Exception as e:
        log.warning("Mapbox isochrone failed for %s: %s", loc.name, e)
        return None
    # Tag the feature so downstream tools can join back to the location.
    props = feat.setdefault("properties", {})
    props["location_id"] = loc.id
    props["minutes"] = minutes
    props["profile"] = profile
    return feat


async def _real_isochrones(locations: list[Location], minutes: int, profile: str) -> list[dict]:
    # Fire requests concurrently — Mapbox handles ~10 RPS happily.
    tasks = [_mapbox_one(loc, minutes, profile) for loc in locations]
    results = await asyncio.gather(*tasks)
    out = [f for f in results if f]
    # For any location that failed real lookup, fall back to canned circle
    # so the storymap still has a polygon per branch.
    covered = {f["properties"]["location_id"] for f in out}
    failed = [loc for loc in locations if loc.id not in covered and loc.lat is not None]
    if failed:
        log.info("Falling back to canned isochrones for %d branches.", len(failed))
        out.extend(canned.isochrones_walk(failed, minutes))
    return out


async def isochrone_walk(locations: list[Location], minutes: int = 10) -> list[dict]:
    """Walking isochrone per location.

    Primary: Mapbox Isochrone API (returns polygons directly). See
    app/clients/mapbox.py for the design rationale vs CSDI.
    Fallback: canned circles (offline / no MAPBOX_ACCESS_TOKEN / API failure).
    Forced canned: DEMO_MODE=true.
    """
    s = get_settings()
    if s.demo_mode:
        return canned.isochrones_walk(locations, minutes)
    mb = get_mapbox()
    if not mb.has_token:
        log.info("MAPBOX_ACCESS_TOKEN not set; using canned isochrones.")
        return canned.isochrones_walk(locations, minutes)
    return await _real_isochrones(locations, minutes, "walking")


async def isochrone_drive(locations: list[Location], minutes: int = 15) -> list[dict]:
    """Driving isochrone via Mapbox; canned fallback."""
    s = get_settings()
    if s.demo_mode:
        return canned.isochrones_walk(locations, minutes)
    mb = get_mapbox()
    if not mb.has_token:
        return canned.isochrones_walk(locations, minutes)
    return await _real_isochrones(locations, minutes, "driving")


async def isochrone_transit(locations: list[Location], minutes: int = 20) -> list[dict]:
    """Transit isochrone — MTR + bus. Not yet wired; falls back to canned."""
    if get_settings().demo_mode:
        return canned.isochrones_walk(locations, minutes)
    log.info("Transit isochrones not yet wired; using canned circles.")
    return canned.isochrones_walk(locations, minutes)
