"""Sanity tests for the chat tool intent classifier.

The chat tool router is the front-line for prompt-driven layer creation
(OSM fetch, Mapbox isochrones, H3 aggregation). These tests pin the
classifier's behaviour so a regex tweak doesn't silently break the demo
prompts the user is going to type on stage.
"""

from __future__ import annotations

import pytest

from app.orchestrator.chat_tools import classify


@pytest.mark.parametrize("prompt, expected_category", [
    ("find all the schools in hong kong and add them to the database and to the map", "schools"),
    ("show all hospitals", "hospitals"),
    ("load restaurants in hk", "restaurants"),
    ("get supermarkets near central", "supermarkets"),
    ("fetch museums", "museums"),
    ("download all MTR stations across the territory", "mtr"),
    # Extra verbs the user actually types — must also be classified.
    ("add all the schools in hong kong", "schools"),
    ("plot every pharmacy in hk", "pharmacies"),
    ("drop hotels onto the map", "hotels"),
    ("include all parks in the region", "parks"),
    ("import every supermarket", "supermarkets"),
    ("put atms on the map", "atms"),
])
def test_classify_osm_fetch(prompt: str, expected_category: str) -> None:
    intent = classify(prompt)
    assert intent is not None, f"prompt {prompt!r} should be classified"
    assert intent.kind == "osm_fetch", intent
    assert intent.params["category"] == expected_category, intent


@pytest.mark.parametrize("prompt, minutes", [
    ("show me an isochrone layer for all hsbc banks (15 minutes walking time)", 15),
    ("draw a 10-minute walking isochrone for the user network", 10),
    ("20 min driving catchment around HSBC banks", 20),
])
def test_classify_isochrone(prompt: str, minutes: int) -> None:
    intent = classify(prompt)
    assert intent is not None, f"prompt {prompt!r} should be classified"
    assert intent.kind == "isochrone", intent
    assert intent.params["minutes"] == minutes, intent


@pytest.mark.parametrize("prompt, expected_res", [
    ("aggregate the user network on H3 r9 with population", 9),
    ("show me a hex grid of competitive intensity", 8),
    ("h3 resolution 7 aggregation please", 7),
])
def test_classify_h3(prompt: str, expected_res: int) -> None:
    intent = classify(prompt)
    assert intent is not None
    assert intent.kind == "h3_aggregate", intent
    assert intent.params["resolution"] == expected_res, intent


@pytest.mark.parametrize("prompt", [
    # Plain SQL-style — must fall through to the SQL agent (None).
    "which 10 competitor banks are closest to Central?",
    "show all branches with their nearest competitor distance.",
    "are any of my branches within 500m of each other?",
])
def test_classify_falls_through_to_sql(prompt: str) -> None:
    assert classify(prompt) is None, f"{prompt!r} should NOT be intercepted"


@pytest.mark.parametrize("prompt, radius_m", [
    # The literal demo prompt the user asked for.
    ("make a buffer zone 500m from every bank", 500.0),
    # Radius before "buffer".
    ("500m buffer around every bank", 500.0),
    ("draw a 250-metre buffer around HSBC", 250.0),
    # km units.
    ("1km buffer zone around all banks", 1000.0),
    ("buffer of 2 km from my network", 2000.0),
    # Pluralised, no verb, "for" preposition.
    ("buffers for HSBC banks at 400 metres", 400.0),
])
def test_classify_buffer(prompt: str, radius_m: float) -> None:
    intent = classify(prompt)
    assert intent is not None, f"{prompt!r} should be classified"
    assert intent.kind == "buffer", intent
    assert intent.params["radius_m"] == radius_m, intent
