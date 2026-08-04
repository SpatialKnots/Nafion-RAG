from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
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
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    hybrid_rrf_k: int = Field(default=60, ge=1)
    hybrid_candidate_multiplier: int = Field(default=5, ge=1)
    default_top_k: int = 10
    rag_provider: str = "extractive"
    rag_retrieval_method: str = "hybrid"
    rag_top_k: int = Field(default=5, ge=1)
    rag_max_claims: int = Field(default=5, ge=1)
    rag_ollama_url: str = "http://127.0.0.1:11434"
    rag_model: str = ""
    rag_timeout_seconds: int = Field(default=120, ge=1)
    enable_external_metadata_lookup: bool = False
    upload_max_file_size_mb: int = Field(default=100, ge=1)
    upload_max_files_per_request: int = Field(default=10, ge=1)
    upload_read_chunk_bytes: int = Field(default=1024 * 1024, ge=1024)
    ingestion_poll_seconds: int = Field(default=2, ge=1)
    ingestion_lease_seconds: int = Field(default=1200, ge=1)
    ingestion_heartbeat_seconds: int = Field(default=30, ge=1)
    ingestion_max_attempts: int = Field(default=3, ge=1)
    ingestion_failed_retention_days: int = Field(default=7, ge=1)
    ingestion_worker_id: str = ""
    worker_role: str = "all"
    vector_auto_rebuild_enabled: bool = True
    vector_rebuild_debounce_seconds: int = Field(default=10, ge=0)
    vector_rebuild_poll_seconds: int = Field(default=2, ge=1)
    vector_rebuild_lease_seconds: int = Field(default=1800, ge=1)
    vector_rebuild_heartbeat_seconds: int = Field(default=30, ge=1)
    vector_rebuild_max_attempts: int = Field(default=3, ge=1)
    vector_rebuild_batch_size: int = Field(default=64, ge=1)
    vector_index_keep_generations: int = Field(default=2, ge=1)
    vector_staging_retention_hours: int = Field(default=24, ge=1)

    @model_validator(mode="after")
    def validate_ingestion_timing(self) -> Settings:
        if self.ingestion_heartbeat_seconds >= self.ingestion_lease_seconds:
            raise ValueError("INGESTION_HEARTBEAT_SECONDS must be less than INGESTION_LEASE_SECONDS")
        if self.vector_rebuild_heartbeat_seconds >= self.vector_rebuild_lease_seconds:
            raise ValueError("VECTOR_REBUILD_HEARTBEAT_SECONDS must be less than VECTOR_REBUILD_LEASE_SECONDS")
        if self.worker_role not in {"ingestion", "vector", "all"}:
            raise ValueError("WORKER_ROLE must be one of: ingestion, vector, all")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
