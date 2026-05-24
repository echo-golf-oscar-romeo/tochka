"""POST /analyze — run the orchestrator, stream events as SSE."""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from app.orchestrator.agent import Orchestrator
from app.store import store

router = APIRouter(prefix="/analyze", tags=["analyze"])


class AnalyzeBody(BaseModel):
    network_id: str
    user_intent: str | None = None
    clarification_answer: str | None = None


@router.post("")
async def analyze(body: AnalyzeBody):
    network = store.networks.get(body.network_id)
    if network is None:
        raise HTTPException(404, "Unknown network_id. Upload first.")

    orch = Orchestrator()

    async def event_stream():
        async for event in orch.run(network, user_intent=body.user_intent,
                                    clarification_answer=body.clarification_answer):
            # sse-starlette will JSON-stringify if we pass a dict; we wrap to be explicit.
            yield {"event": event.kind, "data": json.dumps(event.payload)}
            if event.kind == "storymap_ready":
                store.storymaps[event.payload["storymap_id"]] = event.payload["storymap"]

    return EventSourceResponse(event_stream())
