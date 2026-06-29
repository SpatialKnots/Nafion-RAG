from __future__ import annotations

from app.ingestion.checksum import sha256_file


def test_sha256_file(tmp_path) -> None:
    path = tmp_path / "sample.txt"
    path.write_text("nafion", encoding="utf-8")

    assert sha256_file(path) == "ebe8526851d9c52657dc610c15bc9dcdb2f210f1d5b37641a8bfd713f7fe3546"
