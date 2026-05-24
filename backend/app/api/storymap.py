"""GET /storymap/{id} — return the final storymap JSON."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.storymap import StorymapResult
from app.store import store

router = APIRouter(prefix="/storymap", tags=["storymap"])


@router.get("/{storymap_id}", response_model=StorymapResult)
async def get_storymap(storymap_id: str) -> StorymapResult:
    sm = store.storymaps.get(storymap_id)
    if sm is None:
        raise HTTPException(404, "Storymap not found.")
    return sm
