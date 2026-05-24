"""Network and Location — the uploaded CSV, typed."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Location(BaseModel):
    id: str
    name: str
    lat: float | None = None
    lng: float | None = None
    address: str | None = None
    # Everything else from the CSV row — preserved for the orchestrator to inspect.
    raw_fields: dict[str, Any] = Field(default_factory=dict)
    # Filled in by the geocoding tool when (lat, lng) was missing.
    geocoded: bool = False
    geocode_confidence: float | None = None


class Network(BaseModel):
    id: str
    source_filename: str
    locations: list[Location]
    # Classification is set by the orchestrator after parsing.
    inferred_poi_type: str | None = None
