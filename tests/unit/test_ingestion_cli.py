from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from app.ingestion import cli as ingestion_cli


def test_folder_reports_summary(monkeypatch, tmp_path) -> None:
    runner = CliRunner()
    (tmp_path / "b.pdf").write_bytes(b"%PDF b")
    (tmp_path / "a.pdf").write_bytes(b"%PDF a")

    def fake_ingest_one(path: Path, collection: str) -> dict[str, object]:
        status = "duplicate" if path.name == "b.pdf" else "indexed"
        return {"path": str(path), "status": status, "collection": collection}

    monkeypatch.setattr(ingestion_cli, "_ingest_one", fake_ingest_one)

    result = runner.invoke(ingestion_cli.cli, ["folder", str(tmp_path), "--collection", "literature"])

    assert result.exit_code == 0
    assert "'indexed': 1" in result.output
    assert "'duplicate': 1" in result.output
    assert "'failed': 0" in result.output


def test_folder_reports_failures_and_exits_nonzero(monkeypatch, tmp_path) -> None:
    runner = CliRunner()
    (tmp_path / "good.pdf").write_bytes(b"%PDF good")
    (tmp_path / "bad.pdf").write_bytes(b"%PDF bad")

    def fake_ingest_one(path: Path, collection: str) -> dict[str, object]:
        if path.name == "bad.pdf":
            raise ValueError("broken pdf")
        return {"path": str(path), "status": "indexed", "collection": collection}

    monkeypatch.setattr(ingestion_cli, "_ingest_one", fake_ingest_one)

    result = runner.invoke(ingestion_cli.cli, ["folder", str(tmp_path)])

    assert result.exit_code == 1
    assert "'status': 'failed'" in result.output
    assert "'error_type': 'ValueError'" in result.output
    assert "'failed': 1" in result.output
