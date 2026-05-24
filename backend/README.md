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
| Orchestrator decision tree (rule-based methodology pick) | wired |
| Qwen LLM — clarifying question | **wired** via DashScope OpenAI-compatible endpoint; falls back to hard-coded string when no API key |
| Qwen LLM — per-section narrative rewriting | **wired**; falls back to composed f-string when no API key |
| Qwen tool-calling loop (LLM picks tools turn-by-turn) | stub — see `QWEN-AGENT-HOOK` in `app/orchestrator/agent.py`; slots in `qwen-agent.Assistant` later |
| All data tool functions | stubs returning canned data when `DEMO_MODE=true`, raising `NotImplementedError` otherwise |
| CSDI client | stub |
| DuckDB-spatial connection | wired |

## LLM mode vs. demo mode

`DEMO_MODE` only gates **data tools** (CSDI, isochrones, competitors, population). LLM calls are independent:

- If `DASHSCOPE_API_KEY` is set → real Qwen for clarify + narrative (recommended for live demo).
- If unset or the call fails → graceful fallback to hard-coded strings. Loop still completes.

That split lets the live demo show the LLM thinking on stage while the data layer stays deterministic against venue WiFi.
