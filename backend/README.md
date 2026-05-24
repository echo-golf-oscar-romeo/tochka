# Tochka backend

FastAPI app exposing three endpoints, one orchestrator (Qwen or DeepSeek), one tool library across CSDI / Mapbox / OSM data.

## Run

```bash
uv sync
cp ../.env.example ../.env   # then fill in the LLM provider key (see below)
uv run uvicorn app.main:app --reload --port 8000
```

Swagger UI at http://localhost:8000/docs.

## Endpoints

- `POST /upload` — multipart CSV → `network_id`.
- `POST /analyze` — body `{network_id, archetypes?, clarification_answer?}` → SSE stream of agent events; on `done` event the storymap is ready.
- `GET /storymap/{id}` — final storymap JSON.

## Layout

```
app/
  main.py          FastAPI entry, lifespan, CORS, router mounting
  config.py        Pydantic-Settings env reader
  api/             HTTP route handlers, thin
  models/          Pydantic models for all wire formats
  orchestrator/    Decision tree, prompts, LLM helpers, agent event loop
  tools/           geocoding · reachability · demand · competitors · spatial · aggregation · modeling · viz
  clients/         CSDI (ALS) · Mapbox (isochrones) · LLM (provider-agnostic) · DuckDB
  mock/            Canned data for demo-mode determinism
scripts/           One-off helpers — e.g. fetch_osm_banks.py
tests/             Pytest, minimal happy-path coverage
```

## LLM provider — Qwen or DeepSeek

Tochka talks to both providers over the same OpenAI-compatible Chat Completions endpoint. Switch with one env var:

```bash
# Primary: Alibaba DashScope (Qwen)
LLM_PROVIDER=qwen
DASHSCOPE_API_KEY=sk-xxx
QWEN_MODEL=qwen-max

# Fallback while DashScope account is pending:
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_MODEL=deepseek-chat
```

Agent log events tag which provider answered (`source: "qwen"`, `source: "deepseek"`, or `source: "fallback"` when both fail and we use canned strings).

## DEMO_MODE vs. LLM key

These are independent toggles.

| Setting | Effect |
|---|---|
| `DEMO_MODE=true`  | All **spatial tools** return canned data. Live-demo determinism. |
| `DEMO_MODE=false` | Tools try real (CSDI ALS, Mapbox isochrones, pre-fetched OSM) first; canned on any failure. |
| Provider key set  | Real LLM for clarify + narrative. Independent of `DEMO_MODE`. |
| Provider key unset / call fails | Hard-coded fallback strings. Loop completes. |

## What's wired

| Piece | Status |
|---|---|
| FastAPI routing | wired |
| Pydantic models incl. capacity + actual_volume | wired |
| Orchestrator: 4-question methodology, archetype-driven tool sequence | wired |
| LLM client (Qwen + DeepSeek over OpenAI-compatible API) | wired |
| Clarifying question + per-section narrative via LLM | wired (provider-agnostic) |
| Qwen-Agent tool-calling loop (LLM picks tools turn-by-turn) | stub — `QWEN-AGENT-HOOK` in `app/orchestrator/agent.py` |
| CSDI ALS geocoding | wired |
| Mapbox isochrones (walking + driving) | wired |
| OSM competitor banks/ATMs scan | wired (file pre-fetched by `scripts/fetch_osm_banks.py`) |
| CSDI Population Distribution / iGeoCom / Streetscape / Pedestrian Route | not yet wired |
| DuckDB-spatial connection | wired |

## One-time setup beyond keys

```bash
# Pre-fetch OSM banks + ATMs (gitignored output)
uv run python scripts/fetch_osm_banks.py
```

This writes `data/osm/banks_atms_hk.json` once. The competitor tool reads it with an in-process cache.
