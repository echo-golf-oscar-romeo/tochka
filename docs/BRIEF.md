# Brief — preserved verbatim

The original brief from 2026-05-24. Treat this as the source of truth for product scope and submission deadlines. Update only when scope changes; do not edit casually.

---

## Submissions

1. **HKSTP Spatial AI Sandbox PoC Challenge** — proposal + business plan due **26 May 2026 noon** (PowerPoint/PDF, 10–20 pages each, ≤25MB). Banking theme, BOCHK as the corporate partner.

2. **Qwenched #1 (WYB × Alibaba Cloud)** — live demo **30 May 2026** in Causeway Bay, USD$200 Qwen credits, must be powered by Qwen.

Today is 24 May 2026. Same product serves both.

## Product

An agent-driven location intelligence platform. Inspired by Aino (Finnish location intelligence tool — scroll-driven storymap UX, clean cartography). Extends earlier hackathon project SiteSense (github.com/echo-golf-oscar-romeo/SiteSense — basic accessibility analysis for any POI).

Core flow:
- User uploads a CSV of their network of locations (ATMs, branches, stores, anything).
- An orchestrator agent (Qwen) asks 1–2 clarifying questions and decides methodology.
- Specialist agents execute: data cleaning, competitor scraping from Google Maps POIs, isochrone reachability zones, catchment/demand modelling, anomaly detection (under/overperforming locations), expansion opportunity scoring.
- Output: a scroll-driven storymap with concrete next steps.

Generalisable across industries; banking (BOCHK) is the entry use case. Other targets: retail, F&B, healthcare networks, social services (HKCYS routing), real estate.

## Methodology — the orchestrator's four questions

1. **What is the user's network?** Parse uploaded file, identify POI type, geocode rows via CSDI ALS if needed.
2. **What is "demand" in this context?** Choose one:
   - People-driven (banking, retail, F&B) — demand = population × spending × accessibility.
   - Visit-driven (clinics, elderly day care) — demand = registered users + service-area population in target demographic.
   - Flow-driven (ATM, vending) — demand = pedestrian/vehicular flow + dwell.
   - Catchment-fixed (schools, community centres) — demand = bounded population in fixed polygon.
3. **What is the analytical question?** Three archetypes (composable):
   - Diagnose: "How is my current network performing?" → anomaly detection.
   - Expand: "Where should I open next?" → gap analysis, opportunity scoring.
   - Rationalise: "Which to close/merge/resize?" → cannibalisation, redundancy.
4. **What data is needed vs. available?** Build a data plan: user fields → CSDI layers → scraped Google Maps competitors → OSM fallback. Fetch only what the chosen archetype needs.

## Agent tool library

Each tool is a deterministic Python function the LLM picks and calls. The LLM doesn't do math; it picks tools and reads results.

| Category | Tools |
|---|---|
| Geocoding | `als_lookup`, `csdi_location_search` |
| Reachability | `isochrone_walk`, `isochrone_drive`, `isochrone_transit` (OSRM/Valhalla + CSDI 3D Pedestrian Network for HK) |
| Demand surface | `population_in_polygon`, `demographic_breakdown` (CSDI Population Distribution FSDT) |
| Competitive landscape | `competitors_in_radius`, `gmaps_poi_scrape` |
| Spatial joins | `points_in_polygon`, `nearest_neighbor`, `spatial_sql` (DuckDB spatial) |
| Aggregation | `h3_aggregate`, `hex_bin` |
| Modelling | `huff_model`, `gravity_score`, `anomaly_detect` |
| Visualisation | `make_layer`, `make_storymap_section` |

## Storymap output structure — 5 sections, Aino-inspired

1. **Your network at a glance** — map of all uploaded locations + summary KPIs.
2. **Who you reach today** — overlapping isochrones + population captured + competitive landscape.
3. **What's working, what's not** — per-location performance vs expected (Huff/gravity), bottom 3 / top 3.
4. **Where the opportunity is** — gap analysis hex map, ranked top 5 candidate locations with rationale.
5. **Next steps** — concrete actions (open here, close here, restaff here).

Phase 2 — section 6: "When you're under pressure" — hour-by-hour demand vs capacity (spatio-temporal).

## BOCHK pain points → our output

