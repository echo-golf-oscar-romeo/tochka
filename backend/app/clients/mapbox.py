"""Mapbox client — used for isochrone polygons.

Why Mapbox here at all (vs. pure CSDI): CSDI's 3D Pedestrian Route Search
is a route endpoint (point-to-point), not an isochrone endpoint. Building
a polygon from it requires sampling many destinations on a hex grid and
alpha-shaping the reachable set — heavy and brittle for live demo timing.

Mapbox's Isochrone API returns a polygon in a single request. Free tier:
100k requests/month, easily enough for both demo and pilot work.

Endpoint:
    GET https://api.mapbox.com/isochrone/v1/mapbox/{profile}/{lng},{lat}
        ?contours_minutes=10&polygons=true&access_token=<token>

`profile` is one of: walking, cycling, driving, driving-traffic.
Response: GeoJSON FeatureCollection with Polygon features, one per contour.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import get_settings

log = logging.getLogger(__name__)

_BASE_URL = "https://api.mapbox.com/isochrone/v1/mapbox"


class MapboxClient:
    def __init__(self) -> None:
        s = get_settings()
        self.token = s.mapbox_access_token
        self._client = httpx.AsyncClient(timeout=10.0)

    @property
    def has_token(self) -> bool:
        return bool(self.token)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def walking_isochrone(self, lat: float, lng: float,
                                minutes: int = 10) -> dict[str, Any]:
        return await self._isochrone("walking", lat, lng, minutes)

    async def driving_isochrone(self, lat: float, lng: float,
                                minutes: int = 15) -> dict[str, Any]:
        return await self._isochrone("driving", lat, lng, minutes)

    async def _isochrone(self, profile: str, lat: float, lng: float,
                         minutes: int) -> dict[str, Any]:
        if not self.token:
            raise RuntimeError("MAPBOX_ACCESS_TOKEN is not set.")
        url = f"{_BASE_URL}/{profile}/{lng},{lat}"
        params = {
            "contours_minutes": str(minutes),
            "polygons": "true",
            "denoise": "1",
            "generalize": "10",
            "access_token": self.token,
        }
        r = await self._client.get(url, params=params)
        r.raise_for_status()
        data = r.json()
        features = data.get("features") or []
        if not features:
            raise ValueError("Mapbox returned no isochrone features.")
        # Return the single contour (we requested only one).
        return features[0]


_singleton: MapboxClient | None = None


def get_mapbox() -> MapboxClient:
    global _singleton
    if _singleton is None:
        _singleton = MapboxClient()
    return _singleton
