# /data

Local-only. Gitignored. Contents expected:

- `hong-kong-latest.osm.pbf` — OSM HK extract (download from Geofabrik). Used by OSRM as the isochrone fallback when CSDI 3D Pedestrian Route Search is unavailable.
- `csdi/` — cached CSDI FSDT downloads (Population Distribution geopackage, Building footprints, iGeoCom POIs).
- `gmaps/` — parsed Google Maps POI snapshots (competitor banks, retail anchors). Format: parquet, partitioned by district.
- `pilot/` — pilot CSVs. `bochk_branches.csv` is the live demo input.
- `tochka.duckdb` — DuckDB database, spatial extension loaded. Holds POIs, hex grids, pre-computed isochrones for demo determinism.

Pre-fetch script (not yet written): `backend/scripts/bootstrap_data.py`.
