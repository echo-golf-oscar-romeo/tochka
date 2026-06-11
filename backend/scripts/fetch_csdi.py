"""Fetch real Hong Kong CSDI / gov open data → compact files the backend loads.

Produces two committed artefacts under data/csdi/:

  csdi_pois.parquet   — 37k official HK POIs from the iGeoCom dataset
                        (open.hkmapservice.gov.hk). Already WGS84.
                        Columns: geonameid, name_en, name_zh, class, type,
                        category, lat, lng, district_en, address_en.
  hk_districts.geojson — the 18 HK District Council district boundaries
                        (had.gov.hk), GeoJSON FeatureCollection, WGS84.

Both are small enough to commit (parquet ~2 MB, geojson ~1 MB), so the
backend boots with real CSDI data already present. Re-run to refresh.

    cd backend && python scripts/fetch_csdi.py
"""

from __future__ import annotations

import io
import json
import logging
import sys
import zipfile
from pathlib import Path

import duckdb
import httpx

log = logging.getLogger(__name__)

UA = {"User-Agent": "tochka/0.1 (+https://github.com/echo-golf-oscar-romeo/tochka)"}

IGEOCOM_URL = (
    "https://open.hkmapservice.gov.hk/OpenData/directDownload"
    "?productName=iGeoCom&sheetName=iGeoCom&productFormat=GEOJSON"
)
DISTRICTS_URL = (
    "https://www.had.gov.hk/psi/hong-kong-administrative-boundaries"
    "/hksar_18_district_boundary.json"
)

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / "data" / "csdi"
POIS_PARQUET = OUT_DIR / "csdi_pois.parquet"
DISTRICTS_GEOJSON = OUT_DIR / "hk_districts.geojson"

# iGeoCom CLASS code → friendly category. Codes that aren't mapped keep the
# raw 3-letter code as their category (still queryable).
CLASS_LABELS = {
    "SCH": "school",
    "AMD": "medical",
    "HNC": "medical",
    "TRS": "transport",
    "TRF": "transport",
    "TRH": "transport",
    "CMF": "commercial",
    "COM": "community",
    "GOV": "government",
    "REM": "religious",
    "CUF": "cultural",
    "RSF": "recreation",
    "PAK": "park",
    "AQU": "recreation",
    "MUF": "municipal",
    "UTI": "utility",
    "BUS": "business",
    "BGD": "building",
}


def _fetch(url: str, timeout: float = 120.0) -> bytes:
    # gov.hk endpoints occasionally ship an incomplete cert chain → verify=False.
    with httpx.Client(timeout=timeout, follow_redirects=True, verify=False, headers=UA) as c:
        r = c.get(url)
        r.raise_for_status()
        return r.content


def fetch_pois() -> int:
    log.info("Downloading iGeoCom POIs …")
    raw = _fetch(IGEOCOM_URL)
    zf = zipfile.ZipFile(io.BytesIO(raw))
    member = next((n for n in zf.namelist() if n.lower().endswith((".geojson", ".json"))), None)
    if member is None:
        raise RuntimeError(f"No GeoJSON in iGeoCom zip; members={zf.namelist()}")
    fc = json.loads(zf.read(member).decode("utf-8"))
    rows: list[tuple] = []
    for f in fc.get("features", []):
        geom = f.get("geometry") or {}
        if geom.get("type") != "Point":
            continue
        coords = geom.get("coordinates") or []
        if len(coords) != 2:
            continue
        lng, lat = float(coords[0]), float(coords[1])
        p = f.get("properties", {}) or {}
        cls = (p.get("CLASS") or "").strip() or None
        rows.append((
            p.get("GEONAMEID"),
            p.get("ENGLISHNAME"),
            p.get("CHINESENAME"),
            cls,
            (p.get("TYPE") or "").strip() or None,
            CLASS_LABELS.get(cls, (cls or "other").lower()),
            lat,
            lng,
            p.get("E_DISTRICT"),
            p.get("E_ADDRESS"),
        ))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute(
        "CREATE TABLE t (geonameid BIGINT, name_en VARCHAR, name_zh VARCHAR, "
        "class VARCHAR, type VARCHAR, category VARCHAR, lat DOUBLE, lng DOUBLE, "
        "district_en VARCHAR, address_en VARCHAR)"
    )
    con.executemany("INSERT INTO t VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
    con.execute("COPY t TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(POIS_PARQUET)])
    con.close()
    print(f"OK wrote {len(rows):,} CSDI POIs to {POIS_PARQUET}")
    return len(rows)


def fetch_districts() -> int:
    log.info("Downloading HK 18-district boundaries …")
    raw = _fetch(DISTRICTS_URL, timeout=60.0)
    fc = json.loads(raw.decode("utf-8"))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    DISTRICTS_GEOJSON.write_text(json.dumps(fc, ensure_ascii=False), encoding="utf-8")
    n = len(fc.get("features", []))
    print(f"OK wrote {n} district boundaries to {DISTRICTS_GEOJSON}")
    return n


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    rc = 0
    try:
        fetch_pois()
    except Exception as e:  # noqa: BLE001
        print(f"iGeoCom POI fetch failed: {e}", file=sys.stderr)
        rc = 1
    try:
        fetch_districts()
    except Exception as e:  # noqa: BLE001
        print(f"District boundary fetch failed: {e}", file=sys.stderr)
        rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
