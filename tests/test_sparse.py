from prodrag.retrieval.sparse import create_local_bm25_sparse_embeddings


def test_local_bm25_uses_configured_model_language_and_cache(monkeypatch, tmp_path) -> None:
    captured = {}
    (tmp_path / "english.txt").write_text("the\nand\n", encoding="utf-8")

    class FakeFastEmbedSparse:
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)

    monkeypatch.setattr("prodrag.retrieval.sparse.FastEmbedSparse", FakeFastEmbedSparse)

    result = create_local_bm25_sparse_embeddings(
        model_name="Qdrant/bm25",
        language="english",
        model_assets_dir=tmp_path,
    )

    assert isinstance(result, FakeFastEmbedSparse)
    assert captured == {
        "model_name": "Qdrant/bm25",
        "language": "english",
        "specific_model_path": str(tmp_path),
        "local_files_only": True,
    }
