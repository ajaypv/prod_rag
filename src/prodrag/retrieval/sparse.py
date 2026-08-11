from __future__ import annotations

from pathlib import Path

from langchain_qdrant import FastEmbedSparse


def create_local_bm25_sparse_embeddings(
    *, model_name: str, language: str, model_assets_dir: Path | None = None
) -> FastEmbedSparse:
    """Create genuine BM25 sparse embeddings entirely on the local host."""
    model_assets_dir = model_assets_dir or (
        Path(__file__).resolve().parents[1] / "assets" / "bm25"
    )
    stopwords_path = model_assets_dir / f"{language}.txt"
    if not stopwords_path.is_file():
        raise RuntimeError(f"Missing local BM25 language asset: {stopwords_path}")
    return FastEmbedSparse(
        model_name=model_name,
        language=language,
        specific_model_path=str(model_assets_dir),
        local_files_only=True,
    )
