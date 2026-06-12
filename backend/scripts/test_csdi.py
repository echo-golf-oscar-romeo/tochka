"""CSDI connectivity self-test — run this when you suspect the APIs are down.

    cd backend && python scripts/test_csdi.py

Probes every CSDI / HK-gov surface the app uses and prints PASS/FAIL with
the reason. Exit code 0 = all live endpoints reachable.
"""

from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")


async def main() -> int:
    import warnings

    warnings.filterwarnings("ignore")
    from app.clients.csdi import get_csdi
    from app.clients.ddb import (
        ensure_csdi_pois_loaded,
        ensure_districts_loaded,
        ensure_kontur_loaded,
        get_duckdb,
    )

    failures = 0

    def report(name: str, ok: bool, detail: str) -> None:
        nonlocal failures
        print(f"  [{'PASS' if ok else 'FAIL'}] {name:28} {detail}")
        if not ok:
            failures += 1

    c = get_csdi()

    # 1. ALS geocoding (live HTTP)
    try:
        r = await c.als_lookup("International Commerce Centre", n=1)
        report("ALS geocoding", bool(r), f"{len(r)} result(s)" if r else "no results")
    except Exception as e:  # noqa: BLE001
        report("ALS geocoding", False, str(e)[:90])

    # 2. locationSearch (live HTTP, EPSG:2326 conversion)
    try:
        r = await c.location_search("Mong Kok MTR", n=2)
        ok = bool(r) and 22.0 < r[0]["lat"] < 23.0
        report("locationSearch", ok, f"{r[0]['name']} @ {r[0]['lat']:.4f}" if r else "no results")
    except Exception as e:  # noqa: BLE001
        report("locationSearch", False, str(e)[:90])

    # 3. Local CSDI POI table (committed parquet)
    conn = get_duckdb()
    ok = ensure_csdi_pois_loaded(conn)
    n = conn.execute("SELECT COUNT(*) FROM csdi_pois").fetchone()[0] if ok else 0
    report("csdi_pois table", ok and n > 30000, f"{n:,} POIs")

    # 4. search_nearby against the table
    try:
        near = await c.search_nearby(22.2837, 114.1370, category="school", radius_m=1500, limit=3)
        report("search_nearby", bool(near), f"{len(near)} schools near HKU" if near else "none")
    except Exception as e:  # noqa: BLE001
        report("search_nearby", False, str(e)[:90])

    # 5. Districts + population
    ok = ensure_districts_loaded(conn)
    if ok:
        n, pop = conn.execute("SELECT COUNT(*), SUM(population) FROM hk_districts").fetchone()
        report("hk_districts", n == 18 and (pop or 0) > 7e6, f"{n} districts, pop {int(pop or 0):,}")
    else:
        report("hk_districts", False, "load failed — run scripts/fetch_csdi.py")

    # 6. Kontur grid sanity (axis order!)
    ok = ensure_kontur_loaded(conn)
    if ok:
        mn, mx = conn.execute("SELECT MIN(lat), MAX(lat) FROM kontur_pop_hex").fetchone()
        report("kontur_pop_hex", 21.5 < mn < mx < 23.0, f"lat {mn:.2f}..{mx:.2f}")
    else:
        report("kontur_pop_hex", False, "load failed")

    await c.aclose()
    print(f"\n{'ALL GOOD' if failures == 0 else f'{failures} FAILURE(S)'} — "
          "live endpoints: ALS + locationSearch; everything else is committed local data.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
