"""Fetch Hong Kong banks + ATMs from OpenStreetMap via Overpass.

Output: data/osm/banks_atms_hk.json — a flat JSON array of POIs. Gitignored.

Run:
    cd backend && uv run python scripts/fetch_osm_banks.py

Idempotent: re-running overwrites the file. Polite to Overpass — single query,
~5–15s, well under the public Overpass instance's rate limit. Keep it manual:
do not auto-run from the backend at request time.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import httpx

# HK bounding box, slightly wider than admin boundaries to catch outlying islands.
HK_BBOX = (22.15, 113.83, 22.57, 114.45)   # S, W, N, E

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

QUERY = """
[out:json][timeout:90];
(
  node["amenity"="bank"]({bbox});
  way ["amenity"="bank"]({bbox});
  node["amenity"="atm"]({bbox});
  way ["amenity"="atm"]({bbox});
);
out center tags;
""".strip()


REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_PATH = REPO_ROOT / "data" / "osm" / "banks_atms_hk.json"


def _coords(el: dict) -> tuple[float, float] | None:
    if el.get("type") == "node":
        return el.get("lat"), el.get("lon")
    centre = el.get("center")
    if centre:
        return centre.get("lat"), centre.get("lon")
    return None


def _normalise(el: dict) -> dict | None:
    tags = el.get("tags") or {}
    amenity = tags.get("amenity")
    if amenity not in ("bank", "atm"):
        return None
    latlon = _coords(el)
    if not latlon or latlon[0] is None or latlon[1] is None:
        return None
    name = tags.get("name") or tags.get("operator") or tags.get("brand") or "Unknown"
    brand = tags.get("brand") or tags.get("operator") or name
    return {
        "id": f"{el.get('type', 'el')}/{el.get('id')}",
        "type": amenity,                       # 'bank' | 'atm'
        "name": name,
        "brand": brand,
        "lat": float(latlon[0]),
        "lng": float(latlon[1]),
        "addr_street": tags.get("addr:street"),
        "addr_housenumber": tags.get("addr:housenumber"),
        "addr_district": tags.get("addr:district") or tags.get("addr:suburb"),
        "operator": tags.get("operator"),
        "atm": tags.get("atm") == "yes" or amenity == "atm",
    }


def fetch() -> list[dict]:
    bbox_str = ",".join(str(x) for x in HK_BBOX)
    body = QUERY.format(bbox=bbox_str)
    t0 = time.monotonic()
    # Overpass requires a real User-Agent and the QL text in `data=`. Some
    # instances reject default httpx UAs with 406.
    headers = {
        "User-Agent": "Tochka/0.1 (location intelligence; github.com/echo-golf-oscar-romeo/tochka)",
        "Accept": "application/json",
    }
    with httpx.Client(timeout=120.0, headers=headers) as client:
        r = client.post(OVERPASS_URL, data={"data": body})
    elapsed = time.monotonic() - t0
    r.raise_for_status()
    raw = r.json()
    elements = raw.get("elements", [])
    pois: list[dict] = []
    for el in elements:
        norm = _normalise(el)
        if norm:
            pois.append(norm)
    print(f"Overpass returned {len(elements)} elements in {elapsed:.1f}s; "
          f"kept {len(pois)} normalised POIs.", file=sys.stderr)
    return pois


def _safe_print(s: str) -> None:
    """Print without crashing on Windows cp1252 consoles when text contains CJK."""
    try:
        print(s)
    except UnicodeEncodeError:
        enc = sys.stdout.encoding or "ascii"
        print(s.encode(enc, errors="replace").decode(enc, errors="replace"))


def main() -> int:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    pois = fetch()
    OUT_PATH.write_text(json.dumps(pois, ensure_ascii=False, indent=2), encoding="utf-8")
    banks = sum(1 for p in pois if p["type"] == "bank")
    atms = sum(1 for p in pois if p["type"] == "atm")
    brands: dict[str, int] = {}
    for p in pois:
        brands[p["brand"]] = brands.get(p["brand"], 0) + 1
    top_brands = sorted(brands.items(), key=lambda kv: -kv[1])[:8]
    _safe_print(f"Wrote {OUT_PATH.relative_to(REPO_ROOT)}: {len(pois)} POIs "
                f"({banks} banks, {atms} ATMs).")
    _safe_print("Top brands: " + ", ".join(f"{b} ({n})" for b, n in top_brands))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
