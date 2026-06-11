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
_kontur_loaded: bool = False
_csdi_loaded: bool = False


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
    global _conn, _osm_loaded, _kontur_loaded, _csdi_loaded
    if _conn is not None:
        _conn.close()
        _conn = None
        _osm_loaded = False
        _kontur_loaded = False
        _csdi_loaded = False


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
# CSDI POI loader (real Hong Kong iGeoCom dataset, 37k official POIs)
# ---------------------------------------------------------------------------

def _csdi_pois_path() -> Path:
    return (Path(__file__).resolve().parents[3] / "data" / "csdi" / "csdi_pois.parquet").resolve()


def ensure_csdi_pois_loaded(conn: duckdb.DuckDBPyConnection | None = None) -> bool:
    """Load the real CSDI iGeoCom POIs into a `csdi_pois` table. Idempotent.

    Columns: geonameid, name_en, name_zh, class, type, category, lat, lng,
    district_en, address_en. Returns True when populated, False if the
    parquet is missing (run scripts/fetch_csdi.py).
    """
    global _csdi_loaded
    if _csdi_loaded:
        return True
    conn = conn or get_duckdb()
    path = _csdi_pois_path()
    if not path.exists():
        log.warning("CSDI POIs parquet missing at %s. Run scripts/fetch_csdi.py.", path)
        return False
    conn.execute("DROP TABLE IF EXISTS csdi_pois;")
    conn.execute("CREATE TABLE csdi_pois AS SELECT * FROM read_parquet(?)", [str(path)])
    n = conn.execute("SELECT COUNT(*) FROM csdi_pois").fetchone()[0]
    log.info("Loaded %d CSDI POIs into DuckDB.", n)
    _csdi_loaded = True
    return True


def hk1980_to_wgs84(points: list[tuple[float, float]],
                    conn: duckdb.DuckDBPyConnection | None = None) -> list[tuple[float, float]]:
    """Batch-convert HK1980 Grid (EPSG:2326) easting/northing → (lng, lat) WGS84.

    CSDI's locationSearch returns x/y in EPSG:2326; this uses DuckDB-spatial's
    ST_Transform with always_xy so we don't need a separate pyproj dependency.
    Returns [(lng, lat), ...] in the same order; (None, None) for bad rows.
    """
    if not points:
        return []
    conn = conn or get_duckdb()
    out: list[tuple[float, float]] = []
    for x, y in points:
        try:
            r = conn.execute(
                "SELECT ST_X(p), ST_Y(p) FROM (SELECT ST_Transform("
                "ST_Point(?, ?), 'EPSG:2326', 'EPSG:4326', true) AS p)",
                [float(x), float(y)],
            ).fetchone()
            out.append((r[0], r[1]))
        except Exception:  # noqa: BLE001
            out.append((None, None))
    return out


# ---------------------------------------------------------------------------
# Kontur population hex (H3 r8) loader
# ---------------------------------------------------------------------------

def _kontur_parquet_path() -> Path:
    return (Path(__file__).resolve().parents[3] / "data" / "kontur" / "kontur_pop_hk.parquet").resolve()


def _synthetic_kontur_rows() -> list[tuple]:
    """A tiny synthetic HK population grid used when the real Kontur parquet
    isn't available. Lets the demo + tests still run something plausible.

    Generates an evenly-spaced grid across the HK bbox with a population
    distribution that decays from the urban core (Central) outwards, so
    opportunity-style queries return realistic-shaped output.
    """
    import math
    import h3  # type: ignore[import-not-found]

    # HK urban core ≈ Central (Hong Kong Island).
    core_lat, core_lng = 22.282, 114.158
    bbox_s, bbox_w, bbox_n, bbox_e = 22.17, 113.85, 22.55, 114.42
    step = 0.012  # ≈1.3 km grid — coarser than Kontur r8 but adequate for fallback.

    rows: list[tuple] = []
    seen: set[str] = set()
    lat = bbox_s
    while lat <= bbox_n:
        lng = bbox_w
        while lng <= bbox_e:
            # Decay with distance from core (great-circle, very rough).
            dlat = lat - core_lat
            dlng = (lng - core_lng) * math.cos(math.radians(core_lat))
            r_km = math.hypot(dlat, dlng) * 111.0
            pop = max(50.0, 18000.0 * math.exp(-r_km / 8.0))
            cell = h3.latlng_to_cell(lat, lng, 8)
            if cell in seen:
                lng += step
                continue
            seen.add(cell)
            rows.append((cell, lat, lng, pop, 8))
            lng += step
        lat += step
    return rows


def ensure_kontur_loaded(conn: duckdb.DuckDBPyConnection | None = None) -> bool:
    """Load Kontur HK population hex (or synthetic fallback) into `kontur_pop_hex`.

    Schema: h3 VARCHAR, lat DOUBLE, lng DOUBLE, population DOUBLE, res INTEGER.
    Idempotent. Returns True when populated (real OR synthetic).
    """
    global _kontur_loaded
    if _kontur_loaded:
        return True
    conn = conn or get_duckdb()
    conn.execute("DROP TABLE IF EXISTS kontur_pop_hex;")

    parquet = _kontur_parquet_path()
    if parquet.exists():
        try:
            conn.execute(
                "CREATE TABLE kontur_pop_hex AS SELECT * FROM read_parquet(?)",
                [str(parquet)],
            )
            n = conn.execute("SELECT COUNT(*) FROM kontur_pop_hex").fetchone()[0]
            log.info("Loaded %d Kontur HK population hexes (real).", n)
            _kontur_loaded = True
            return True
        except Exception as e:
            log.warning("Real Kontur parquet at %s failed to load: %s — falling back to synthetic.",
                        parquet, e)

    # Synthetic fallback. Always succeeds.
    try:
        rows = _synthetic_kontur_rows()
    except Exception as e:
        log.warning("Synthetic Kontur fallback failed: %s", e)
        return False

    conn.execute(
        "CREATE TABLE kontur_pop_hex (h3 VARCHAR, lat DOUBLE, lng DOUBLE, "
        "population DOUBLE, res INTEGER);"
    )
    conn.executemany("INSERT INTO kontur_pop_hex VALUES (?, ?, ?, ?, ?)", rows)
    log.info("Loaded %d synthetic Kontur HK hexes (no real parquet at %s).", len(rows), parquet)
    _kontur_loaded = True
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
