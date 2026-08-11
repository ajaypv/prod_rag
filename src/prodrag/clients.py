from __future__ import annotations

from functools import lru_cache

from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel

from prodrag.config import Settings, get_settings


def _require_compartment(settings: Settings) -> str:
    if not settings.oci_compartment_id:
        raise RuntimeError("OCI_COMPARTMENT_OCID is required for OCI model calls")
    return settings.oci_compartment_id


class OCIQueryDocumentEmbeddings(Embeddings):
    """Use OCI's asymmetric search modes while sharing one native OCI client."""

    def __init__(self, document_embeddings: Embeddings, query_embeddings: Embeddings) -> None:
        self.document_embeddings = document_embeddings
        self.query_embeddings = query_embeddings

    @property
    def client(self):
        return getattr(self.document_embeddings, "client", None)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.document_embeddings.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        return self.query_embeddings.embed_query(text)


@lru_cache(maxsize=1)
def get_embeddings() -> Embeddings:
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
    embeddings = get_embeddings()
    client = getattr(embeddings, "client", None)
    if client is None:
        raise RuntimeError("The LangChain OCI embeddings client was not initialized")
    return client
