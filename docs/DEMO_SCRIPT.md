# Qwenched demo — 3 minutes, 2026-05-30, Causeway Bay

Audience: WYB + Alibaba Cloud judges, including Bryan Chu. The decisive narrative beats: an agent makes a real methodology decision, the storymap shows a concrete recommendation, the CSDI angle is on screen.

## On the laptop before walking on stage

- Backend running locally with `DEMO_MODE=true`.
- Frontend on `http://localhost:3000`.
- Sample CSV `data/pilot/bochk_branches.csv` ready to drag.
- A second monitor or projector showing the browser at 1440×900.
- Network off if WiFi flaky — demo mode does not need it.

## Beat-by-beat

| Time | On screen | What you say |
|---|---|---|
| 0:00–0:20 | Upload screen. Drag `bochk_branches.csv` (~30 BOCHK branches). | "BOCHK has ~190 branches across Hong Kong. The network was sized for a population that has shifted. Here are 30 of them as a CSV." |
| 0:20–0:40 | Orchestrator clarifying question dialog: "These look like bank branches. Optimise for retail customer access, SME access, or both?" Click **Retail**. | "The orchestrator agent — running on Qwen — recognises bank branches, and asks the one question it needs to pick a methodology." |
| 0:40–1:30 | Agent log streams: parse → classify → geocode via CSDI ALS → 10-min walk isochrones via CSDI 3D Pedestrian Network → competitor pull (HSBC, Hang Seng, Standard Chartered) → population in catchment → anomaly detection. | "It's now sequencing tools. Notice the data sources: CSDI's 3D Pedestrian Network gives real walking catchments — not crow-flies circles. Population from the Mar 2025 FSDT. Competitors from our Google Maps parser." |
| 1:30–2:00 | Storymap section 1 appears: "Your network at a glance." Then section 2: "Who you reach today" with overlapping isochrones. | "Section 1 — the network. Section 2 — who they actually reach in a 10-minute walk." |
| 2:00–2:30 | Section 3: "What's working, what's not." Bottom three branches flagged. Section 4: "Where the opportunity is." Hex gap map. Top 5 candidates ranked. | "The agent diagnoses three under-performers, and identifies five places to open next." |
| 2:30–3:00 | Click expansion candidate #1 — Tsing Yi North. Drill panel: "47K residents within 10-min walk, 0 BOCHK branches, 1 HSBC at capacity." | "Click any candidate, get the rationale. That's the product. Three minutes from CSV to actionable recommendation, powered by Qwen, grounded in HKSAR public spatial data." |

## What we say in the deck but not on stage

- The competitor POI database is pre-parsed.
- Population grid is cached.
- Isochrone graph is pre-warmed for Sham Shui Po + Kowloon West.
- The clarifying question, methodology selection, tool sequencing, and narrative are real-time Qwen calls.

## Fallback plan if the agent loop is unstable by 2026-05-28

Same UI, same orchestrator structure, but tool sequence is hard-coded for the demo CSV. The agent still writes the narrative live. Slides note the constraint honestly: "tool sequence pre-determined for demo; orchestrator dynamic on production data."

## Common questions and answers

- **Why Qwen?** Sponsor + the agent framework is good + Chinese-language support matters for an HK product roadmap.
- **Why CSDI not Google?** Better pedestrian network, official population data, no licence cost, narrative win with HKSTP/BOCHK.
- **What's defensible?** Tool library + CSDI integration depth + the orchestrator's domain methodology. Each tool added compounds.
- **Why a storymap not a dashboard?** A dashboard makes the analyst do the work. A storymap shows them the conclusion.
