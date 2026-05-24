"""Competitive-landscape tools — competitor banks, retail anchors."""

from __future__ import annotations

from app.config import get_settings
from app.mock import canned
from app.models.network import Location


async def competitors_in_radius(locations: list[Location], radius_m: int = 500,
                                categories: tuple[str, ...] = ("bank",)) -> list[dict]:
    """Find competitor POIs within `radius_m` of each user location.

    Primary: our parsed Google Maps POI database in DuckDB.
    Fallback: OSM `amenity=bank` from the HK extract.
    """
    if get_settings().demo_mode:
        return canned.competitors_in_radius(locations, radius_m)
    raise NotImplementedError("Wire DuckDB POI query / OSM fallback.")


async def gmaps_poi_scrape(bbox: tuple[float, float, float, float],
                           category: str = "bank") -> list[dict]:
    """On-demand Google Maps POI extraction for a bbox.

    Heavy. Use sparingly; cache to DuckDB. Implementation extends the SiteSense
    scraper at github.com/echo-golf-oscar-romeo/SiteSense.
    """
    if get_settings().demo_mode:
        return canned.gmaps_pois(bbox, category)
    raise NotImplementedError("Wire the SiteSense-derived gmaps parser.")
