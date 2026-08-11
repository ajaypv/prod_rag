from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Load and validate every setting used by the CLI pipeline.

    The CLI never constructs this class directly. ``get_settings()`` reads ``.env`` once,
    caches the validated object, and the composition functions in ``container.py`` pass that
    same configuration to ingestion, retrieval, and answering services. For example,
    ``RAG_CHUNK_SIZE_TOKENS=450`` becomes ``settings.chunk_size_tokens`` and is passed to
    ``SemanticChunkingStrategy``.
    """

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
        default="technical_support_v1", validation_alias="QDRANT_COLLECTION"
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
    max_file_mb: int = Field(default=25, ge=1, le=200, validation_alias="RAG_MAX_FILE_MB")
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
    @property
    def effective_oci_service_endpoint(self) -> str:
        """Return an explicit endpoint or derive OCI's regional inference endpoint."""
        return self.oci_service_endpoint or (
            f"https://inference.generativeai.{self.oci_region}.oci.oraclecloud.com"
        )

    @property
    def expanded_oci_config_file(self) -> str:
        """Expand ``~`` before passing the OCI config path to SDK clients."""
        return str(self.oci_config_file.expanduser())

    @property
    def max_file_bytes(self) -> int:
        """Translate the human-friendly MiB limit into the byte limit used by parsers."""
        return self.max_file_mb * 1024 * 1024

    @model_validator(mode="after")
    def validate_production_settings(self) -> Settings:
        """Reject combinations that would make the CLI misleading or unusable.

        Embedded Qdrant is always exact search, so accepting HNSW with ``QDRANT_PATH`` would
        falsely suggest an approximate graph exists. Production also requires a compartment
        because OCI embeddings, reranking, triage, and answering all need it.
        """
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

        if not self.oci_compartment_id:
            raise ValueError("Missing production configuration: OCI_COMPARTMENT_OCID")
        return self


SUPPORTED_EXTENSIONS = frozenset({".pdf", ".docx", ".pptx", ".html", ".htm", ".md", ".txt"})


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return one validated settings object for the lifetime of this CLI process."""
    return Settings()
