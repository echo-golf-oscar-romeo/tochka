"""POST /upload — accept a CSV of locations, return a network_id."""

from __future__ import annotations

import io
import uuid

import pandas as pd
from fastapi import APIRouter, File, HTTPException, UploadFile

from app.models.network import Location, Network
from app.store import store

router = APIRouter(prefix="/upload", tags=["upload"])


@router.post("", response_model=Network)
async def upload_csv(file: UploadFile = File(...)) -> Network:
    """Parse a CSV. Required columns: at minimum `name` and (`lat`,`lng`) OR `address`.

    Optional columns are preserved on each Location as `raw_fields`. The orchestrator
    reads them when classifying the network and choosing a demand model.
    """
    if not file.filename or not file.filename.lower().endswith((".csv", ".tsv")):
        raise HTTPException(400, "Upload a .csv or .tsv file.")

    raw = await file.read()
    sep = "\t" if file.filename.lower().endswith(".tsv") else ","
    try:
        df = pd.read_csv(io.BytesIO(raw), sep=sep)
    except Exception as e:
        raise HTTPException(400, f"Failed to parse CSV: {e}") from e

    if df.empty:
        raise HTTPException(400, "CSV is empty.")

    cols = {c.lower(): c for c in df.columns}

    def _first(*aliases: str) -> str | None:
        for a in aliases:
            if a in cols:
                return cols[a]
        return None

    name_col = _first("name", "branch_name", "location_name")
    if not name_col:
        raise HTTPException(400, "CSV must include a 'name' column.")

    lat_col = _first("lat", "latitude", "y")
    lng_col = _first("lng", "lon", "longitude", "x")
    addr_col = _first("address", "addr")

    if not ((lat_col and lng_col) or addr_col):
        raise HTTPException(400, "CSV must include (lat,lng) or an address column.")

    # Optional operational columns. We accept several common aliases so
    # uploaders don't have to rename columns. First match wins per slot.
    capacity_col = _first("capacity", "max_capacity", "cap", "hourly_capacity",
                          "daily_capacity", "capacity_per_day")
    volume_col = _first("actual_volume", "volume", "traffic", "footfall",
                        "visitors", "daily_visitors", "customers_per_day",
                        "monthly_transactions", "transactions", "utilization",
                        "utilisation", "throughput")

    reserved = {c for c in (name_col, lat_col, lng_col, addr_col, capacity_col, volume_col) if c}
    locations: list[Location] = []
    for _, row in df.iterrows():
        def _num(col: str | None) -> float | None:
            if not col or pd.isna(row[col]):
                return None
            try:
                return float(row[col])
            except (TypeError, ValueError):
                return None
        locations.append(
            Location(
                id=str(uuid.uuid4()),
                name=str(row[name_col]),
                lat=_num(lat_col),
                lng=_num(lng_col),
                address=str(row[addr_col]) if addr_col and pd.notna(row[addr_col]) else None,
                capacity=_num(capacity_col),
                actual_volume=_num(volume_col),
                raw_fields={k: row[k] for k in df.columns if k not in reserved and pd.notna(row[k])},
            )
        )

    network = Network(
        id=str(uuid.uuid4()),
        source_filename=file.filename,
        locations=locations,
    )
    store.networks[network.id] = network
    return network
