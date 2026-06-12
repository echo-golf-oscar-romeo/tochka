# tochka — agent-driven location intelligence for Hong Kong

Map-first spatial-AI platform: upload a CSV of locations → a methodologist
agent designs the analysis plan → deterministic geospatial tools execute it,
streaming layers to a MapLibre map → a designed report with charts, maps and
recommendations. Built for the HKSTP Spatial AI Sandbox PoC Challenge +
Qwenched #1 (May 2026). Brand is always lowercase: **tochka**.

## Stack & layout

- `backend/` — FastAPI + SSE (`sse-starlette`), DuckDB-spatial, h3 v4, numpy,
  PuLP/CBC, scipy, scikit-learn. Python 3.11, managed with **uv**
  (`uv add …`, venv at `backend/.venv`).
  - `app/api/` — routes: `/upload`, `/analyze` (SSE), `/storymap`, `/chat`.
  - `app/orchestrator/` — the brains:
    - `agent.py` — the run loop: clarify → methodologist plan → execute
      steps → compose report → narrate. Emits `AgentEvent`s
      (thought/plan_narrative/tool_call/tool_result/layer_added/
      narrating/storymap_ready/done).
    - `registry.py` — the step registry (16 analysis steps with
      requires/produces deps). Add a capability = add one `Step` here.
    - `llm.py` — `llm_select_plan` (methodologist), `llm_narrate`
      (report copy), `llm_clarify`. All fall back gracefully when no key.
    - `geosql.py` — chat loop: deterministic tool router FIRST (works
      key-less), then LLM SQL agent (300-row cap, SELECT-only blacklist).
    - `chat_tools.py` — chat intents: OSM preset fetch, `/osm` freeform
      (LLM→Overpass QL), Mapbox isochrones, metric buffers, H3 aggregate,
      district choropleths. `overpass_post()` = 3-mirror failover.
    - `method_tools.py` — advanced-method chat intents + handlers
      (whitespace, MCLP, best-new-site, LISA incl. hex-grid LISA,
      find-similar, clusters, drivers, 2SFCA). `RAMP`/`ramp_expr` =
      single-hue gradient helper.
    - `SKILL_geosql.md` / `SKILL_methodology.md` / `SKILL_report.md` —
      the agent's skills (SQL tables+rules, plan design, report house style).
  - `app/tools/` — deterministic tools: reachability (Mapbox isochrones),
    competitors (OSM + own-brand exclusion), demand, modeling (decay Huff +
    anomalies), opportunity (real Kontur), optimization (p-median/LSCP/MCLP),
    similarity (context embeddings), regression, decay kernels,
    geostatistics (Moran/LISA/Gi*/IDW/2SFCA), siteselection (MCDA/
    best-new-point/whitespace), viz (layer builders + report composer).
  - `app/clients/ddb.py` — DuckDB singleton + loaders: `osm_pois` (1.3k
    banks/ATMs), `kontur_pop_hex` (1,298 real H3 r8 population cells),
    `csdi_pois` (37,378 official iGeoCom POIs), `hk_districts` (18 with
    population + geometry), `_user_locations` (per-upload temp).
  - `scripts/` — `fetch_csdi.py`, `fetch_kontur.py`, `fetch_osm_banks.py`
    (regenerate the committed data), `test_csdi.py` (connectivity self-test).
- `frontend/` — Next.js 15 / React 19 / Tailwind / MapLibre GL /
  framer-motion / lucide-react / Recharts.
  - `components/MapWorkspace.tsx` — the shell: chat left, map centre,
    layers+reports right. `QuestionFlow` (post-upload ask), `ReportPanel`
    (slide-over report with charts + static map), `MethodologyPopover`
    (live plan checklist), `LayersList` (eye toggles, drag reorder —
    first row = TOP of map stack).
  - `lib/` — `api.ts` (SSE parser, chat), `mapStyle.ts` (Mapbox style +
    `transformRequest` rewriting `mapbox://` URIs), `reports.ts`
    (localStorage shelf), `storymap.ts` (types incl. ChartSpec).
