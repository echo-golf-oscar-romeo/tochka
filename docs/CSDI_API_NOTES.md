# CSDI API notes

A living scratchpad for quirks discovered while integrating CSDI. Add rather than rewrite; future-us needs the history.

## Portal entry points

- Main portal: https://portal.csdi.gov.hk
- API list: https://portal.csdi.gov.hk/csdi-webpage/apilist
- Vector basemap style: https://mapapi.geodata.gov.hk/gs/api/v1.0.0/styleSheet/vector (no key; pin in `.env`).
- ALS service: https://www.als.gov.hk

## Authentication

As of 2026-05-24, most CSDI Map APIs and FSDT downloads are anonymous. **Verify per-endpoint before the proposal submission** — if a key turns out to be needed for 3D Pedestrian Route Search or Search Nearby at production volumes, we register early in the sandbox phase. Set `CSDI_API_KEY` in `.env` once known.

## Endpoint-by-endpoint

> Fill in as we wire each one in `backend/app/clients/csdi.py`.

### Address Lookup Service (ALS)
- Endpoint: TBD (search the portal).
- Request: free-text or structured address.
- Response: array of candidates with coordinates and confidence.
- Confidence threshold for auto-accept: 0.7. Below: flag for user confirmation.
- Rate limits: TBD.
- Notes: HK addresses are messy. Romanised, Chinese, mixed, with floor/unit. ALS handles most.

### Location Search
- Endpoint: TBD.
- Request: free-text query, optional bbox.
- Response: TBD.
- Notes: TBD.

### Search Nearby
- Endpoint: TBD.
- Notes: useful for finding government POIs near a candidate site.

### Identify
- Endpoint: TBD.
- Notes: click-on-map → attributes. Storymap drill-in.

### 3D Pedestrian Route Search
- Endpoint: TBD.
- Request: origin lat/lng + max walking time/distance.
- Response: routes / reachable nodes. We turn these into isochrone polygons via alpha-shape.
- Notes: this is the *narrative win* — true walking catchments respecting overpasses, lifts, MTR concourses. If the API only returns point-to-point routes, we sample destinations on a hex grid and build the catchment ourselves.

### Streetscape 360
- Endpoint: TBD.
- Notes: for storymap section depth. Use sparingly — heavy.

### Vector Map tiles
- Style URL is public. MapLibre points at it directly; no auth.
- Glyphs / sprites: verify they resolve through the same host (style URL usually includes absolute refs).

## FSDT downloads

### Population Distribution (Mar 2025)
- Location: TBD on portal.
- Format: TBD (geopackage / shapefile / parquet?).
- Schema: TBD (likely a grid with totals + age breakdowns).
- Pre-load into DuckDB-spatial; query via H3 in `population_in_polygon`.

### Building footprints
- Location: TBD.
- Format: TBD.

### iGeoCom POIs
- Location: TBD.
- Categories: government offices, MTR, schools, hospitals — useful for both demand and constraints.

### Slope and Geology
- Location: TBD.
- Use case: elderly-focused networks where steep streets reduce effective catchment.

## Caching strategy

Every CSDI response is cached in DuckDB keyed by `(endpoint, params_hash)`. Stale TTL: 30 days for static layers, 24 hours for ALS lookups. Demo mode skips the network entirely and reads from `app/mock/canned.py`.

## Failure modes seen

> Fill as encountered.

- _none yet_
