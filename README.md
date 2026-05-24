# Tochka — Spatial AI Agent

Location-intelligence platform: upload a CSV of your network of locations, an agent orchestrator decides the methodology, specialist tools execute, and the output is a scroll-driven storymap with concrete next steps.

Entry use case: BOCHK branch / ATM network optimisation. Generalisable across retail, F&B, healthcare, social services, real estate.

## Submissions
- **HKSTP Spatial AI Sandbox PoC Challenge** — proposal + business plan due 2026-05-26 noon.
- **Qwenched #1 (WYB × Alibaba Cloud)** — live demo 2026-05-30, Causeway Bay.

## Stack
- **Backend** — Python, FastAPI, DuckDB-spatial, H3, Qwen-Agent (DashScope).
- **Frontend** — Next.js, MapLibre GL with CSDI Vector Map basemap, Mapbox-Storytelling-pattern scrollytelling ported to MapLibre.
- **Data** — CSDI (ALS, 3D Pedestrian Network, Population Distribution, iGeoCom), Google Maps POIs (parsed), OSM HK extract fallback.

## Layout
```
backend/        FastAPI app, agent orchestrator, tool library
frontend/       Next.js storymap UI
data/           Local data cache (gitignored)
docs/           Methodology, proposal outline, demo script, data inventory
```

## Quick start
```bash
# backend
cd backend && uv sync && uv run uvicorn app.main:app --reload --port 8000

# frontend
cd frontend && npm install && npm run dev
```

## Reading order for new contributors
1. `docs/BRIEF.md` — full product brief
2. `docs/METHODOLOGY.md` — the 4-question orchestrator decision flow
3. `docs/DEMO_SCRIPT.md` — what the 3-minute Qwenched run looks like
4. `docs/DATA_INVENTORY.md` — which CSDI datasets we use and why
