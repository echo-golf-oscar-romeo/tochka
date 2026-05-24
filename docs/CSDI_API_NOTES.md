# CSDI API notes

A living scratchpad for quirks discovered while integrating CSDI. Add rather than rewrite; future-us needs the history.

## Portal entry points

- Main portal: https://portal.csdi.gov.hk
- API list: https://portal.csdi.gov.hk/csdi-webpage/apilist
- Vector basemap style: https://mapapi.geodata.gov.hk/gs/api/v1.0.0/styleSheet/vector (no key; pin in `.env`).
- ALS service: https://www.als.gov.hk

## Authentication

As of 2026-05-24, most CSDI Map APIs and FSDT downloads are anonymous. **Verify per-endpoint before the proposal submission** — if a key turns out to be needed for endpoints we add later, register early in the sandbox phase. Set `CSDI_API_KEY` in `.env` once known.

## Endpoint-by-endpoint

### Address Lookup Service (ALS) — **wired** ✓
- Endpoint: `GET https://www.als.gov.hk/lookup?q=<address>&n=<n>`
- Accept: `application/json` (without this header you get XML)
- Response: `SuggestedAddress[]` with `Address.PremisesAddress.{EngPremisesAddress, GeospatialInformation}` and `ValidationInformation.ValidationStatus` ∈ {Valid, Partial, Postal}.
- Confidence mapping in `clients/csdi.py::_VALIDATION_CONFIDENCE`: Valid → 0.95, Partial → 0.75, Postal → 0.55, fallback → 0.5. Threshold for auto-accept: 0.7.
- HK addresses are messy. Romanised, Chinese, mixed, with floor/unit. ALS handles most; failures fall back to canned coords so the pipeline keeps running.
- Rate limits: not documented; we don't currently throttle. Hit rates should be modest (uploaded CSVs only, not per-request).

### Location Search — not wired
- Endpoint: TBD.
- Use case: free-text → coordinates (e.g. "Tsing Yi MTR"). Useful for landmark resolution that ALS misses.

### Search Nearby — not wired
- Endpoint: TBD.
- Use case: gov POIs near a candidate site for the storymap's drill-in.

### Identify — not wired
- Endpoint: TBD.
- Use case: click-on-map → attributes for storymap interactions.

### 3D Pedestrian Route Search — **deferred** ⚠️
- This is a **route** endpoint (origin → destination), not an isochrone endpoint.
- To build an isochrone polygon from it: sample N destinations on a hex grid around the origin, call route-to-each, alpha-shape the reachable set. That's ~100 calls per branch → too brittle for the live demo timing budget.
- **Current design call**: use Mapbox Isochrone API as primary (single call per origin → polygon). See `backend/app/clients/mapbox.py`. The CSDI route endpoint stays a stub in `clients/csdi.py::pedestrian_route` until we either implement the grid-sampling builder or CSDI exposes a true reachability endpoint.
- The grid-sampling approach is the eventual "100% CSDI" upgrade — worth doing during the sandbox phase for the HKSTP narrative.

### Streetscape 360 — not wired
- Endpoint: TBD.
- Use case: storymap drill-in panels with real photography.

### Vector Map tiles — **broken upstream** ⚠️
- The previously documented style URL
  `https://mapapi.geodata.gov.hk/gs/api/v1.0.0/styleSheet/vector` currently
  returns 404 ("Resource not found"). All path variants I tried also 404.
  CSDI appears to have changed their API surface.
- **Current workaround**: Carto Positron
  (`https://basemaps.cartocdn.com/gl/positron-gl-style/style.json`) is the
  default basemap. Same Aino-style aesthetic, cross-origin enabled, no auth.
  Configurable via `NEXT_PUBLIC_BASEMAP_STYLE`.
- When CSDI republishes a working vector style URL, set
  `NEXT_PUBLIC_BASEMAP_STYLE` to point at it; no code changes needed.

## FSDT downloads

### Population Distribution (Mar 2025) — not wired
- Location: TBD on portal.
- Format: TBD (geopackage / shapefile / parquet?).
- Pre-load into DuckDB-spatial; query via H3 in `population_in_polygon`.

### Building footprints — not wired
- Location: TBD.

### iGeoCom POIs — not wired
- Categories: government offices, MTR, schools, hospitals. Useful for both demand and constraints.

### Slope and Geology — not wired
- Use case: elderly-focused networks where steep streets reduce effective catchment.

## Non-CSDI: pre-fetched OSM data — **wired** ✓
- Banks + ATMs across HK pulled via Overpass into `data/osm/banks_atms_hk.json` (gitignored).
- Generator: `backend/scripts/fetch_osm_banks.py`. Single Overpass query, ~5–15s.
- Consumer: `backend/app/tools/competitors.py::competitors_in_radius` — equirectangular distance scan, in-memory cache via `lru_cache`. ~1.3k POIs is small enough that a spatial index would be over-engineering for now.

## Non-CSDI: Mapbox Isochrone — **wired** ✓
- Single endpoint per request: `https://api.mapbox.com/isochrone/v1/mapbox/{profile}/{lng},{lat}?contours_minutes=N&polygons=true&access_token=...`.
- Free tier: 100k requests/month — generous for both demo and pilot.
- Token in `MAPBOX_ACCESS_TOKEN` (no public exposure; only used server-side).

## Caching strategy

For ALS and other CSDI endpoints once wired, plan: cache responses in DuckDB keyed by `(endpoint, params_hash)`. Stale TTL: 30 days for static layers, 24 hours for ALS lookups. `DEMO_MODE=true` skips the network entirely and reads from `app/mock/canned.py`.

## Fallback chain (when DEMO_MODE=false)

Every spatial tool follows the same pattern:

1. **Try real API** (CSDI / Mapbox / pre-fetched OSM).
2. On any failure (network, parse, no candidate, missing token / data file) — **log warning and fall back to canned**. The pipeline continues.
3. `DEMO_MODE=true` short-circuits step 1 entirely.

This makes the live demo robust against venue WiFi without sacrificing real-data behaviour the rest of the time.

## Failure modes seen

> Fill as encountered.

- Overpass returns 406 on requests without a real `User-Agent` header — fixed in `scripts/fetch_osm_banks.py`.
- Windows cp1252 console crashes on CJK brand names when printing — guarded with `_safe_print` in the same script.
