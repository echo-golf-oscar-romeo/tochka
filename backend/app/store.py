"""In-memory store for the skeleton. Swap for DuckDB/Redis later.

Two dicts keyed by id: uploaded networks and produced storymaps. Lifetime = process.
Good enough for the demo and for local development; not for a production deployment.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class _Store:
    networks: dict[str, Any] = field(default_factory=dict)
    storymaps: dict[str, Any] = field(default_factory=dict)
    # Per-storymap chat history: list of {role, content} dicts.
    chat_histories: dict[str, list[dict[str, str]]] = field(default_factory=dict)


store = _Store()
