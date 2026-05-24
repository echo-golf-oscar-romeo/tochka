"""Geocoding tools — turn addresses into coordinates."""

from __future__ import annotations

import logging

from app.clients.csdi import get_csdi
from app.config import get_settings
from app.mock import canned
from app.models.network import Location

log = logging.getLogger(__name__)


async def als_lookup(locations: list[Location]) -> list[Location]:
    """Geocode rows that are missing (lat, lng) using CSDI ALS.

    Strategy:
    - DEMO_MODE=true → never call the network; canned coords.
    - Else, for each row with an address but no coordinates, hit ALS.
    - On any failure (network, parse, no candidate), fall back to canned
      coords so the rest of the pipeline still runs. Confidence is recorded
      truthfully so the orchestrator can warn in the narrative when many
      rows are low-confidence.

    Mutates and returns the input list.
    """
    s = get_settings()
    missing = [loc for loc in locations if loc.lat is None or loc.lng is None]
    if not missing:
        return locations

    if s.demo_mode:
        canned.geocode(missing)
        return locations

    csdi = get_csdi()
    still_missing: list[Location] = []
    for loc in missing:
        if not loc.address:
            # Nothing to query — leave for canned fallback below.
            still_missing.append(loc)
            continue
        try:
            results = await csdi.als_lookup(loc.address, n=3)
        except Exception as e:
            log.warning("ALS failed for %s (%r): %s", loc.name, loc.address, e)
            still_missing.append(loc)
            continue
        if not results:
            log.info("ALS no match for %r (%s)", loc.address, loc.name)
            still_missing.append(loc)
            continue
        top = results[0]
        loc.lat = top["lat"]
        loc.lng = top["lng"]
        loc.geocoded = True
        loc.geocode_confidence = top["confidence"]

    if still_missing:
        log.info("Canned-geocoding %d rows ALS couldn't resolve.", len(still_missing))
        canned.geocode(still_missing)
    return locations


async def csdi_location_search(query: str, bbox: tuple[float, float, float, float] | None = None) -> list[dict]:
    """Free-text → coordinates via CSDI Location Search. Stubbed."""
    if get_settings().demo_mode:
        return canned.location_search(query)
    raise NotImplementedError("Wire CSDI Location Search.")
