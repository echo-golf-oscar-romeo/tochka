"""Geocoding tools — turn addresses into coordinates."""

from __future__ import annotations

from app.config import get_settings
from app.mock import canned
from app.models.network import Location


async def als_lookup(locations: list[Location]) -> list[Location]:
    """Geocode locations that are missing (lat, lng). Mutates in place.

    Source: CSDI Address Lookup Service (ALS). Confidence < 0.7 → flag for review.
    Demo mode: every input is geocoded with high confidence using canned coords.
    """
    if get_settings().demo_mode:
        canned.geocode(locations)
        return locations
    # TODO: real ALS HTTP call via app.clients.csdi
    raise NotImplementedError("Wire CSDI ALS in app/clients/csdi.py")


async def csdi_location_search(query: str, bbox: tuple[float, float, float, float] | None = None) -> list[dict]:
    """Free-text → coordinates via CSDI Location Search."""
    if get_settings().demo_mode:
        return canned.location_search(query)
    raise NotImplementedError("Wire CSDI Location Search.")
