from prodrag.retrieval.sparse import LocalBM25SparseEmbeddings


def test_local_sparse_embeddings_are_deterministic_and_weight_repeated_terms() -> None:
    embeddings = LocalBM25SparseEmbeddings()

    first = embeddings.embed_documents(["HTTP 429 retry retry"])[0]
    second = embeddings.embed_documents(["HTTP 429 retry retry"])[0]
    query = embeddings.embed_query("HTTP 429 retry")

    assert first == second
    assert len(first.indices) == len(set(first.indices)) == 3
    assert max(first.values) > 1.0
    assert set(query.values) == {1.0}
