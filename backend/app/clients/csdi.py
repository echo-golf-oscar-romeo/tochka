"""CSDI client — Map APIs and FSDT downloads.

Skeleton only. Real endpoints are TBD; see docs/CSDI_API_NOTES.md for what we know.
Use one shared httpx.AsyncClient, retry with exponential backoff, cache responses
in DuckDB by (endpoint, params_hash).
"""

from __future__ import annotations

from typing import Any

import httpx

from app.config import get_settings


class CSDIClient:
    def __init__(self) -> None:
        s = get_settings()
        self.base_url = s.csdi_base_url
        headers: dict[str, str] = {}
        if s.csdi_api_key:
            headers["Authorization"] = f"Bearer {s.csdi_api_key}"
        self._client = httpx.AsyncClient(base_url=self.base_url, headers=headers, timeout=15.0)

    async def aclose(self) -> None:
        await self._client.aclose()

    # --- Map APIs ---

    async def als_lookup(self, query: str) -> list[dict[str, Any]]:
        """Address Lookup Service. Endpoint TBD; see docs/CSDI_API_NOTES.md."""
        raise NotImplementedError

    async def location_search(self, query: str,
                              bbox: tuple[float, float, float, float] | None = None) -> list[dict[str, Any]]:
        raise NotImplementedError

    async def search_nearby(self, lat: float, lng: float,
                            category: str, radius_m: int = 500) -> list[dict[str, Any]]:
        raise NotImplementedError

    async def pedestrian_route(self, origin: tuple[float, float],
                               max_minutes: int = 10) -> dict[str, Any]:
        """3D Pedestrian Route Search. Returns reachable nodes or a route graph."""
        raise NotImplementedError

    # --- FSDT downloads ---

    async def fetch_population_distribution(self, dest_path: str) -> str:
        """Download Population Distribution FSDT package to dest_path."""
        raise NotImplementedError


_singleton: CSDIClient | None = None


def get_csdi() -> CSDIClient:
    global _singleton
    if _singleton is None:
        _singleton = CSDIClient()
    return _singleton
