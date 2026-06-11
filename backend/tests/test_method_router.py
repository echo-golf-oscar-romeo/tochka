"""Pins the advanced-method intent classifier so demo prompts keep routing.

Classifier only — deterministic, no data / network needed."""

from __future__ import annotations

import os

os.environ.setdefault("DEMO_MODE", "true")

import pytest  # noqa: E402

from app.orchestrator.method_tools import classify_method  # noqa: E402


@pytest.mark.parametrize("prompt, kind", [
    ("where should I open 5 new branches to cover the most people", "optimize_coverage"),
    ("optimise coverage with 6 sites", "optimize_coverage"),
    ("run a p-median for 4 facilities", "optimize_coverage"),
    ("what's the best new site for a branch", "best_new_point"),
    ("where should I open a new branch next", "best_new_point"),
    ("show me the underserved whitespace", "whitespace"),
    ("where are the coverage gaps", "whitespace"),
    ("find hot spots and cold spots of branch volume", "hotspots"),
    ("run a LISA on actual volume", "hotspots"),
    ("is my network spatially clustered", "hotspots"),
    ("find locations similar to Central", "find_similar"),
    ("which areas look like my best branch", "find_similar"),
    ("cluster my network into 3 segments", "cluster"),
    ("segment my branches", "cluster"),
    ("what drives branch volume", "drivers"),
    ("which factors explain performance", "drivers"),
    ("show 2sfca accessibility", "accessibility"),
    ("where is access poor", "accessibility"),
])
def test_method_intents_classified(prompt: str, kind: str) -> None:
    intent = classify_method(prompt)
    assert intent is not None, f"{prompt!r} should classify as {kind}"
    assert intent.kind == kind, f"{prompt!r} -> {intent.kind}, expected {kind}"


@pytest.mark.parametrize("prompt", [
    "which 10 competitor banks are closest to hku",
    "show all branches with their nearest competitor distance",
    "create a 500m buffer from each bank",
    "find all schools in hong kong",
])
def test_plain_queries_fall_through(prompt: str) -> None:
    # These belong to SQL / OSM / buffer routers, not the method router.
    assert classify_method(prompt) is None


def test_count_and_radius_extraction() -> None:
    i = classify_method("optimise coverage with 7 sites within 1200m")
    assert i.params.get("count") == 7
    assert i.params.get("radius_m") == 1200.0
    i2 = classify_method("cover demand with 5 branches within 1.5km")
    assert i2.params.get("radius_m") == 1500.0