| BOCHK pain | Agent output |
|---|---|
| Branch accessibility & shifting population | Coverage gap map: where 10-min walk catchments miss high-density residential zones; ranked candidate locations using CSDI Population Distribution + 3D Pedestrian Network. |
| ATM cash replenishment routing | ATM clusters by demand profile (commuter peak vs residential weekly cycle); replenishment route templates per cluster. |
| POS spatial patterns & wealth prospecting | POI affinity scoring: density of premium venues (private clubs, specialty hospitals, international schools) around customer transaction hotspots → spatial wealth segmentation layer. |

## CSDI data — assessment criteria explicitly require CSDI Map API + spatial data (50% weighting)

Map APIs: Location Search, Search Nearby, Identify, 3D Pedestrian Route Search, Streetscape 360, Vector Map tiles.

Datasets / FSDTs: Address Lookup Service (ALS), Building footprints, Population Distribution, iGeoCom POIs, 3D Pedestrian Network, 3D Visualisation Map, Slope and Geology.

Portal: portal.csdi.gov.hk. API list: portal.csdi.gov.hk/csdi-webpage/apilist.

## Data inventory

| Layer | Source |
|---|---|
| HK address geocoding | CSDI ALS |
| Building footprints | CSDI Building FSDT / 3D Spatial Data |
| Population distribution | CSDI Population Distribution FSDT (released Mar 2025) |
| Pedestrian network | CSDI 3D Pedestrian Network + Route Search API |
| Government POIs | CSDI iGeoCom |
| Commercial POIs / competitors | Our Google Maps parser (extends SiteSense scraper) |
| Driving network | OSM HK extract |
| MTR | CSDI iGeoCom + 3D Indoor MTR Station Map |
| Streetscape | CSDI Streetscape 360 API |
| 3D city model | CSDI 3D Visualisation Map (now full HK) |
| Topography / slope | CSDI Slope and Geology FSDT |
| User's network | CSV upload |
| Spatio-temporal flows (phase 2) | Mobile signal / transit card / customer-provided |

## Stack

- **LLM** — Qwen (qwen-max via DashScope). Non-negotiable for Qwenched.
- **Agent framework** — Qwen-Agent (Alibaba's own; scores points with Bryan Chu at Qwenched).
- **Backend** — Python + FastAPI + DuckDB-spatial + H3 for hex grids.
- **Isochrones** — CSDI 3D Pedestrian Route Search for walking (narrative win); pre-baked OSRM on HK OSM extract as fallback.
- **Frontend** — Next.js + MapLibre GL (with CSDI Vector Map tiles as basemap — another narrative win).
- **Storymap** — scroll-driven, Mapbox-Storytelling pattern ported to MapLibre.
- **Hosting** — Vercel (frontend), Fly.io or Railway (backend); localhost OK for the live demo if WiFi is unreliable.

## Qwenched demo — 3 minutes, 30 May

- 0:00–0:20: Drag-drop CSV of ~30 BOCHK-shaped branches (BOCHK's actual public branch list).
- 0:20–0:40: Orchestrator asks one clarifying question — "These look like bank branches; optimize for retail customer access, SME access, or both?" — user picks retail.
- 0:40–1:30: Agent log scrolls: cleaning → geocoding via CSDI ALS → 10-min walk isochrones via CSDI 3D Pedestrian Network → competitor pull (HSBC, Hang Seng, StanChart) from our POI DB → population in catchments → anomaly detection.
- 1:30–2:30: Storymap renders section by section: coverage → gap heatmap → top 3 underperformers → top 5 expansion candidates.
- 2:30–3:00: Click an expansion candidate → drill into rationale ("Tsing Yi North — 47K residents within 10-min walk, 0 BOCHK branches, 1 HSBC branch at capacity").

### Honest scope

- **Genuinely agentic**: clarifying question, methodology selection, tool sequencing, narrative writing.
- **Pre-computed** (we say so in the deck, not on stage): competitor POI DB, population grid cached, isochrone graph pre-warmed.
- **Fallback** — if by 28 May the loop isn't stable: ship a scripted demo with a real agent backbone (same UI/orchestrator, predetermined sequence). Judges remember the storymap.

## Pilot district for the demo

Sham Shui Po — high density, queue overload narrative, multiple BOCHK branches, multiple pain points show up at once, visually compelling. Open to changing.
