"""Environment-backed settings. Read once at startup."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parents[2] / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    app_env: str = "development"
    app_port: int = 8000
    demo_mode: bool = True

    # Qwen / DashScope
    dashscope_api_key: str = ""
    dashscope_base_url: str = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    qwen_model: str = "qwen-max"

    # CSDI
    csdi_api_key: str = ""
    csdi_base_url: str = "https://www.als.gov.hk"

    # Mapbox — isochrone polygons (CSDI 3D Pedestrian is route-only).
    mapbox_access_token: str = ""

    # Data paths
    duckdb_path: str = "./data/tochka.duckdb"
    osm_hk_pbf_path: str = "./data/hong-kong-latest.osm.pbf"
    osm_banks_path: str = "./data/osm/banks_atms_hk.json"

    # CORS
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])


@lru_cache
def get_settings() -> Settings:
    return Settings()
