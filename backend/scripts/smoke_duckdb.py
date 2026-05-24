"""Quick smoke test that the new DuckDB-spatial tool paths actually execute
against the real OSM data, instead of silently falling back to canned.

Run:
    cd backend && uv run python scripts/smoke_duckdb.py
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import tempfile
from pathlib import Path

# Force real-data paths, no LLM HTTP calls.
os.environ["DEMO_MODE"] = "false"
os.environ["DASHSCOPE_API_KEY"] = ""
os.environ["DEEPSEEK_API_KEY"] = ""
os.environ["MAPBOX_ACCESS_TOKEN"] = ""
# Avoid contending with a running uvicorn for the default duckdb file lock.
_smoke_db = Path(tempfile.gettempdir()) / "tochka_smoke.duckdb"
_smoke_db.unlink(missing_ok=True)
os.environ["DUCKDB_PATH"] = str(_smoke_db)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.clients.ddb import ensure_osm_loaded, get_duckdb       # noqa: E402
from app.mock import canned                                      # noqa: E402
from app.models.network import Location                          # noqa: E402
from app.tools.competitors import competitors_in_radius          # noqa: E402
from app.tools.modeling import anomaly_detect, huff_model        # noqa: E402
from app.tools.spatial import nearest_neighbor, points_in_polygon # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s - %(message)s")


def _safe(s) -> str:
    """Encode any string for the current stdout encoding (handles cp1252)."""
    if s is None:
        return ""
    enc = sys.stdout.encoding or "ascii"
    return str(s).encode(enc, errors="replace").decode(enc, errors="replace")


def make_locations() -> list[Location]:
    """Eight HK branches mirroring the sample CSV. Includes capacity + actuals."""
    sample = [
        ("BR001", "Sham Shui Po Branch",   22.3311, 114.1623, 1800.0, 2150.0),
        ("BR002", "Cheung Sha Wan Branch", 22.3389, 114.1559, 1800.0, 1620.0),
        ("BR005", "Mong Kok Branch",       22.3193, 114.1696, 1800.0, 2400.0),
        ("BR007", "Tsim Sha Tsui Branch",  22.2988, 114.1722, 1800.0, 1910.0),
        ("BR008", "Central District",      22.2811, 114.1592, 2400.0, 1720.0),
        ("BR009", "Causeway Bay Branch",   22.2804, 114.1834, 1800.0, 2310.0),
        ("BR010", "North Point Branch",    22.2912, 114.2003, 1800.0, 1530.0),
        ("BR012", "Tsing Yi Branch",       22.3580, 114.1067, 1800.0, 1920.0),
    ]
    return [Location(id=i, name=n, lat=la, lng=lo, capacity=c, actual_volume=v)
            for (i, n, la, lo, c, v) in sample]


async def main() -> int:
    locations = make_locations()
    print(f"\n[1] OSM loader\n----")
    conn = get_duckdb()
    if not ensure_osm_loaded(conn):
        print("OSM file missing — run scripts/fetch_osm_banks.py first.")
        return 2
    n = conn.execute("SELECT COUNT(*) FROM osm_pois").fetchone()[0]
    print(f"osm_pois has {n:,} rows.")

    print(f"\n[2] competitors_in_radius (radius=500m, banks)\n----")
    comp = await competitors_in_radius(locations, radius_m=500, categories=("bank",))
    print(f"got {len(comp)} competitors")
    for c in comp[:5]:
        print(f"  {c['distance_m']:>6}m  {_safe(c['brand'])}  nearest to {c['nearest_user_location_id']}")

    print(f"\n[3] points_in_polygon (user points x canned isochrones)\n----")
    # Need polygons — use canned isochrones since Mapbox would require a token.
    isos = canned.isochrones_walk(locations, minutes=10)
    points = [{"id": loc.id, "lat": loc.lat, "lng": loc.lng} for loc in locations]
    pip = await points_in_polygon(points, isos)
    print(f"got {len(pip)} polygon->points groups")
    for row in pip[:3]:
        print(f"  polygon {row['polygon_id']}: {len(row['point_ids'])} point(s) inside")

    print(f"\n[4] nearest_neighbor (locations x first 50 competitors, k=2)\n----")
    nn = await nearest_neighbor(points, comp[:50], k=2)
    for row in nn[:3]:
        ns = ", ".join(f"{nb['id']}@{nb['distance_m']}m" for nb in row["neighbors"])
        print(f"  {row['id']} -> {ns}")

    print(f"\n[5] huff_model (locations x competitors x canned population)\n----")
    pop = canned.population_in_polygon(isos)
    scores = await huff_model(locations, comp, pop)
    for s in scores[:5]:
        print(f"  {_safe(s['name']):<24}  pop={s['catchment_pop']:>6}  "
              f"comp={s['comp_count']:>3}  share={s['share']:.2f}  expected={s['expected_demand']:>6}")

    print(f"\n[6] anomaly_detect (using huff scores with actuals)\n----")
    anomalies = await anomaly_detect(scores)
    if not anomalies:
        print("  (no anomalies flagged — actuals tracked expectation closely)")
    for a in anomalies:
        print(f"  [{a['kind']:>5}] {_safe(a['rationale'])}")

    print("\nSmoke OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
