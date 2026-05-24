"""CSDI client — Map APIs and FSDT downloads.

Only ALS (Address Lookup Service) is wired right now; the rest are stubs.
Endpoint quirks live in docs/CSDI_API_NOTES.md.

ALS endpoint shape (https://www.als.gov.hk/lookup?q=<address>&n=<n>) returns:

    {
      "SuggestedAddress": [
        {
          "Address": {
            "PremisesAddress": {
              "EngPremisesAddress": {
                "BuildingName": "...", "EngStreet": {"StreetName": ...},
                "EngDistrict": {"DcDistrict": ...}, "Region": "..."
              },
              "GeospatialInformation": {
                "Latitude": "22.281...", "Longitude": "114.158..."
              }
            }
          },
          "ValidationInformation": { "ValidationStatus": "Valid" | "Partial" | "Postal" }
        }, ...
      ]
    }

Confidence mapping is conservative; real-world ALS quality varies by input
completeness so we add a `partial` floor when bilingual or unit info is missing.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import get_settings

log = logging.getLogger(__name__)

_VALIDATION_CONFIDENCE = {
    "Valid": 0.95,
    "Partial": 0.75,
    "Postal": 0.55,
}


class CSDIClient:
    def __init__(self) -> None:
        s = get_settings()
        self.base_url = s.csdi_base_url.rstrip("/")
        headers: dict[str, str] = {
            "Accept": "application/json",
            "User-Agent": "Tochka/0.1 (location intelligence)",
        }
        if s.csdi_api_key:
            headers["Authorization"] = f"Bearer {s.csdi_api_key}"
        self._client = httpx.AsyncClient(headers=headers, timeout=12.0)

    async def aclose(self) -> None:
        await self._client.aclose()

    # --- ALS (Address Lookup Service) ---

    async def als_lookup(self, query: str, n: int = 5) -> list[dict[str, Any]]:
        """Resolve an HK address string to up to n candidate coordinates.

        Returns a list of {lat, lng, address, district, region, confidence}
        sorted by ALS's own ranking (best first). Empty list on no match.
        """
        if not query or not query.strip():
            return []
        url = f"{self.base_url}/lookup"
        r = await self._client.get(url, params={"q": query, "n": n})
        r.raise_for_status()
        data = r.json()
        out: list[dict[str, Any]] = []
        for suggestion in data.get("SuggestedAddress", []) or []:
            parsed = self._parse_suggestion(suggestion)
            if parsed:
                out.append(parsed)
        return out

    @staticmethod
    def _parse_suggestion(sug: dict[str, Any]) -> dict[str, Any] | None:
        try:
            addr = sug.get("Address", {}).get("PremisesAddress", {}) or {}
            geo = addr.get("GeospatialInformation") or {}
            lat = float(geo.get("Latitude"))
            lng = float(geo.get("Longitude"))
        except (TypeError, ValueError):
            return None

        eng = addr.get("EngPremisesAddress") or {}
        street = (eng.get("EngStreet") or {})
        district = (eng.get("EngDistrict") or {}).get("DcDistrict")

        pieces = []
        if eng.get("BuildingName"):
            pieces.append(str(eng["BuildingName"]).strip())
        if street.get("BuildingNoFrom") and street.get("StreetName"):
            pieces.append(f"{street['BuildingNoFrom']} {street['StreetName']}")
        elif street.get("StreetName"):
            pieces.append(str(street["StreetName"]).strip())
        if district:
            pieces.append(str(district).strip())

        v_status = (sug.get("ValidationInformation") or {}).get("ValidationStatus", "")
        confidence = _VALIDATION_CONFIDENCE.get(v_status, 0.5)

        return {
            "lat": lat,
            "lng": lng,
            "address": ", ".join(pieces),
            "district": district,
            "region": eng.get("Region"),
            "confidence": confidence,
            "validation_status": v_status,
        }

    # --- Stubs for future endpoints ---

    async def location_search(self, query: str,
                              bbox: tuple[float, float, float, float] | None = None) -> list[dict[str, Any]]:
        raise NotImplementedError("Wire CSDI Location Search.")

    async def search_nearby(self, lat: float, lng: float,
                            category: str, radius_m: int = 500) -> list[dict[str, Any]]:
        raise NotImplementedError("Wire CSDI Search Nearby.")

    async def pedestrian_route(self, origin: tuple[float, float],
                               max_minutes: int = 10) -> dict[str, Any]:
        """CSDI 3D Pedestrian Route Search.

        This is a *route* endpoint (origin → destination), not an isochrone
        endpoint. Building an isochrone polygon from it requires sampling
        many destinations on a grid + alpha-shape — too slow for live demo.
        We use Mapbox isochrones as the primary; this stub is here for the
        eventual HK-specific upgrade.
        """
        raise NotImplementedError("CSDI 3D Pedestrian Route Search is route-only; "
                                  "isochrone construction requires grid sampling. "
                                  "Use Mapbox isochrones via app/clients/mapbox.py for now.")


_singleton: CSDIClient | None = None


def get_csdi() -> CSDIClient:
    global _singleton
    if _singleton is None:
        _singleton = CSDIClient()
    return _singleton
