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

    # LLM provider — "qwen" (DashScope) or "deepseek". Both are OpenAI-compatible.
    llm_provider: str = "qwen"

    # Qwen / DashScope
    dashscope_api_key: str = ""
    dashscope_base_url: str = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    qwen_model: str = "qwen-max"

    # DeepSeek (fallback while DashScope is pending activation)
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"

    # OpenRouter — multi-provider routing fallback. Works in HK; openly-
    # licensed Qwen models are cheap (~$0.40 / M input tokens).
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # CSDI — real Hong Kong Common Spatial Data Infrastructure endpoints.
    csdi_api_key: str = ""
    csdi_base_url: str = "https://www.als.gov.hk"                       # ALS geocoding
    csdi_locationsearch_url: str = "https://www.map.gov.hk/gs/api/v1.0.0/locationSearch"
    # gov.hk certs sometimes ship an incomplete chain — allow opting out of
    # TLS verification for these specific hosts (defence: only CSDI hosts).
    csdi_tls_verify: bool = False

    # Mapbox — isochrone polygons (CSDI 3D Pedestrian is route-only).
    mapbox_access_token: str = ""

    # Data paths
    duckdb_path: str = "./data/tochka.duckdb"
    osm_hk_pbf_path: str = "./data/hong-kong-latest.osm.pbf"
    osm_banks_path: str = "./data/osm/banks_atms_hk.json"
    csdi_pois_path: str = "./data/csdi/csdi_pois.parquet"
    hk_districts_path: str = "./data/csdi/hk_districts.geojson"

    # CORS
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])


@lru_cache
def get_settings() -> Settings:
    return Settings()
