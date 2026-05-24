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
    name_col = cols.get("name") or cols.get("branch_name") or cols.get("location_name")
    if not name_col:
        raise HTTPException(400, "CSV must include a 'name' column.")

    lat_col = cols.get("lat") or cols.get("latitude") or cols.get("y")
    lng_col = cols.get("lng") or cols.get("lon") or cols.get("longitude") or cols.get("x")
    addr_col = cols.get("address") or cols.get("addr")

    if not ((lat_col and lng_col) or addr_col):
        raise HTTPException(400, "CSV must include (lat,lng) or an address column.")

    reserved = {name_col, lat_col, lng_col, addr_col}
    locations: list[Location] = []
    for _, row in df.iterrows():
        locations.append(
            Location(
                id=str(uuid.uuid4()),
                name=str(row[name_col]),
                lat=float(row[lat_col]) if lat_col and pd.notna(row[lat_col]) else None,
                lng=float(row[lng_col]) if lng_col and pd.notna(row[lng_col]) else None,
                address=str(row[addr_col]) if addr_col and pd.notna(row[addr_col]) else None,
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
