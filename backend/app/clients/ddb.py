"""DuckDB connection with the spatial extension loaded.

One process-wide connection. Cheap to share across coroutines for our scale.

This module also owns the small "load once" helpers that materialise the
pre-fetched OSM POIs into a DuckDB table so tools can run real spatial SQL
(ST_Distance_Spheroid, ST_DWithin, ST_Contains) against it.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable

import duckdb

from app.config import get_settings

log = logging.getLogger(__name__)

_conn: duckdb.DuckDBPyConnection | None = None
_osm_loaded: bool = False


def get_duckdb() -> duckdb.DuckDBPyConnection:
    """Lazy-init the process-wide connection with spatial extension loaded."""
    global _conn
    if _conn is not None:
        return _conn
    path = Path(get_settings().duckdb_path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    _conn = duckdb.connect(str(path))
    try:
        _conn.execute("INSTALL spatial; LOAD spatial;")
    except duckdb.Error:
        # First install requires network; if offline the user must have
        # pre-installed before the demo (uv run python -c "import duckdb; duckdb.connect().execute('INSTALL spatial')").
        try:
            _conn.execute("LOAD spatial;")
        except duckdb.Error as e:
            log.warning("DuckDB spatial extension unavailable: %s", e)
    return _conn


def close_duckdb() -> None:
    global _conn, _osm_loaded
    if _conn is not None:
        _conn.close()
        _conn = None
        _osm_loaded = False


# ---------------------------------------------------------------------------
# OSM POI loader
# ---------------------------------------------------------------------------

def _resolve_osm_path() -> Path:
    p = Path(get_settings().osm_banks_path)
    if not p.is_absolute():
        # Resolve relative to repo root (parent of backend/).
        p = (Path(__file__).resolve().parents[3] / p).resolve()
    return p


def ensure_osm_loaded(conn: duckdb.DuckDBPyConnection | None = None) -> bool:
    """Load the OSM banks/ATMs JSON into a `osm_pois` table. Idempotent.

    Returns True when the table is populated; False when the source file is
    missing (callers fall back to canned or empty results).
    """
    global _osm_loaded
    if _osm_loaded:
        return True
    conn = conn or get_duckdb()

    path = _resolve_osm_path()
    if not path.exists():
        log.warning("OSM POIs file missing at %s. Run scripts/fetch_osm_banks.py.", path)
        return False

    # Drop and re-create on each fresh process so schema changes don't bite us.
    conn.execute("DROP TABLE IF EXISTS osm_pois;")
    conn.execute(
        """
        CREATE TABLE osm_pois AS
        SELECT
            id,
            type,
            name,
            brand,
            CAST(lat AS DOUBLE) AS lat,
            CAST(lng AS DOUBLE) AS lng,
            addr_district AS district,
            COALESCE(atm, FALSE) AS atm
        FROM read_json_auto(?)
        """,
        [str(path)],
    )
    n = conn.execute("SELECT COUNT(*) FROM osm_pois").fetchone()[0]
    log.info("Loaded %d OSM POIs into DuckDB.", n)
    _osm_loaded = True
    return True


# ---------------------------------------------------------------------------
# Ad-hoc table registration helpers
# ---------------------------------------------------------------------------

def register_locations(conn: duckdb.DuckDBPyConnection, locations: Iterable) -> str:
    """Materialise a list of `app.models.network.Location` as a temp table.

    Skips rows without coordinates. Exposes: id, name, lat, lng, capacity,
    actual_volume. Returns the table name.
    """
    conn.execute("DROP TABLE IF EXISTS _user_locations;")
    conn.execute(
        """
        CREATE TEMP TABLE _user_locations (
            id VARCHAR, name VARCHAR, lat DOUBLE, lng DOUBLE,
            capacity DOUBLE, actual_volume DOUBLE
        );
        """
    )
    rows = [
        (
            loc.id, loc.name, float(loc.lat), float(loc.lng),
            float(loc.capacity) if loc.capacity is not None else None,
            float(loc.actual_volume) if loc.actual_volume is not None else None,
        )
        for loc in locations
        if loc.lat is not None and loc.lng is not None
    ]
    if rows:
        conn.executemany(
            "INSERT INTO _user_locations VALUES (?, ?, ?, ?, ?, ?)",
            rows,
        )
    return "_user_locations"


def register_kv_table(conn: duckdb.DuckDBPyConnection, name: str,
                      rows: list[dict], columns: list[tuple[str, str]]) -> str:
    """Materialise a list of dicts as a temp table with explicit (col, sqltype).

    Missing keys land as NULL. Returns the table name.
    """
    conn.execute(f"DROP TABLE IF EXISTS {name};")
    cols_def = ", ".join(f"{c} {t}" for c, t in columns)
    conn.execute(f"CREATE TEMP TABLE {name} ({cols_def});")
    if rows:
        cols_only = [c for c, _ in columns]
        placeholders = ", ".join(["?"] * len(columns))
        tuples = [tuple(r.get(c) for c in cols_only) for r in rows]
        conn.executemany(f"INSERT INTO {name} VALUES ({placeholders})", tuples)
    return name
