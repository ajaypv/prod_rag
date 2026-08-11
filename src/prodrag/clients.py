from __future__ import annotations

from functools import lru_cache

from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel

from prodrag.config import Settings, get_settings


def _require_compartment(settings: Settings) -> str:
    """Fail early when an OCI operation has no compartment to bill and authorize."""
    if not settings.oci_compartment_id:
        raise RuntimeError("OCI_COMPARTMENT_OCID is required for OCI model calls")
    return settings.oci_compartment_id


class OCIQueryDocumentEmbeddings(Embeddings):
    """Expose OCI's asymmetric embedding modes through LangChain's one interface.

    Cohere Embed uses ``SEARCH_DOCUMENT`` for indexed passages and ``SEARCH_QUERY`` for a
    question. The model and dimension remain identical, but the input type tells the model
    which side of the retrieval comparison it is encoding.
    """

    def __init__(self, document_embeddings: Embeddings, query_embeddings: Embeddings) -> None:
        self.document_embeddings = document_embeddings
        self.query_embeddings = query_embeddings

    @property
    def client(self):
        """Expose the shared authenticated OCI SDK client for native reranking."""
        return getattr(self.document_embeddings, "client", None)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Encode stored passages with the OCI ``SEARCH_DOCUMENT`` client."""
        return self.document_embeddings.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        """Encode a customer question with the OCI ``SEARCH_QUERY`` client."""
        return self.query_embeddings.embed_query(text)


@lru_cache(maxsize=1)
def get_embeddings() -> Embeddings:
    """Create and cache paired OCI document/query embedding clients.

    The returned adapter is shared by semantic chunking and Qdrant. During ingestion Chonkie
    embeds sentence windows to choose boundaries, then Qdrant embeds the final children for
    storage. During querying Qdrant calls only ``embed_query``.
    """
    from langchain_oci import OCIGenAIEmbeddings

    settings = get_settings()
    # Both encoders use the same model and dimension. Only the task-specific input mode
    # differs, which is required for asymmetric document/query retrieval embeddings.
    common = {
        "model_id": settings.oci_embed_model,
        "service_endpoint": settings.effective_oci_service_endpoint,
        "compartment_id": _require_compartment(settings),
        "auth_type": settings.oci_auth_type,
        "auth_profile": settings.oci_profile,
        "auth_file_location": settings.expanded_oci_config_file,
        "batch_size": 96,
        "truncate": "END",
        "output_dimensions": settings.oci_embed_dimension,
    }
    document_embeddings = OCIGenAIEmbeddings(
        **common,
        input_type="SEARCH_DOCUMENT",
    )
    query_embeddings = OCIGenAIEmbeddings(
        **common,
        # Reuse the authenticated native client instead of opening a second OCI client.
        client=document_embeddings.client,
        input_type="SEARCH_QUERY",
    )
    return OCIQueryDocumentEmbeddings(document_embeddings, query_embeddings)


@lru_cache(maxsize=1)
def get_chat_model() -> BaseChatModel:
    """Create the deterministic OCI chat client shared by triage and answering."""
    from langchain_oci import ChatOCIGenAI

    settings = get_settings()
    model_kwargs: dict[str, int | float] = {"temperature": 0.0, "max_tokens": 900}
    return ChatOCIGenAI(
        model_id=settings.oci_chat_model,
        service_endpoint=settings.effective_oci_service_endpoint,
        compartment_id=_require_compartment(settings),
        auth_type=settings.oci_auth_type,
        auth_profile=settings.oci_profile,
        auth_file_location=settings.expanded_oci_config_file,
        model_kwargs=model_kwargs,
    )


def get_native_oci_client():
    """Expose the OCI SDK inference client required by the native rerank operation."""
    embeddings = get_embeddings()
    client = getattr(embeddings, "client", None)
    if client is None:
        raise RuntimeError("The LangChain OCI embeddings client was not initialized")
    return client
