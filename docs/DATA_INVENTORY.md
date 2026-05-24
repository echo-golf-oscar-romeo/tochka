# Data inventory

What we use, where it comes from, current status. Update the status column as datasets are wired in.

## CSDI Map APIs

| API | Used for | Status |
|---|---|---|
| Location Search | Free-text → coordinates | not wired |
| Search Nearby | Find POIs in radius for landmarks, banks, hospitals | not wired |
| Identify | Click on map → attribute lookup | not wired |
| 3D Pedestrian Route Search | True walk isochrones | **deferred** — route-only endpoint; would need grid-sampling to produce polygons. See CSDI_API_NOTES.md. Mapbox carries primary isochrones for now. |
| Streetscape 360 | Storymap supporting visuals | not wired |
| Vector Map (tiles) | Basemap for MapLibre | **wired** — frontend pulls style URL from env. |

## CSDI datasets / FSDTs

| Dataset | Used for | Status |
|---|---|---|
| Address Lookup Service (ALS) | Address → coordinates for CSV upload | **wired** — `clients/csdi.py::als_lookup`. Confidence-mapped, canned fallback on miss. |
| Building footprints | Storymap depth, hotspot context | not wired |
| Population Distribution (Mar 2025) | Demand surface for people-driven archetype | not wired |
| iGeoCom POIs | Government POIs, MTR stations, landmarks | not wired |
| 3D Pedestrian Network | Underpins Route Search | deferred (see above) |
| 3D Visualisation Map | Optional 3D context in storymap | not wired |
| Slope and Geology | Accessibility analysis for elderly-focused networks | not wired |

## Non-CSDI

| Source | Used for | Status |
|---|---|---|
| **OpenStreetMap (via Overpass)** | Competitor banks + ATMs across HK | **wired** — `scripts/fetch_osm_banks.py` pulls 1,279 POIs (1,085 banks + 194 ATMs); `tools/competitors.py` queries the JSON. File is gitignored. |
| **Mapbox Isochrone API** | Walking + driving isochrone polygons | **wired** — `clients/mapbox.py`. Requires `MAPBOX_ACCESS_TOKEN`. Free tier covers demo + pilot. |
| OSM HK PBF extract | Driving isochrones via OSRM (alternate path) | not wired — kept as future fallback if Mapbox limits become a problem |
| Our Google Maps POI parser (extends SiteSense) | Additional commercial POIs (non-bank) | parser exists, DB schema not finalised; not wired in this backend yet |
| User CSV upload | The network itself | **wired** — required: `name` + `(lat,lng OR address)`; optional: `capacity`, `actual_volume` (many aliases accepted) |
| Mobile signal / transit card (phase 2) | Spatio-temporal demand | not in scope for May submissions |

## Sample data shipped with the repo

- `backend/app/mock/sample_branches.csv` — 15 BOCHK-shaped rows including capacity + daily_visitors for branches (ATMs leave them blank). Use this for testing the happy path. Real demo uses the actual BOCHK public branch list dropped into `data/pilot/bochk_branches.csv` (gitignored).
- Canned tool returns in `backend/app/mock/canned.py` — deterministic outputs for every tool when `DEMO_MODE=true`.

## Behaviour modes

| Setting | Effect |
|---|---|
| `DEMO_MODE=true` | All spatial tools short-circuit to canned data. LLM calls unaffected. Use for the live Qwenched demo. |
| `DEMO_MODE=false` | Tools try the real source first; on failure fall back to canned. Mapbox / ALS / OSM JSON all follow this pattern. |
| `DASHSCOPE_API_KEY` set | Real Qwen for clarify + narrative. Independent of `DEMO_MODE`. |
| `MAPBOX_ACCESS_TOKEN` set | Real isochrones. Without token + `DEMO_MODE=false` → silent canned fallback. |

## Open questions

- Population Distribution FSDT format and projection — verify before writing `population_in_polygon`.
- Rate limits on Mapbox isochrones if a single demo uploads ~190 BOCHK branches (still under 100k/mo, but ~190 calls in ~10s).
- Whether CSDI plans to publish a true reachability/isochrone endpoint that would replace Mapbox.
