"""Fetch Kontur population hex (H3 r8) for Hong Kong → DuckDB-friendly Parquet.

Source: Kontur's open Population dataset, country-clipped releases on HDX.
URL pattern:
    https://geodata-eu-central-1-kontur-public.s3.eu-central-1.amazonaws.com
        /kontur_datasets/kontur_population_HK_20231101.gpkg.gz

The official release file uses an H3 r8 hex grid (~0.74 km² per cell) with one
population value per cell. We use DuckDB-spatial's ST_Read to load the
GeoPackage directly (no geopandas dependency), derive the cell centroid + h3
index in pure Python, and write a flat parquet:

    h3        VARCHAR    -- H3 cell id (resolution 8)
    lat       DOUBLE     -- cell centre latitude
    lng       DOUBLE     -- cell centre longitude
    population DOUBLE    -- residents in the cell (Kontur estimate)
    res       INTEGER    -- always 8 for the source file

Output: data/kontur/kontur_pop_hk.parquet. Committed to the repo so the
backend boots with real population hexes loaded.

Run:
    cd backend && python scripts/fetch_kontur.py
"""

from __future__ import annotations

import gzip
import logging
import sys
from pathlib import Path

import duckdb
import h3
import httpx

log = logging.getLogger(__name__)

KONTUR_URL = (
    "https://geodata-eu-central-1-kontur-public.s3.eu-central-1.amazonaws.com"
    "/kontur_datasets/kontur_population_HK_20231101.gpkg.gz"
)

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / "data" / "kontur"
OUT_PATH = OUT_DIR / "kontur_pop_hk.parquet"
TMP_GPKG = OUT_DIR / "_kontur_hk.gpkg"


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    log.info("Downloading Kontur HK population hex …")

    try:
        with httpx.Client(timeout=120.0, follow_redirects=True) as client:
            r = client.get(KONTUR_URL)
            r.raise_for_status()
            raw = r.content
    except Exception as e:
        print(f"FAILED to download: {e}", file=sys.stderr)
        print("The backend will fall back to a synthetic Hong Kong population grid.")
        return 1

    log.info("Downloaded %d bytes; decompressing", len(raw))
    try:
        gpkg_bytes = gzip.decompress(raw)
    except OSError:
        # Already plain .gpkg (older release).
        gpkg_bytes = raw
    TMP_GPKG.write_bytes(gpkg_bytes)

    # DuckDB-spatial reads GeoPackage natively via ST_Read.
    con = duckdb.connect(":memory:")
    con.execute("INSTALL spatial; LOAD spatial;")

    # Find the actual population column name (Kontur sometimes uses 'population',
    # 'pop', or 'kontur_population' depending on release).
    cols = con.execute(
        "SELECT column_name FROM (DESCRIBE SELECT * FROM ST_Read(?))",
        [str(TMP_GPKG)],
    ).fetchall()
    col_names = [c[0] for c in cols]
    log.info("GeoPackage columns: %s", col_names)
    pop_col = next((c for c in ("population", "pop", "kontur_population") if c in col_names), None)
    if pop_col is None:
        print(f"No population column found. Columns: {col_names}", file=sys.stderr)
        return 3

    # Kontur ships hexes in EPSG:3857 (web mercator). Transform centroid to
    # WGS84 before sampling lat/lng. The GeoPackage already carries an `h3`
    # column with the resolution-8 cell id, so we re-use that rather than
    # recomputing.
    has_h3 = "h3" in col_names
    # always_xy=true is CRITICAL: without it EPSG:4326 output uses PROJ's
    # authority axis order (lat first), so ST_X silently returns latitude
    # and the whole grid lands in the Indian Ocean.
    sql = f"""
        SELECT
            {"h3," if has_h3 else "NULL AS h3,"}
            ST_X(ST_Transform(ST_Centroid(geom), 'EPSG:3857', 'EPSG:4326', true)) AS lng,
            ST_Y(ST_Transform(ST_Centroid(geom), 'EPSG:3857', 'EPSG:4326', true)) AS lat,
            CAST({pop_col} AS DOUBLE) AS population
        FROM ST_Read(?)
        WHERE {pop_col} IS NOT NULL
    """
    rows = con.execute(sql, [str(TMP_GPKG)]).fetchall()
    log.info("Read %d hex rows from GeoPackage", len(rows))

    out_rows = [
        (
            h3_cell if h3_cell else h3.latlng_to_cell(lat, lng, 8),
            lat,
            lng,
            float(pop),
            8,
        )
        for (h3_cell, lng, lat, pop) in rows
    ]

    # Write parquet via DuckDB (cheaper than pyarrow for this size).
    con.execute("DROP TABLE IF EXISTS _out;")
    con.execute(
        "CREATE TABLE _out (h3 VARCHAR, lat DOUBLE, lng DOUBLE, population DOUBLE, res INTEGER);"
    )
    con.executemany("INSERT INTO _out VALUES (?, ?, ?, ?, ?)", out_rows)
    con.execute("COPY _out TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(OUT_PATH)])
    con.close()

    try:
        TMP_GPKG.unlink()
    except OSError:
        pass

    print(f"OK wrote {len(out_rows):,} hex rows to {OUT_PATH}")
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    sys.exit(main())
