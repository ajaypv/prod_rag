from langchain_core.embeddings import Embeddings

from prodrag.clients import OCIQueryDocumentEmbeddings


class RecordingEmbeddings(Embeddings):
    def __init__(self, value: float) -> None:
        self.value = value
        self.document_calls: list[list[str]] = []
        self.query_calls: list[str] = []

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.document_calls.append(texts)
        return [[self.value] for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        self.query_calls.append(text)
        return [self.value]


def test_embedding_router_keeps_document_and_query_modes_separate() -> None:
    document_embeddings = RecordingEmbeddings(1.0)
    query_embeddings = RecordingEmbeddings(2.0)
    embeddings = OCIQueryDocumentEmbeddings(document_embeddings, query_embeddings)

    assert embeddings.embed_documents(["document"]) == [[1.0]]
    assert embeddings.embed_query("question") == [2.0]
    assert document_embeddings.document_calls == [["document"]]
    assert document_embeddings.query_calls == []
    assert query_embeddings.document_calls == []
    assert query_embeddings.query_calls == ["question"]
