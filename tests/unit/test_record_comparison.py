"""Synthetic source/protocol counterexamples; not scientific gold or model inference."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.records import smoke
from app.records.comparison import compare_batches, compare_observation, render_comparison
from app.records.reference import DevelopmentReference, ExpectedAnswer, FieldExpectation, LinkageReview, ReferenceCase
from app.records.schema import CandidateBundle, EvidenceSpan, SourceRegion, TextObservation, source_identity, text_hash


def source(raw: str = "Header at 25 °C. Sample L. Value 1 × 10−4. Footnote d at 20 °C. Page A5253.") -> CandidateBundle:
    data = {
        "article_id": str(uuid4()), "original_pdf_path": "/synthetic/source.pdf", "original_pdf_sha256": "a" * 64,
        "page_number": 1, "text_layer_id": str(uuid4()), "text_layer": "original",
        "layer_pdf_path": "/synthetic/source.pdf", "layer_pdf_sha256": "a" * 64,
        "page_text": raw, "page_text_sha256": text_hash(raw), "start": 0, "end": len(raw),
        "quote": raw, "quote_sha256": text_hash(raw), "selection_basis": "manual_development",
        "selection_note": "Synthetic test context; not gold.",
    }
    data["region_id"] = source_identity(data)
    return CandidateBundle(run_id=uuid4(), created_at=datetime.now(UTC), producer="synthetic", regions=(SourceRegion.model_validate(data),))


def span(bundle, text: str, start: int | None = None) -> EvidenceSpan:
    region = bundle.regions[0]
    offset = region.quote.index(text) if start is None else start
    return EvidenceSpan(region_id=region.region_id, start=offset, end=offset + len(text), quote=text)


def expectation(bundle, field="value", raw="1 × 10−4", criterion="exact_raw") -> FieldExpectation:
    answers = (ExpectedAnswer(raw_text=raw, anchors=(span(bundle, raw),)),) if criterion == "exact_raw" else ()
    return FieldExpectation(field=field, criterion=criterion, answers=answers,
                            support=(span(bundle, bundle.regions[0].quote),), rationale="Synthetic declared expectation.")


def reference(bundle) -> DevelopmentReference:
    raw_input = bundle.model_dump_json(indent=2).encode()
    fields = tuple(expectation(bundle, field=field, criterion="exact_raw" if field == "value" else "abstain")
                   for field in smoke.FIELD_INSTRUCTIONS)
    reviews = tuple(LinkageReview(dimension=dimension, status="needs_independent_review",
                                  support=(span(bundle, bundle.regions[0].quote),), rationale="Synthetic unresolved linkage.")
                    for dimension in ("sample_linkage", "condition_linkage", "origin_linkage"))
    case = ReferenceCase(case_id="test", input_sha256=hashlib.sha256(raw_input).hexdigest(), task_sha256=text_hash("Synthetic task"),
                         context=bundle, fields=fields, linkage=reviews)
    return DevelopmentReference(reference_id=uuid4(), created_at=datetime.now(UTC), author="Synthetic fixture",
                                cases=(case,), limitations=("Synthetic; not independent gold.",))


@pytest.mark.parametrize("raw,field", [("25 °C", "temperature"), ("A5253", "value")])
def test_literal_source_match_does_not_make_wrong_temperature_or_bibliographic_value_correct(raw, field) -> None:
    bundle = source()
    target = "20 °C" if field == "temperature" else "1 × 10−4"
    actual = TextObservation(status="present", raw_text=raw, evidence=(span(bundle, raw),))
    result = compare_observation(expectation(bundle, field, target), actual)
    assert result["field_agreement"] == "mismatch"
    assert result["reference_anchor"] == "mismatch"


def test_same_raw_unit_at_wrong_property_occurrence_fails_reference_anchor() -> None:
    bundle = source("Ionic unit S cm−1. Electronic unit S cm−1.")
    actual = TextObservation(status="present", raw_text="S cm−1", evidence=(span(bundle, "Electronic unit S cm−1"),))
    result = compare_observation(expectation(bundle, "unit", "S cm−1"), actual)
    assert result["field_agreement"] == "match"
    assert result["reference_anchor"] == "mismatch"


def test_bibliography_requires_abstention_even_for_literal_property_title() -> None:
    bundle = source("Title conductivity. Page A5253.")
    expected = expectation(bundle, "property_name", criterion="abstain")
    actual = TextObservation(status="present", raw_text="conductivity", evidence=(span(bundle, "conductivity"),))
    assert compare_observation(expected, actual)["abstention"] == "false_assertion"
    missing = TextObservation(status="not_found_in_context", note="No measurement in synthetic context.")
    assert compare_observation(expected, missing)["abstention"] == "correct"


def test_deferred_expectation_remains_ungraded() -> None:
    bundle = source()
    actual = TextObservation(status="not_found_in_context", note="Missing.")
    assert set(compare_observation(expectation(bundle, criterion="deferred"), actual).values()) == {"deferred"}


@pytest.mark.parametrize("change", ["missing_field", "duplicate_field", "bad_span", "wrong_raw", "approved_status"])
def test_reference_rejects_incomplete_or_unproven_expected_answers(change) -> None:
    data = reference(source()).model_dump(mode="json")
    case = data["cases"][0]
    if change == "missing_field":
        case["fields"].pop()
    elif change == "duplicate_field":
        case["fields"][0] = case["fields"][1]
    elif change == "bad_span":
        case["fields"][0]["support"][0]["quote"] = "invented"
    elif change == "wrong_raw":
        next(field for field in case["fields"] if field["field"] == "value")["answers"][0]["raw_text"] = "invented"
    else:
        data["status"] = "approved"
    with pytest.raises(ValidationError):
        DevelopmentReference.model_validate(data)


@pytest.fixture
def experiment(tmp_path: Path, monkeypatch):
    bundle = source()
    (tmp_path / "app" / "records").mkdir(parents=True)
    for name in ("schema.py", "comparison.py"):
        (tmp_path / "app" / "records" / name).write_text("# synthetic fixture\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("# synthetic fixture\n", encoding="utf-8")
    input_path = tmp_path / "input.json"
    input_path.write_bytes(bundle.model_dump_json(indent=2).encode())
    reference_path = tmp_path / "reference.json"
    reference_path.write_text(reference(bundle).model_dump_json(indent=2), encoding="utf-8")
    identity = tmp_path / "runtime.json"
    identity.write_text(json.dumps({"endpoint": "http://127.0.0.1:18086", "model_alias": "synthetic"}), encoding="utf-8")

    def make_run(field="value", text="1 × 10−4", finish="stop"):
        content = json.dumps({"region": "R1" if text is not None else None, "text": text}, ensure_ascii=False)
        monkeypatch.setattr(smoke, "send_local_request", lambda *args: json.dumps({
            "choices": [{"message": {"content": content}, "finish_reason": finish}],
        }).encode())
        directory = tmp_path / "batch" / field
        result = smoke.run_smoke(input_path, directory, task="Synthetic task", field=field, field_format="span",
                                 endpoint="http://127.0.0.1:18086", model="synthetic", runtime_manifest=identity, source_root=tmp_path)
        return {"case": "test", "field": field, "directory": str(directory), "result": result}

    return tmp_path, reference_path, make_run


def compare_fixture(experiment, runs):
    root, reference_path, _ = experiment
    path = root / "batch" / "batch_result.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps({"runs": runs}), encoding="utf-8")
    return compare_batches(reference_path, [path], root / "comparison", source_root=root)


def test_incomplete_batch_preserves_missing_fields_and_linkage_review(experiment) -> None:
    _, _, make_run = experiment
    report = compare_fixture(experiment, [make_run()])
    batch = report["batches"][0]
    assert batch["summary"]["expected_fields"] == 10
    assert batch["summary"]["reference_agreements"] == 1
    assert batch["summary"]["field_outcomes"]["unavailable"] == 9
    assert report["scientific_admission"] == "not_evaluated"
    assert all(item["status"] == "needs_independent_review" for row in batch["rows"] for item in row["linkage"])


@pytest.mark.parametrize("text,finish", [("invented", "stop"), ("1 × 10−4", "length")])
def test_failed_or_truncated_output_is_not_filtered_out(experiment, text, finish) -> None:
    _, _, make_run = experiment
    report = compare_fixture(experiment, [make_run(text=text, finish=finish)])
    summary = report["batches"][0]["summary"]
    assert summary["expected_fields"] == 10
    assert summary["reference_agreements"] == 0
    assert summary["literal_valid"] == 0


@pytest.mark.parametrize("fault", ["input", "request", "task", "directory", "duplicate"])
def test_comparison_rejects_changed_context_or_ambiguous_batch_identity(experiment, fault) -> None:
    root, _, make_run = experiment
    run = make_run()
    directory = Path(run["directory"])
    if fault == "input":
        (directory / "input.json").write_bytes(b"changed")
    elif fault == "request":
        (directory / "request.json").write_bytes(b"changed")
    elif fault == "task":
        path = directory / "manifest.json"
        manifest = json.loads(path.read_bytes())
        manifest["task"] = "Different task"
        path.write_text(json.dumps(manifest), encoding="utf-8")
    elif fault == "directory":
        run["directory"] = str(root.parent)
    with pytest.raises(ValueError):
        compare_fixture(experiment, [run, run] if fault == "duplicate" else [run])
    assert not (root / "comparison").exists()


def test_report_refuses_overwrite_and_escapes_untrusted_markup(experiment) -> None:
    root, reference_path, make_run = experiment
    report = compare_fixture(experiment, [make_run()])
    row = report["batches"][0]["rows"][0]
    row["case"] = "<script>|`"
    markdown = render_comparison(report)
    assert "<script>" not in markdown
    assert "&lt;script&gt;&#124;&#96;" in markdown
    with pytest.raises(FileExistsError):
        compare_batches(reference_path, [root / "batch" / "batch_result.json"], root / "comparison", source_root=root)
