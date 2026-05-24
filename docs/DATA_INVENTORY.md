# Data inventory

What we use, where it comes from, current status. Update the status column as datasets are wired in.

## CSDI Map APIs

| API | Used for | Status |
|---|---|---|
| Location Search | Free-text → coordinates | not wired |
| Search Nearby | Find POIs in radius for landmarks, banks, hospitals | not wired |
| Identify | Click on map → attribute lookup | not wired |
| 3D Pedestrian Route Search | True walk isochrones | not wired |
| Streetscape 360 | Storymap supporting visuals | not wired |
| Vector Map (tiles) | Basemap for MapLibre | URL pinned in `.env.example`, frontend uses it |

## CSDI datasets / FSDTs

| Dataset | Used for | Status |
|---|---|---|
| Address Lookup Service (ALS) | Address → coordinates for CSV upload | not wired |
| Building footprints | Storymap depth, hotspot context | not wired |
| Population Distribution (Mar 2025) | Demand surface for people-driven archetype | not wired |
| iGeoCom POIs | Government POIs, MTR stations, landmarks | not wired |
| 3D Pedestrian Network | Underpins Route Search | downloaded by Route Search call |
| 3D Visualisation Map | Optional 3D context in storymap | not wired |
| Slope and Geology | Accessibility analysis for elderly-focused networks | not wired |

## Non-CSDI

| Source | Used for | Status |
|---|---|---|
| Our Google Maps POI parser (extends SiteSense) | Competitors and commercial anchors | parser exists, DB schema not finalised |
| OSM HK extract (Geofabrik) | Driving isochrones via OSRM, fallback for `amenity=bank` | not wired |
| User CSV upload | The network itself | wired in skeleton |
| Mobile signal / transit card (phase 2) | Spatio-temporal demand | not in scope for May submissions |

## Sample data shipped with the repo

- `backend/app/mock/sample_branches.csv` — ~10 BOCHK-shaped rows for testing happy path. Real demo uses the actual BOCHK public branch list, placed in `data/pilot/bochk_branches.csv` (gitignored).
- Canned tool returns in `backend/app/mock/canned.py` — deterministic outputs for every tool when `DEMO_MODE=true`.

## Open questions

- Does CSDI 3D Pedestrian Route Search require registration? Confirm against portal docs before 2026-05-26.
- Population Distribution FSDT format and projection — verify before writing `population_in_polygon`.
- Rate limits on Location Search and Search Nearby. Cache aggressively in DuckDB.
