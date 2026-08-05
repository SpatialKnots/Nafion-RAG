from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from typer.testing import CliRunner

from app.ingestion import cli as ingestion_cli


def _json_lines(output: str) -> list[dict[str, object]]:
    return [json.loads(line) for line in output.splitlines() if line.strip()]


class FakeSession:
    committed = False
    rolled_back = False

    def __enter__(self) -> FakeSession:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        return None

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True


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


def test_corpus_report_outputs_json_summary(monkeypatch, tmp_path) -> None:
    runner = CliRunner()
    session = FakeSession()
    monkeypatch.setattr(ingestion_cli, "SessionLocal", lambda: session)
    monkeypatch.setattr(ingestion_cli, "get_settings", lambda: SimpleNamespace(data_root=tmp_path))

    def fake_build_report(active_session: object, data_root: Path, collection: str) -> dict[str, object]:
        assert active_session is session
        assert data_root == tmp_path
        assert collection == "literature"
        return {"collection": collection, "summary": {"articles": 2, "articles_with_doi": 1}, "latest_retrieval_eval": None}

    monkeypatch.setattr(ingestion_cli, "_build_corpus_report", fake_build_report)

    result = runner.invoke(ingestion_cli.cli, ["corpus-report"])

    assert result.exit_code == 0
    payload = _json_lines(result.output)[0]
    assert payload["output_path"].endswith(".json")
    assert Path(str(payload["output_path"])).exists()
    assert payload["summary"] == {"articles": 2, "articles_with_doi": 1}


def test_latest_retrieval_eval_uses_file_mtime_not_name(tmp_path) -> None:
    export_dir = tmp_path / "exports"
    export_dir.mkdir()
    older = export_dir / "retrieval_eval_semantic_20260804T083642Z.json"
    newer = export_dir / "retrieval_eval_extended_hybrid_20260805T062109Z.json"
    older.write_text(json.dumps({"created_at": "old", "summary": {"total": 24}, "settings": {"method": "semantic"}}), encoding="utf-8")
    newer.write_text(json.dumps({"created_at": "new", "summary": {"total": 46}, "settings": {"method": "hybrid"}}), encoding="utf-8")
    os.utime(older, (100, 100))
    os.utime(newer, (200, 200))

    latest = ingestion_cli._latest_retrieval_eval(tmp_path)

    assert latest is not None
    assert latest["path"] == str(newer)
    assert latest["created_at"] == "new"
    assert latest["summary"] == {"total": 46}


def test_text_quality_report_outputs_json_summary(monkeypatch, tmp_path) -> None:
    runner = CliRunner()
    session = FakeSession()
    monkeypatch.setattr(ingestion_cli, "SessionLocal", lambda: session)
    monkeypatch.setattr(ingestion_cli, "get_settings", lambda: SimpleNamespace(data_root=tmp_path))

    def fake_build_report(active_session: object, settings: object, collection: str) -> dict[str, object]:
        assert active_session is session
        assert collection == "literature"
        return {
            "collection": collection,
            "article_count": 2,
            "page_count": 5,
            "empty_original_page_count": 1,
            "short_original_page_count": 2,
            "ocr_used_pages": 1,
            "suspicious_page_count": 3,
        }

    monkeypatch.setattr(ingestion_cli, "build_text_quality_report", fake_build_report)

    result = runner.invoke(ingestion_cli.cli, ["text-quality-report"])

    assert result.exit_code == 0
    payload = _json_lines(result.output)[0]
    assert payload["output_path"].endswith(".json")
    assert Path(str(payload["output_path"])).exists()
    assert payload["summary"]["suspicious_page_count"] == 3


