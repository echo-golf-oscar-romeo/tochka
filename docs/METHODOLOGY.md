# Methodology — the orchestrator's decision flow

The orchestrator is a Qwen agent that, given a CSV upload and a thin user intent, answers four questions in order. Each answer narrows the tool set and the data plan. The orchestrator does not do math; it picks tools, reads results, and writes narrative.

## Question 1 — What is the user's network?

Inputs: uploaded CSV, optional industry hint.

Steps:
1. Parse CSV headers → `Network` schema.
2. Classify POI type. Heuristics on column names and string content:
   - "branch", "atm" → bank network.
   - "store", "shop", "outlet" → retail.
   - "clinic", "centre" → healthcare / social.
3. Geocode rows missing lat/lng via CSDI ALS. Confidence ≥ 0.7 required; flag the rest for review.

Output: `Network` object — typed locations, bounding box, geocoding confidence summary.

## Question 2 — What is "demand"?

The four demand archetypes:

| Archetype | When it fits | Primary signal |
|---|---|---|
| People-driven | Banking, retail, F&B | Population × spending × accessibility |
| Visit-driven | Clinics, elderly day care | Registered users + service-area population in target demo |
| Flow-driven | ATMs, vending | Pedestrian / vehicular flow + dwell |
| Catchment-fixed | Schools, community centres | Bounded population in fixed polygon |

Decision is rule-based on POI type + 1 clarifying question. Example: bank network → ask "retail customer access, SME access, or both" → retail = people-driven, SME = flow-driven + premium POI affinity.

## Question 3 — What is the analytical question?

Three archetypes. Composable.

| Archetype | Question | Lead tools |
|---|---|---|
| Diagnose | How is my current network performing? | `huff_model` or `gravity_score` → `anomaly_detect` |
| Expand | Where should I open next? | gap analysis on `h3_aggregate` + `population_in_polygon` − existing isochrones |
| Rationalise | Which to close / merge / resize? | `huff_model` cannibalisation, `nearest_neighbor` redundancy |

Default for BOCHK demo: **Diagnose + Expand**.

## Question 4 — What data is needed vs available?

Build a data plan, fetch only what the chosen archetype needs.

Resolution order per layer:
1. User-provided fields.
2. CSDI Map APIs / FSDTs.
3. Parsed Google Maps POIs (our DB).
4. OSM HK extract as last resort.

The plan is a list of `{layer, source, status}`. Status starts `requested`, moves to `cached` after the tool returns. If a layer is unavailable, the orchestrator either substitutes a proxy or trims the analysis and explains the gap in the storymap.

## Tool sequencing

The orchestrator writes a short plan (5–8 steps), then executes one tool at a time, reading the result and deciding the next step. After all tool calls complete, it composes the storymap by calling `make_storymap_section` once per section.

## Failure modes the orchestrator handles

- **Geocoding < 70% confident**: ask user to confirm flagged rows before proceeding.
- **No competitor data in district**: fall back to OSM `amenity=bank`, mark layer as low-confidence.
- **Population grid stale**: warn in narrative, proceed.
- **Demo mode**: every tool returns canned data from `app/mock/canned.py`. Determinism over realism.
