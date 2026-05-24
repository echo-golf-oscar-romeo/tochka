"""POST /chat/{storymap_id} — Aino-style follow-up Q&A on the storymap.

The endpoint is stateful per storymap_id — conversation history is held
in the in-process store. Each turn is one LLM-driven spatial SQL cycle
(see orchestrator/geosql.py).
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.orchestrator.geosql import run_chat_turn
from app.store import store

log = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatBody(BaseModel):
    message: str


class ChatResponse(BaseModel):
    answer: str
    sql: str | None = None
    rows: list[dict[str, Any]] = []
    columns: list[str] = []
    error: str | None = None
    provider: str | None = None
    history: list[dict[str, str]] = []


@router.post("/{storymap_id}", response_model=ChatResponse)
async def chat(storymap_id: str, body: ChatBody) -> ChatResponse:
    storymap = store.storymaps.get(storymap_id)
    if storymap is None:
        raise HTTPException(404, "Storymap not found.")

    # Resolve the network behind this storymap.
    network_id = (storymap or {}).get("network_id") if isinstance(storymap, dict) else None
    if network_id is None and hasattr(storymap, "network_id"):
        network_id = storymap.network_id   # in case it's a Pydantic model
    network = store.networks.get(network_id) if network_id else None
    if network is None:
        raise HTTPException(400, "Underlying network is no longer available; re-upload.")

    history = store.chat_histories.setdefault(storymap_id, [])
    summary = None
    if isinstance(storymap, dict):
        summary = storymap.get("summary")

    result = await run_chat_turn(
        network=network,
        history=history,
        user_message=body.message,
        storymap_summary=summary,
    )

    # Persist the turn so future questions have context.
    history.append({"role": "user", "content": body.message})
    history.append({"role": "assistant", "content": result["answer"]})
    if len(history) > 40:
        # Keep the last 20 exchanges only.
        del history[: len(history) - 40]

    return ChatResponse(
        answer=result["answer"],
        sql=result.get("sql"),
        rows=result.get("rows", []),
        columns=result.get("columns", []),
        error=result.get("error"),
        provider=result.get("provider"),
        history=list(history),
    )


@router.get("/{storymap_id}/history", response_model=list[dict[str, str]])
async def get_chat_history(storymap_id: str) -> list[dict[str, str]]:
    return store.chat_histories.get(storymap_id, [])


@router.post("/network/{network_id}", response_model=ChatResponse)
async def chat_network(network_id: str, body: ChatBody) -> ChatResponse:
    """Chat against a network even before any analysis storymap exists.

    Same machinery as /chat/{storymap_id}, but the history is keyed by
    the network_id and there's no storymap summary to feed into the prompt.
    """
    network = store.networks.get(network_id)
    if network is None:
        raise HTTPException(404, "Unknown network — upload first.")

    history_key = f"net:{network_id}"
    history = store.chat_histories.setdefault(history_key, [])

    result = await run_chat_turn(
        network=network,
        history=history,
        user_message=body.message,
        storymap_summary=None,
    )

    history.append({"role": "user", "content": body.message})
    history.append({"role": "assistant", "content": result["answer"]})
    if len(history) > 40:
        del history[: len(history) - 40]

    return ChatResponse(
        answer=result["answer"],
        sql=result.get("sql"),
        rows=result.get("rows", []),
        columns=result.get("columns", []),
        error=result.get("error"),
        provider=result.get("provider"),
        history=list(history),
    )
