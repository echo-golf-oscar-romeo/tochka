"""Storymap-shaped models — what the frontend renders.

The shape is deliberately close to Mapbox Storytelling's `config.chapters[]`
so the frontend can hand it almost directly to the scroll controller.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class MapLocation(BaseModel):
    center: tuple[float, float]    # lng, lat — MapLibre convention
    zoom: float
    pitch: float = 0
    bearing: float = 0


class LayerOp(BaseModel):
    """A layer visibility / opacity instruction tied to a chapter."""
    layer: str
    opacity: float = 1.0


class Layer(BaseModel):
    """A renderable map layer — either inline GeoJSON or a source ref."""
    id: str
    kind: Literal["geojson", "raster", "vector", "hex"]
    data: dict[str, Any] | None = None     # inline GeoJSON for geojson/hex
    source_url: str | None = None          # for raster/vector tile sources
    paint: dict[str, Any] = Field(default_factory=dict)


class ChartSpec(BaseModel):
    """A renderable chart block inside a report section.

    `data` rows are {label, value} (+ optional value2 for scatter, where
    value=x and value2=y). The frontend maps `kind` to a Recharts component.
    """
    kind: Literal["bar", "area", "donut", "scatter", "rank"]
    title: str
    subtitle: str | None = None
    unit: str | None = None                # e.g. "residents", "%", "HK$"
    data: list[dict[str, Any]] = Field(default_factory=list)
    source: str | None = None              # e.g. "Kontur population · CSDI"


class StorymapSection(BaseModel):
    """One scroll-step. Matches Mapbox Storytelling chapter shape closely."""
    id: str                                # 'network-glance', 'who-you-reach', …
    title: str
    description: str                       # markdown allowed
    alignment: Literal["left", "center", "right", "full"] = "left"
    location: MapLocation
    on_enter: list[LayerOp] = Field(default_factory=list)
    on_exit: list[LayerOp] = Field(default_factory=list)
    callouts: list[str] = Field(default_factory=list)
    kpis: dict[str, str] = Field(default_factory=dict)
    charts: list[ChartSpec] = Field(default_factory=list)


class StorymapResult(BaseModel):
    id: str
    network_id: str
    style_url: str                         # CSDI Vector Map by default
    layers: list[Layer]
    sections: list[StorymapSection]
    summary: str | None = None             # short narrative for hero / share card