def test_reprocess_article_text_quality_dry_run_writes_report(monkeypatch, tmp_path) -> None:
    runner = CliRunner()
    session = FakeSession()
    article_id = uuid4()
    article = SimpleNamespace(id=article_id, title="Dry run paper")
    monkeypatch.setattr(ingestion_cli, "SessionLocal", lambda: session)
    monkeypatch.setattr(ingestion_cli, "get_settings", lambda: SimpleNamespace(data_root=tmp_path))
    session.scalar = lambda statement: article  # type: ignore[method-assign]

    def fake_dry_run(active_session: object, settings: object, active_article: object) -> dict[str, object]:
        assert active_session is session
        assert active_article is article
        return {
            "dry_run": True,
            "mutation_performed": False,
            "current_counts": {"pages": 2, "chunks": 1, "page_text_layers": 2},
            "candidate_actions": {"evaluate_caption_evidence": 1},
        }

    monkeypatch.setattr(ingestion_cli, "build_reprocess_text_quality_dry_run", fake_dry_run)

    result = runner.invoke(ingestion_cli.cli, ["reprocess-article", str(article_id)])

    assert result.exit_code == 0
    payload = _json_lines(result.output)[0]
    assert payload["status"] == "dry_run"
    assert payload["output_path"].endswith(".json")
    assert Path(str(payload["output_path"])).exists()
    assert payload["candidate_actions"] == {"evaluate_caption_evidence": 1}
    assert session.committed is False


def test_reprocess_article_apply_backs_up_reselects_and_commits(monkeypatch, tmp_path) -> None:
    runner = CliRunner()
    session = FakeSession()
    article_id = uuid4()
    article = SimpleNamespace(id=article_id, title="Apply paper")
    monkeypatch.setattr(ingestion_cli, "SessionLocal", lambda: session)
    monkeypatch.setattr(ingestion_cli, "get_settings", lambda: SimpleNamespace(data_root=tmp_path))
    session.scalar = lambda statement: article  # type: ignore[method-assign]
    monkeypatch.setattr(
        ingestion_cli,
        "build_reprocess_text_quality_dry_run",
        lambda active_session, settings, active_article: {
            "current_counts": {"pages": 2, "chunks": 1, "page_text_layers": 2},
            "candidate_actions": {"evaluate_caption_evidence": 1},
        },
    )
    monkeypatch.setattr(
        ingestion_cli,
        "_backup_article_content",
        lambda active_session, active_article, backup_dir, reason: backup_dir / "backup.json",
    )
    monkeypatch.setattr(ingestion_cli, "reselect_article_text", lambda active_session, settings, active_article: 4)

    result = runner.invoke(ingestion_cli.cli, ["reprocess-article", str(article_id), "--apply"])

    assert result.exit_code == 0
    payload = _json_lines(result.output)[0]
    assert payload["status"] == "reprocessed"
    assert payload["backup_path"].endswith("backup.json")
    assert payload["chunk_count"] == 4
    assert payload["vector_index"] == "marked_stale"
    assert session.committed is True


def test_latest_retrieval_eval_loads_newest_summary(tmp_path) -> None:
    export_dir = tmp_path / "exports"
    export_dir.mkdir()
    older = export_dir / "retrieval_eval_20260803T000000Z.json"
    newer = export_dir / "retrieval_eval_20260803T010000Z.json"
    older.write_text(json.dumps({"summary": {"total": 1}, "settings": {"top_k": 5}}), encoding="utf-8")
    newer.write_text(
        json.dumps({"created_at": "2026-08-03T01:00:00Z", "summary": {"total": 15}, "settings": {"top_k": 10}}),
        encoding="utf-8",
    )
    os.utime(older, (100, 100))
    os.utime(newer, (200, 200))

    report = ingestion_cli._latest_retrieval_eval(tmp_path)

    assert report == {
        "path": str(newer),
        "status": "loaded",
        "created_at": "2026-08-03T01:00:00Z",
        "summary": {"total": 15},
        "settings": {"top_k": 10},
    }


def test_corpus_manifest_writes_tracked_snapshot(monkeypatch, tmp_path) -> None:
    runner = CliRunner()
    session = FakeSession()
    manifest = {
        "schema_version": 1,
        "created_at": "2026-08-03T00:00:00+00:00",
        "collection": "literature",
        "summary": {"articles": 1, "pages": 2, "chunks": 3, "text_layers": 4},
        "articles": [
            {
                "checksum_sha256": "abc",
                "title": "Paper",
                "doi": None,
                "pdf_original_basename": "paper.pdf",
                "pdf_ocr_basename": None,
                "status": "indexed",
                "page_count": 2,
                "chunk_count": 3,
                "text_layer_count": 4,
            }
        ],
    }
    output_path = tmp_path / "corpus_manifest.json"
    monkeypatch.setattr(ingestion_cli, "SessionLocal", lambda: session)
    monkeypatch.setattr(ingestion_cli, "_build_corpus_manifest", lambda active_session, collection: manifest)

    result = runner.invoke(ingestion_cli.cli, ["corpus-manifest", "--output", str(output_path)])

    assert result.exit_code == 0
    payload = _json_lines(result.output)[0]
    assert payload["status"] == "written"
    assert payload["output_path"] == str(output_path)
    assert json.loads(output_path.read_text(encoding="utf-8")) == manifest


