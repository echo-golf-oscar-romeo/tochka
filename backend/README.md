# Tochka backend

FastAPI app exposing three endpoints, one Qwen orchestrator, one tool library.

## Run

```bash
uv sync
cp ../.env.example ../.env   # then fill in DASHSCOPE_API_KEY
uv run uvicorn app.main:app --reload --port 8000
```

Swagger UI at http://localhost:8000/docs.

## Endpoints

- `POST /upload` — multipart CSV → `network_id`.
- `POST /analyze` — body `{network_id, user_intent?}` → SSE stream of agent events; on `done` event the storymap is ready.
- `GET /storymap/{id}` — final storymap JSON.

## Layout

```
app/
  main.py          FastAPI entry, lifespan, CORS, router mounting
  config.py        Pydantic-Settings env reader
  api/             HTTP route handlers, thin
  models/          Pydantic models for all wire formats
  orchestrator/    Qwen-Agent loop + the 4-question decision logic
  tools/           One file per tool category — geocoding, reachability, demand, …
  clients/         External HTTP clients — CSDI, DashScope (Qwen) — and DuckDB
  mock/            Canned data for demo-mode determinism
tests/             Pytest, minimal happy-path coverage
```

## Demo mode

Set `DEMO_MODE=true` in `.env`. Every tool short-circuits to `app/mock/canned.py` and never hits the network. Used for the live Qwenched demo so a flaky venue WiFi can't break anything.

## What's stubbed vs. wired

| Piece | Status |
|---|---|
| FastAPI routing | wired |
| Pydantic models | wired |
| Orchestrator decision tree | rule-based stub, ready for Qwen wiring |
| Qwen tool-calling loop | stub — TODO once Qwen-Agent API confirmed |
| All tool functions | stubs returning canned data when `DEMO_MODE=true`, raising `NotImplementedError` otherwise |
| CSDI client | stub |
| DashScope client | stub |
| DuckDB-spatial connection | wired |
