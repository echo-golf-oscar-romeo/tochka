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

import json
import logging
from pathlib import Path
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

    # --- Location Search (map.gov.hk GeoData Store) ---

    async def location_search(self, query: str, n: int = 20) -> list[dict[str, Any]]:
        """Free-text place / landmark / building search across Hong Kong.

        Backed by the GeoData Store locationSearch API. It returns x/y in the
        HK1980 Grid (EPSG:2326); we convert to WGS84 lat/lng via DuckDB.
        Returns [{name, name_zh, address, district, lat, lng}] (best first).
        """
        if not query or not query.strip():
            return []
        s = get_settings()
        try:
            r = await self._client.get(
                s.csdi_locationsearch_url, params={"q": query.strip()},
            )
            r.raise_for_status()
            rows = r.json()
        except (httpx.HTTPError, ValueError) as e:
            log.warning("CSDI locationSearch failed for %r: %s", query, e)
            return []
        if not isinstance(rows, list) or not rows:
            return []
        rows = rows[: max(1, n)]
        # Batch-convert EPSG:2326 → WGS84 (lng, lat).
        from app.clients.ddb import hk1980_to_wgs84  # local import avoids cycle
        xy = [(row.get("x"), row.get("y")) for row in rows]
        lnglat = hk1980_to_wgs84([(x, y) for x, y in xy if x is not None and y is not None])
        out: list[dict[str, Any]] = []
        for row, (lng, lat) in zip(rows, lnglat, strict=False):
            if lng is None or lat is None:
                continue
            out.append({
                "name": row.get("nameEN") or row.get("nameZH") or "",
                "name_zh": row.get("nameZH"),
                "address": row.get("addressEN") or "",
                "district": row.get("districtEN"),
                "lat": lat,
                "lng": lng,
            })
        return out

    # --- Search Nearby (against the loaded CSDI POI table) ---

    async def search_nearby(self, lat: float, lng: float,
                            category: str | None = None,
                            radius_m: int = 500, limit: int = 50) -> list[dict[str, Any]]:
        """POIs from the real CSDI iGeoCom dataset within radius_m of a point.

        Queries the local `csdi_pois` DuckDB table (loaded from the committed
        parquet) — no live call needed. Optional category filter matches the
        friendly `category` column (school, medical, transport, …) case-insensitively.
        """
        from app.clients.ddb import ensure_csdi_pois_loaded, get_duckdb
        conn = get_duckdb()
        if not ensure_csdi_pois_loaded(conn):
            return []
        where = ["ST_Distance_Spheroid(ST_Point(lat, lng), ST_Point(?, ?)) <= ?"]
        params: list[Any] = [float(lat), float(lng), int(radius_m)]
        if category:
            where.append("LOWER(category) = LOWER(?)")
            params.append(category)
        sql = (
            "SELECT geonameid, name_en, name_zh, class, type, category, lat, lng, "
            "district_en, address_en, "
            "ROUND(ST_Distance_Spheroid(ST_Point(lat, lng), ST_Point(?, ?)), 1) AS distance_m "
            "FROM csdi_pois WHERE " + " AND ".join(where) +
            " ORDER BY distance_m LIMIT ?"
        )
        params = [float(lat), float(lng)] + params + [int(limit)]
        try:
            rs = conn.execute(sql, params)
            cols = [d[0] for d in rs.description]
            return [dict(zip(cols, row, strict=False)) for row in rs.fetchall()]
        except Exception as e:  # noqa: BLE001
            log.warning("CSDI search_nearby failed: %s", e)
            return []

    # --- District boundaries (committed GeoJSON) ---

    def district_boundaries(self) -> dict[str, Any]:
        """Return the 18 HK District Council district boundaries as a GeoJSON
        FeatureCollection (loaded from the committed file). {} if missing."""
        s = get_settings()
        path = Path(s.hk_districts_path)
        if not path.is_absolute():
            path = (Path(__file__).resolve().parents[3] / path).resolve()
        if not path.exists():
            log.warning("HK districts GeoJSON missing at %s. Run scripts/fetch_csdi.py.", path)
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            log.warning("Failed to read HK districts GeoJSON: %s", e)
            return {}


_singleton: CSDIClient | None = None


def get_csdi() -> CSDIClient:
    global _singleton
    if _singleton is None:
        _singleton = CSDIClient()
    return _singleton
