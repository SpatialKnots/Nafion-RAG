from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "local"
    database_url: str = "postgresql+psycopg://nafion:nafion@localhost:5432/nafion_rag?connect_timeout=5"
    data_root: Path = Path("data")
    default_collection: str = "literature"
    grobid_url: str = "http://localhost:8070"
    ocr_languages: str = "eng+rus"
    ocr_enabled: bool = True
    ocr_command: str = "ocrmypdf"
    ocr_timeout_seconds: int = Field(default=900, ge=1)
    chunk_target_chars: int = Field(default=4500, ge=1000)
    chunk_overlap_chars: int = Field(default=600, ge=0)
    hybrid_rrf_k: int = 60
    default_top_k: int = 10
    enable_external_metadata_lookup: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
