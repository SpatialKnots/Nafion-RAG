import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from app.evaluation import cli as cli_module
from app.evaluation.evidence_relations import (
    RelationDataset,
    evaluate_relation_cases,
    fragment_text_error,
    load_relation_dataset,
    summarize_relation_predictions,
    verify_relation_sources,
)


@pytest.fixture
def dataset():
    return load_relation_dataset(Path("docs/evidence_relation_cases.yaml"))


def test_duplicate_yaml_keys_rejected(tmp_path):
    path = tmp_path / "cases.yaml"
    path.write_text("version: 1\nversion: 1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate YAML key"):
        load_relation_dataset(path)


@pytest.mark.parametrize("change", ["unknown_fragment", "duplicate_id", "unknown_source", "unreviewed_page", "invalid_label"])
def test_invalid_annotations_rejected(dataset, change):
    raw = dataset.model_dump()
    fragment = next(iter(raw["fragments"].values()))
    if change == "unknown_fragment":
        raw["cases"][0]["fragments"] = ["absent"]
    elif change == "duplicate_id":
        raw["cases"][1]["id"] = raw["cases"][0]["id"]
    elif change == "unknown_source":
        fragment["source"] = "absent"
    elif change == "unreviewed_page":
        fragment["page"] = 999
    else:
        raw["cases"][0]["expected_support"] = "maybe"
    with pytest.raises(ValidationError):
        RelationDataset.model_validate(raw)


def test_fragment_drift_and_annotation_corruption_are_distinct(dataset):
    fragment = next(iter(dataset.fragments.values()))
    page = " " * fragment.start + fragment.text
    assert fragment_text_error(fragment, page) is None
    assert fragment_text_error(fragment, "x" + page) == "source_fragment_changed"
    changed = fragment.model_copy(update={"text": fragment.text + "x"})
    assert fragment_text_error(changed, page) == "annotation_text_hash_mismatch"


def test_missing_sources_never_count_as_success(dataset):
    rows = evaluate_relation_cases(dataset, {})
    summary = summarize_relation_predictions(rows)
    assert summary["evaluated"] == 0
    assert summary["invalid"] == len(rows)
    assert summary["accuracy"] is None
    assert summary["passed"] == 0


def test_confusion_metrics_exclude_invalid_sources():
    rows = [{"status": "evaluated", "expected_adequate": expected, "predicted_adequate": predicted}
            for expected, predicted in [(True, True), (False, False), (False, True), (True, False)]]
    rows.append({"status": "invalid_source"})
    summary = summarize_relation_predictions(rows)
    assert summary["accuracy"] == 0.5
    assert summary["adequacy_precision"] == 0.5
    assert summary["adequacy_recall"] == 0.5
    assert summary["invalid"] == 1


def test_expected_labels_do_not_influence_predictions(dataset):
    verified = {key: {"text": fragment.text} for key, fragment in dataset.fragments.items()}
    before = evaluate_relation_cases(dataset, verified)
    for case in dataset.cases:
        case.expected_support = "insufficient" if case.expected_support == "supports" else "supports"
    after = evaluate_relation_cases(dataset, verified)
    assert [row["diagnostics"] for row in before] == [row["diagnostics"] for row in after]
    assert all(a["expected_adequate"] != b["expected_adequate"] for a, b in zip(before, after, strict=True))


@pytest.mark.parametrize("missing", [True, False])
def test_original_pdf_integrity_failure_blocks_fragments(dataset, tmp_path, missing):
    path = tmp_path / "source.pdf"
    if not missing:
        path.write_bytes(b"changed PDF")
    articles = iter(SimpleNamespace(doi=source.doi, pdf_original_path=str(path)) for source in dataset.sources.values())
    session = SimpleNamespace(scalar=lambda query: next(articles))
    verified, errors = verify_relation_sources(session, dataset)
    assert not verified
    assert len(errors) == len(dataset.sources)
    assert {error["reason"] for error in errors} == {"original_pdf_missing" if missing else "original_pdf_hash_mismatch"}


def test_checked_in_fragment_hashes(dataset):
    assert all(hashlib.sha256(fragment.text.encode()).hexdigest() == fragment.text_sha256
               for fragment in dataset.fragments.values())


@pytest.mark.parametrize("check,invalid,expected_exit", [(False, False, 0), (True, False, 1), (False, True, 1)])
def test_cli_preserves_report_before_failure(monkeypatch, tmp_path, check, invalid, expected_exit):
    from contextlib import nullcontext

    report = {"summary": {"failed": 1, "invalid": int(invalid)}, "integrity_errors": []}
    monkeypatch.setattr(cli_module, "SessionLocal", lambda: nullcontext(None))
    monkeypatch.setattr(cli_module, "run_relation_evaluation", lambda *args: report)
    output = tmp_path / "report.json"
    args = ["evidence-relations", "--output", str(output)] + (["--check"] if check else [])
    result = CliRunner().invoke(cli_module.cli, args)
    assert result.exit_code == expected_exit, result.output
    assert output.is_file()