def test_corpus_manifest_check_passes_on_match(monkeypatch, tmp_path) -> None:
    runner = CliRunner()
    session = FakeSession()
    manifest = {
        "schema_version": 1,
        "created_at": "new timestamp",
        "collection": "literature",
        "summary": {"articles": 1},
        "articles": [{"checksum_sha256": "abc", "title": "Paper", "chunk_count": 3}],
    }
    expected_path = tmp_path / "corpus_manifest.json"
    expected = dict(manifest)
    expected["created_at"] = "old timestamp"
    expected_path.write_text(json.dumps(expected), encoding="utf-8")
    monkeypatch.setattr(ingestion_cli, "SessionLocal", lambda: session)
    monkeypatch.setattr(ingestion_cli, "_build_corpus_manifest", lambda active_session, collection: manifest)

    result = runner.invoke(ingestion_cli.cli, ["corpus-manifest", "--check", str(expected_path)])

    assert result.exit_code == 0
    payload = _json_lines(result.output)[0]
    assert payload["status"] == "match"
    assert payload["missing_articles"] == []
    assert payload["extra_articles"] == []
    assert payload["changed_articles"] == []


def test_corpus_manifest_check_reports_differences(monkeypatch, tmp_path) -> None:
    runner = CliRunner()
    session = FakeSession()
    current = {
        "schema_version": 1,
        "created_at": "new timestamp",
        "collection": "literature",
        "summary": {"articles": 1, "chunks": 4},
        "articles": [{"checksum_sha256": "abc", "title": "Paper", "chunk_count": 4}],
    }
    expected_path = tmp_path / "corpus_manifest.json"
    expected_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "created_at": "old timestamp",
                "collection": "literature",
                "summary": {"articles": 1, "chunks": 3},
                "articles": [{"checksum_sha256": "abc", "title": "Paper", "chunk_count": 3}],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(ingestion_cli, "SessionLocal", lambda: session)
    monkeypatch.setattr(ingestion_cli, "_build_corpus_manifest", lambda active_session, collection: current)

    result = runner.invoke(ingestion_cli.cli, ["corpus-manifest", "--check", str(expected_path)])

    assert result.exit_code == 1
    payload = _json_lines(result.output)[0]
    assert payload["status"] == "mismatch"
    assert payload["summary_changed"] is True
    assert payload["changed_articles"][0]["checksum_sha256"] == "abc"


def test_corpus_manifest_check_reports_missing_manifest(monkeypatch, tmp_path) -> None:
    runner = CliRunner()
    monkeypatch.setattr(ingestion_cli, "SessionLocal", lambda: FakeSession())
    monkeypatch.setattr(ingestion_cli, "_build_corpus_manifest", lambda active_session, collection: {"summary": {}, "articles": []})

    result = runner.invoke(ingestion_cli.cli, ["corpus-manifest", "--check", str(tmp_path / "missing.json")])

    assert result.exit_code == 1
    assert _json_lines(result.output)[0]["status"] == "missing_manifest"


def test_corpus_manifest_check_reports_invalid_json(monkeypatch, tmp_path) -> None:
    runner = CliRunner()
    invalid_path = tmp_path / "corpus_manifest.json"
    invalid_path.write_text("{", encoding="utf-8")
    monkeypatch.setattr(ingestion_cli, "SessionLocal", lambda: FakeSession())
    monkeypatch.setattr(ingestion_cli, "_build_corpus_manifest", lambda active_session, collection: {"summary": {}, "articles": []})

    result = runner.invoke(ingestion_cli.cli, ["corpus-manifest", "--check", str(invalid_path)])

    assert result.exit_code == 1
    payload = _json_lines(result.output)[0]
    assert payload["status"] == "invalid_manifest"
    assert payload["error_type"] == "JSONDecodeError"
