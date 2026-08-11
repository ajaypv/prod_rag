from prodrag.config import Settings
from prodrag.worker import _cleanup_upload


def test_cleanup_upload_removes_file_and_empty_document_directory(tmp_path, monkeypatch) -> None:
    settings = Settings(_env_file=None, data_dir=tmp_path)
    monkeypatch.setattr("prodrag.worker.settings", settings)
    upload = tmp_path / "uploads" / "guide" / "job-guide.md"
    upload.parent.mkdir(parents=True)
    upload.write_text("test", encoding="utf-8")

    _cleanup_upload(str(upload))

    assert not upload.exists()
    assert not upload.parent.exists()


def test_cleanup_upload_refuses_path_outside_upload_root(tmp_path, monkeypatch) -> None:
    settings = Settings(_env_file=None, data_dir=tmp_path / "data")
    monkeypatch.setattr("prodrag.worker.settings", settings)
    outside = tmp_path / "keep.md"
    outside.write_text("keep", encoding="utf-8")

    _cleanup_upload(str(outside))

    assert outside.exists()