- `data/` — committed: `kontur/kontur_pop_hk.parquet`, `csdi/csdi_pois.parquet`,
  `csdi/hk_districts.geojson`, `samples/boc_branches_hk.csv` (105 real BOC
  branches for demos). gitignore allows exactly these.

## Commands

```bash
# backend
cd backend && uv run uvicorn app.main:app --reload          # dev server :8000
cd backend && .venv/Scripts/python.exe -m pytest -q          # 87+ tests
cd backend && python scripts/test_csdi.py                    # CSDI self-test
# frontend
cd frontend && npm run dev                                   # :3000
cd frontend && npm run type-check && npm run build
```

`frontend/.env.local`: `NEXT_PUBLIC_MAPBOX_STYLE_URL` + `_ACCESS_TOKEN`
(kuttin29 custom style; falls back to Carto Positron). Backend `.env`:
`DEEPSEEK_API_KEY` / `DASHSCOPE_API_KEY` (LLM), `MAPBOX_ACCESS_TOKEN`
(isochrones), `DEMO_MODE=true` → canned tool outputs for offline demos.

## Hard-won gotchas (do not relearn these)

- **DuckDB-spatial axis order**: `ST_Distance_Spheroid(ST_Point(lat, lng), …)`
  is LAT-FIRST (opposite of GeoJSON). `ST_Transform` MUST get `always_xy :=
  true` or EPSG:4326 output is (lat, lng) and your data lands in the ocean —
  this once silently swapped the entire Kontur grid. `ST_Area_Spheroid`
  wants lat-first too → `ST_FlipCoordinates` first.
- **MapLibre paint props are typed per layer**: passing `line-*` into a
  `fill` layer makes `addLayer` THROW and the polygon silently never
  renders. `MapCanvas.addOrReplaceLayer` filters paint by prefix — keep it.
- **Mapbox styles in MapLibre** need the `transformRequest` hook rewriting
  `mapbox://` source/sprite/glyph URIs + `validateStyle: false` (Mapbox
  styles carry props MapLibre's validator rejects, which aborts loading).
- **Overpass**: default python UAs get 406'd — send a real User-Agent.
  `out geom tags;` is invalid QL (`out geom;`). The main instance sheds
  load often → always go through `overpass_post()` (mirror failover).
- **sse-starlette emits CRLF**: split SSE events with `/\r?\n\r?\n/`.
- **LLM output parsing**: DeepSeek ignores `<sql>` tags ~10% of the time —
  `extract_sql` falls back to ```` ```sql ```` fences then bare SELECT.
  SQL answers must project `lat, lng` for point rows or the frontend can't
  map them (SKILL_geosql rule 4).
- **pydantic-settings reads `.env` at import** — tests must `os.environ`
  override BEFORE importing `app.*`.

## Conventions

- Palette: ink `#0A0903`, paper `#FDFDFD`, primary purple `#4F35F8`,
  secondary red `#FB3640`; 8-colour layer palette `#FAD037 #FB3640 #FA37B2
  #C637FA #37B2FA #37FADD #37FA7E #FA8237`. **Graded layers use single-hue
  light→dark ramps** (`method_tools.RAMP`) — no rainbow ramps. Every layer
  gets its own hue; points get a 1.5–2.5px paper stroke; polygons fill at
  0.25–0.55 opacity. LISA is categorical: HH red, LL blue.
- Font: Inter only. Brand lowercase. Liquid-glass surfaces via
  `.liquid-glass(-strong)`; standard entrance via `.fade-in-up`.
- Every analytical result returns an `interpretation` (plain English with
  the key numbers) and honesty flags (`reliability`, solver `status`,
  sample-size caveats). Charts are computed deterministically; the LLM
  only writes prose around supplied numbers.
- Workflow per round: feature branch → batched commits with verification
  (pytest + type-check + production build) → squash-merge PR via `gh`.
