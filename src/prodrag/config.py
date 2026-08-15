from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_TENANT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


class Settings(BaseSettings):
    """Environment-only configuration for the RAG API and ingestion worker."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        populate_by_name=True,
    )

    environment: Literal["development", "test", "production"] = Field(
        default="development", validation_alias="RAG_ENVIRONMENT"
    )
    log_level: str = Field(default="INFO", validation_alias="RAG_LOG_LEVEL")
    data_dir: Path = Field(default=Path("./data"), validation_alias="RAG_DATA_DIR")
    admin_api_key: SecretStr | None = Field(
        default=None, validation_alias="RAG_ADMIN_API_KEY"
    )
    query_api_key: SecretStr | None = Field(
        default=None, validation_alias="RAG_QUERY_API_KEY"
    )
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://127.0.0.1:4173",
            "http://localhost:4173",
        ],
        validation_alias="RAG_CORS_ORIGINS",
    )
    tenant_admin_api_keys: dict[str, SecretStr] = Field(
        default_factory=dict, validation_alias="RAG_TENANT_ADMIN_API_KEYS"
    )
    tenant_query_api_keys: dict[str, SecretStr] = Field(
        default_factory=dict, validation_alias="RAG_TENANT_QUERY_API_KEYS"
    )

    oci_region: str = Field(default="us-chicago-1", validation_alias="OCI_REGION")
    oci_service_endpoint: str | None = Field(
        default=None, validation_alias="OCI_SERVICE_ENDPOINT"
    )
    oci_compartment_id: str | None = Field(
        default=None, validation_alias="OCI_COMPARTMENT_OCID"
    )
    oci_config_file: Path = Field(
        default=Path("~/.oci/config"), validation_alias="OCI_CONFIG_FILE"
    )
    oci_profile: str = Field(default="DEFAULT", validation_alias="OCI_PROFILE")
    oci_auth_type: Literal[
        "API_KEY", "SECURITY_TOKEN", "INSTANCE_PRINCIPAL", "RESOURCE_PRINCIPAL"
    ] = Field(default="API_KEY", validation_alias="OCI_AUTH_TYPE")
    oci_embed_model: str = Field(
        default="cohere.embed-v4.0", validation_alias="OCI_EMBED_MODEL"
    )
    oci_embed_dimension: int = Field(
        default=1536, ge=256, le=4096, validation_alias="OCI_EMBED_DIMENSION"
    )
    oci_rerank_enabled: bool = Field(default=True, validation_alias="OCI_RERANK_ENABLED")
    oci_rerank_model: str = Field(
        default="cohere.rerank-v4.0-fast", validation_alias="OCI_RERANK_MODEL"
    )
    oci_chat_model: str = Field(
        default="openai.gpt-oss-120b", validation_alias="OCI_CHAT_MODEL"
    )

    qdrant_url: str = Field(default="http://localhost:6333", validation_alias="QDRANT_URL")
    qdrant_path: Path | None = Field(default=None, validation_alias="QDRANT_PATH")
    qdrant_api_key: SecretStr | None = Field(default=None, validation_alias="QDRANT_API_KEY")
    qdrant_collection: str = Field(
        default="technical_support_v2", validation_alias="QDRANT_COLLECTION"
    )
    qdrant_hnsw_enabled: bool = Field(
        default=False, validation_alias="QDRANT_HNSW_ENABLED"
    )
    qdrant_hnsw_m: int = Field(default=16, ge=4, le=64, validation_alias="QDRANT_HNSW_M")
    qdrant_hnsw_ef_construct: int = Field(
        default=128, ge=16, le=1024, validation_alias="QDRANT_HNSW_EF_CONSTRUCT"
    )
    qdrant_hnsw_ef_search: int = Field(
        default=128, ge=16, le=1024, validation_alias="QDRANT_HNSW_EF_SEARCH"
    )
    bm25_model: str = Field(default="Qdrant/bm25", validation_alias="RAG_BM25_MODEL")
    bm25_language: Literal["english"] = Field(
        default="english", validation_alias="RAG_BM25_LANGUAGE"
    )
    redis_url: str = Field(default="redis://localhost:6379/0", validation_alias="REDIS_URL")

    max_file_mb: int = Field(default=25, ge=1, le=200, validation_alias="RAG_MAX_FILE_MB")
    max_pdf_pages: int = Field(
        default=200, ge=1, le=2_000, validation_alias="RAG_MAX_PDF_PAGES"
    )
    pdf_ocr_enabled: bool = Field(
        default=False, validation_alias="RAG_PDF_OCR_ENABLED"
    )
    pdf_table_structure_enabled: bool = Field(
        default=False, validation_alias="RAG_PDF_TABLE_STRUCTURE_ENABLED"
    )
    pdf_force_backend_text: bool = Field(
        default=True, validation_alias="RAG_PDF_FORCE_BACKEND_TEXT"
    )
    parent_max_chars: int = Field(
        default=12_000, ge=2_000, le=50_000, validation_alias="RAG_PARENT_MAX_CHARS"
    )
    chunk_size_tokens: int = Field(
        default=450, ge=100, le=2_000, validation_alias="RAG_CHUNK_SIZE_TOKENS"
    )
    semantic_threshold: float = Field(
        default=0.72, ge=0.0, le=1.0, validation_alias="RAG_SEMANTIC_THRESHOLD"
    )
    retrieval_candidates: int = Field(
        default=20, ge=5, le=100, validation_alias="RAG_RETRIEVAL_CANDIDATES"
    )
    final_contexts: int = Field(
        default=5, ge=1, le=20, validation_alias="RAG_FINAL_CONTEXTS"
    )
    min_rerank_score: float = Field(
        default=0.15, ge=0.0, le=1.0, validation_alias="RAG_MIN_RERANK_SCORE"
    )
    confidence_medium_threshold: float = Field(
        default=0.35,
        ge=0.0,
        le=1.0,
        validation_alias="RAG_CONFIDENCE_MEDIUM_THRESHOLD",
    )
    confidence_high_threshold: float = Field(
        default=0.75,
        ge=0.0,
        le=1.0,
        validation_alias="RAG_CONFIDENCE_HIGH_THRESHOLD",
    )
    context_char_budget: int = Field(
        default=30_000, ge=4_000, le=100_000, validation_alias="RAG_CONTEXT_CHAR_BUDGET"
    )
    job_ttl_seconds: int = Field(default=604_800, ge=3_600, validation_alias="RAG_JOB_TTL")
    query_timeout_seconds: float = Field(
        default=45.0, ge=1.0, le=300.0, validation_alias="RAG_QUERY_TIMEOUT_SECONDS"
    )
    model_retry_attempts: int = Field(
        default=3, ge=1, le=5, validation_alias="RAG_MODEL_RETRY_ATTEMPTS"
    )
    metrics_enabled: bool = Field(default=True, validation_alias="RAG_METRICS_ENABLED")
    upload_scan_command: list[str] = Field(
        default_factory=list, validation_alias="RAG_UPLOAD_SCAN_COMMAND"
    )
    upload_scan_timeout_seconds: int = Field(
        default=120, ge=5, le=600, validation_alias="RAG_UPLOAD_SCAN_TIMEOUT_SECONDS"
    )
    uploads_prevalidated: bool = Field(
        default=False, validation_alias="RAG_UPLOADS_PREVALIDATED"
    )

    @property
    def effective_oci_service_endpoint(self) -> str:
        return self.oci_service_endpoint or (
            f"https://inference.generativeai.{self.oci_region}.oci.oraclecloud.com"
        )

    @property
    def expanded_oci_config_file(self) -> str:
        return str(self.oci_config_file.expanduser())

    @property
    def max_file_bytes(self) -> int:
        return self.max_file_mb * 1024 * 1024

    @field_validator("qdrant_path", mode="before")
    @classmethod
    def normalize_blank_qdrant_path(cls, value):
        return None if value == "" else value

    @model_validator(mode="after")
    def validate_production_settings(self) -> Settings:
        if self.confidence_high_threshold <= self.confidence_medium_threshold:
            raise ValueError(
                "RAG_CONFIDENCE_HIGH_THRESHOLD must be greater than "
                "RAG_CONFIDENCE_MEDIUM_THRESHOLD"
            )
        if self.qdrant_hnsw_enabled and self.qdrant_path:
            raise ValueError(
                "QDRANT_HNSW_ENABLED requires a Qdrant server via QDRANT_URL; "
                "embedded QDRANT_PATH mode uses exact in-process search"
            )
        if self.environment != "production":
            return self

        missing: list[str] = []
        if not self.oci_compartment_id:
            missing.append("OCI_COMPARTMENT_OCID")
        if not self.tenant_admin_api_keys:
            missing.append("RAG_TENANT_ADMIN_API_KEYS")
        if not self.tenant_query_api_keys:
            missing.append("RAG_TENANT_QUERY_API_KEYS")
        if not self.upload_scan_command and not self.uploads_prevalidated:
            missing.append("RAG_UPLOAD_SCAN_COMMAND or RAG_UPLOADS_PREVALIDATED=true")
        if self.upload_scan_command and not any(
            "{path}" in part for part in self.upload_scan_command
        ):
            missing.append("RAG_UPLOAD_SCAN_COMMAND containing a {path} argument")
        all_key_entries = [
            (role, tenant, secret)
            for role, mapping in (
                ("admin", self.tenant_admin_api_keys),
                ("query", self.tenant_query_api_keys),
            )
            for tenant, secret in mapping.items()
        ]
        invalid_keys = sorted(
            f"{role}:{tenant}"
            for role, tenant, secret in all_key_entries
            if len(secret.get_secret_value()) < 32
        )
        if invalid_keys:
            missing.append(
                "tenant API keys of at least 32 characters for: " + ", ".join(invalid_keys)
            )
        invalid_tenants = sorted(
            {tenant for _, tenant, _ in all_key_entries if not _TENANT_ID_RE.fullmatch(tenant)}
        )
        if invalid_tenants:
            missing.append("valid tenant IDs for: " + ", ".join(invalid_tenants))
        key_values = [secret.get_secret_value() for _, _, secret in all_key_entries]
        if len(key_values) != len(set(key_values)):
            missing.append("unique values for every tenant admin/query API key")
        if missing:
            raise ValueError("Missing production configuration: " + ", ".join(missing))
        return self


SUPPORTED_EXTENSIONS = frozenset({".pdf", ".docx", ".pptx", ".html", ".htm", ".md", ".txt"})


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
