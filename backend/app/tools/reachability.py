"""Reachability tools — isochrone polygons by walking, driving, transit."""

from __future__ import annotations

from app.config import get_settings
from app.mock import canned
from app.models.network import Location


async def isochrone_walk(locations: list[Location], minutes: int = 10) -> list[dict]:
    """Walking isochrone for each location.

    Primary: CSDI 3D Pedestrian Route Search (handles overpasses, lifts, MTR concourses).
    Fallback: OSRM on OSM HK extract.
    Returns a list of GeoJSON Polygon features, one per location.
    """
    if get_settings().demo_mode:
        return canned.isochrones_walk(locations, minutes)
    raise NotImplementedError("Wire CSDI 3D Pedestrian Route Search.")


async def isochrone_drive(locations: list[Location], minutes: int = 15) -> list[dict]:
    """Driving isochrone via OSRM on OSM HK extract."""
    if get_settings().demo_mode:
        return canned.isochrones_walk(locations, minutes)  # canned reuse OK for skeleton
    raise NotImplementedError("Wire OSRM driving isochrones.")


async def isochrone_transit(locations: list[Location], minutes: int = 20) -> list[dict]:
    """Transit isochrone — MTR + bus. CSDI iGeoCom + GTFS HK."""
    if get_settings().demo_mode:
        return canned.isochrones_walk(locations, minutes)
    raise NotImplementedError("Wire transit isochrones.")
