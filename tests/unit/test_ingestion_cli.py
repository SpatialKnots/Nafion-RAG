from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from typer.testing import CliRunner

from app.ingestion import cli as ingestion_cli


def _json_lines(output: str) -> list[dict[str, object]]:
    return [json.loads(line) for line in output.splitlines() if line.strip()]


class FakeSession:
    committed = False

    def __enter__(self) -> FakeSession:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        return None

    def commit(self) -> None:
        self.committed = True


def test_folder_reports_summary(monkeypatch, tmp_path) -> None:
    runner = CliRunner()
    (tmp_path / "b.pdf").write_bytes(b"%PDF b")
    (tmp_path / "a.pdf").write_bytes(b"%PDF a")

    def fake_ingest_one(path: Path, collection: str, *, force_ocr: bool = False) -> dict[str, object]:
        status = "duplicate" if path.name == "b.pdf" else "indexed"
        return {"path": str(path), "status": status, "collection": collection, "force_ocr": force_ocr}

    monkeypatch.setattr(ingestion_cli, "_ingest_one", fake_ingest_one)

    result = runner.invoke(ingestion_cli.cli, ["folder", str(tmp_path), "--collection", "literature"])

    assert result.exit_code == 0
    summary = _json_lines(result.output)[-1]["summary"]
    assert summary == {"total": 2, "indexed": 1, "duplicate": 1, "failed": 0}


def test_folder_reports_failures_and_exits_nonzero(monkeypatch, tmp_path) -> None:
    runner = CliRunner()
    (tmp_path / "good.pdf").write_bytes(b"%PDF good")
    (tmp_path / "bad.pdf").write_bytes(b"%PDF bad")

    def fake_ingest_one(path: Path, collection: str, *, force_ocr: bool = False) -> dict[str, object]:
        if path.name == "bad.pdf":
            raise ValueError("broken pdf")
        return {"path": str(path), "status": "indexed", "collection": collection, "force_ocr": force_ocr}

    monkeypatch.setattr(ingestion_cli, "_ingest_one", fake_ingest_one)

    result = runner.invoke(ingestion_cli.cli, ["folder", str(tmp_path)])

    assert result.exit_code == 1
    payloads = _json_lines(result.output)
    assert any(payload.get("status") == "failed" and payload.get("error_type") == "ValueError" for payload in payloads)
    assert payloads[-1]["summary"] == {"total": 2, "indexed": 1, "duplicate": 0, "failed": 1}


def test_folder_passes_force_ocr(monkeypatch, tmp_path) -> None:
    runner = CliRunner()
    (tmp_path / "paper.pdf").write_bytes(b"%PDF paper")

    def fake_ingest_one(path: Path, collection: str, *, force_ocr: bool = False) -> dict[str, object]:
        return {"path": str(path), "status": "indexed", "collection": collection, "force_ocr": force_ocr}

    monkeypatch.setattr(ingestion_cli, "_ingest_one", fake_ingest_one)

    result = runner.invoke(ingestion_cli.cli, ["folder", str(tmp_path), "--force-ocr"])

    assert result.exit_code == 0
    assert _json_lines(result.output)[0]["force_ocr"] is True


def test_prune_missing_corpus_defaults_to_dry_run(monkeypatch, tmp_path) -> None:
    runner = CliRunner()
    article = SimpleNamespace(
        id=uuid4(),
        title="smoke_text",
        pdf_original_path=str(tmp_path / "missing.pdf"),
        pdf_ocr_path=None,
    )
    monkeypatch.setattr(ingestion_cli, "SessionLocal", lambda: FakeSession())
    monkeypatch.setattr(ingestion_cli, "_missing_corpus_articles", lambda session: [article])

    result = runner.invoke(ingestion_cli.cli, ["prune-missing-corpus"])

    payload = _json_lines(result.output)[0]
    assert result.exit_code == 0
    assert payload["status"] == "dry_run"
    assert payload["candidate_count"] == 1


def test_prune_missing_corpus_apply_backs_up_and_deletes(monkeypatch, tmp_path) -> None:
    runner = CliRunner()
    session = FakeSession()
    article = SimpleNamespace(
        id=uuid4(),
        title="smoke_text",
        pdf_original_path=str(tmp_path / "missing.pdf"),
        pdf_ocr_path=None,
    )
    deleted = {"called": False}
    monkeypatch.setattr(ingestion_cli, "SessionLocal", lambda: session)
    monkeypatch.setattr(ingestion_cli, "get_settings", lambda: SimpleNamespace(data_root=tmp_path))
    monkeypatch.setattr(ingestion_cli, "_missing_corpus_articles", lambda active_session: [article])
    monkeypatch.setattr(ingestion_cli, "_backup_missing_articles", lambda active_session, articles, backup_dir: backup_dir / "backup.json")

    def fake_delete(active_session: object, articles: object) -> dict[str, int]:
        deleted["called"] = True
        return {"articles": 1, "chunks": 1}

    monkeypatch.setattr(ingestion_cli, "_delete_articles", fake_delete)

    result = runner.invoke(ingestion_cli.cli, ["prune-missing-corpus", "--apply"])

    payload = _json_lines(result.output)[0]
    assert result.exit_code == 0
    assert payload["status"] == "pruned"
    assert payload["backup_path"].endswith("backup.json")
    assert payload["deleted"] == {"articles": 1, "chunks": 1}
    assert deleted["called"] is True
    assert session.committed is True
