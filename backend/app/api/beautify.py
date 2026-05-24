"""POST /beautify — one iteration of the vision-driven map refinement loop."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.orchestrator.beautify import run_beautify_turn

router = APIRouter(prefix="/beautify", tags=["beautify"])


class StyleEntry(BaseModel):
    layer_id: str
    paint: dict[str, Any] = Field(default_factory=dict)


class BeautifyBody(BaseModel):
    screenshot: str                      # PNG base64 or data URI
    styles: list[StyleEntry]             # current layer paint properties
    iteration: int = 1
    iteration_max: int = 3


class StyleUpdate(BaseModel):
    layer_id: str
    paint: dict[str, Any]


class BeautifyResponse(BaseModel):
    notes: str
    updates: list[StyleUpdate]
    provider: str | None = None
    error: str | None = None


@router.post("", response_model=BeautifyResponse)
async def beautify(body: BeautifyBody) -> BeautifyResponse:
    result = await run_beautify_turn(
        screenshot=body.screenshot,
        current_styles=[s.model_dump() for s in body.styles],
        iteration=body.iteration,
        iteration_max=body.iteration_max,
    )
    return BeautifyResponse(
        notes=result.get("notes", ""),
        updates=[StyleUpdate(**u) for u in result.get("updates", [])],
        provider=result.get("provider"),
        error=result.get("error"),
    )
