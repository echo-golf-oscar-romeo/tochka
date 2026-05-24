"""DuckDB connection with the spatial extension loaded.

One process-wide connection. Cheap to share across coroutines for our scale.
"""

from __future__ import annotations

from pathlib import Path

import duckdb

from app.config import get_settings

_conn: duckdb.DuckDBPyConnection | None = None


def get_duckdb() -> duckdb.DuckDBPyConnection:
    global _conn
    if _conn is not None:
        return _conn
    path = Path(get_settings().duckdb_path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    _conn = duckdb.connect(str(path))
    try:
        _conn.execute("INSTALL spatial; LOAD spatial;")
    except duckdb.Error:
        # First install requires network; if offline at demo venue, the install was
        # done ahead of time so the LOAD succeeds without INSTALL.
        _conn.execute("LOAD spatial;")
    return _conn


def close_duckdb() -> None:
    global _conn
    if _conn is not None:
        _conn.close()
        _conn = None
