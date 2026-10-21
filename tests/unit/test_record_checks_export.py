"""Constructed checks/export counterexamples; no scientific gold or model calls."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from app.records.checks import check_bundle, scalar_notation
from app.records.schema import CandidateBundle, SourceRegion, source_identity, text_hash
from app.records.table_export import export_table

ROOT = Path(__file__).resolve().parents[2]


def make_bundle(tmp_path: Path, *, sample: str = "Sample L", value: str = "1.1 × 10 −4", ocr: bool = False) -> CandidateBundle:
    original = tmp_path / "original.pdf"
    original.write_bytes(b"Synthetic PDF-file identity fixture; no text extraction is tested.")
    layer = tmp_path / "ocr.pdf" if ocr else original
    if ocr:
        layer.write_bytes(b"Synthetic derived-file identity fixture.")
    quote = (f"{sample}; membrane; conductivity {value} S cm−1 at 20 °C in EC/SL; "
             "fraction 0.40 mass fraction; EIS; This work.")
    page = "Hidden prefix.\n" + quote + "\nHidden suffix."
    data = dict(article_id=uuid4(), original_pdf_path=str(original),
                original_pdf_sha256=hashlib.sha256(original.read_bytes()).hexdigest(), page_number=2,
                text_layer_id=uuid4(), text_layer="ocr" if ocr else "original", layer_pdf_path=str(layer),
                layer_pdf_sha256=hashlib.sha256(layer.read_bytes()).hexdigest(), page_text=page,
                page_text_sha256=text_hash(page), start=page.index(quote), end=page.index(quote) + len(quote),
                quote=quote, quote_sha256=text_hash(quote), selection_basis="manual_development", selection_note="Synthetic.")
    data["region_id"] = source_identity(data)
    region = SourceRegion.model_validate(data)

    def present(raw: str) -> dict[str, object]:
        start = quote.index(raw)
        return dict(status="present", raw_text=raw, evidence=[dict(
            region_id=region.region_id, start=start, end=start + len(raw), quote=raw)])

    missing = dict(status="unsupported", note="Not asserted in this synthetic fixture.")
    record = dict(
        record_id=uuid4(), article_id=region.article_id, sample_label=present(sample), material_form=present("membrane"),
        preparation=missing, property_name=present("conductivity"),
        value=dict(raw_value=present(value), raw_unit=present("S cm−1"), representation="scalar",
                   approximation=missing, uncertainty=missing),
        temperature=present("20 °C"), medium=present("EC/SL"), medium_composition=present("0.40"),
        composition_basis=present("mass fraction"), conditioning=missing, method=present("EIS"),
        data_origin=present("This work"), li_ion_author_claim=missing,
        linkage=[dict(role=role, evidence=[dict(region_id=region.region_id, start=0, end=len(quote), quote=quote)],
                      note="Synthetic role label only.")
                 for role in ("sample_value", "property_value", "conditions_measurement")],
    )
    return CandidateBundle.model_validate(dict(run_id=uuid4(), created_at=datetime.now(UTC), producer="synthetic",
                                               regions=[region], records=[record]))


def save_bundle(path: Path, bundle: CandidateBundle) -> Path:
    path.write_text(bundle.model_dump_json(indent=2), encoding="utf-8")
    return path


@pytest.mark.parametrize("raw", [
    "1", "43", "0.0043", ".40", "−1.1", "-1.1", "+1.1", "1e-4", "1 E −4",
    "1.1 × 10 −4", "1.1×10^4", "1.1 × 10^-4", "1.1×10⁻⁴", "1×10³",
])
def test_supported_scalar_syntax_preserves_source_components(raw: str) -> None:
    parts = scalar_notation(raw)
    assert parts is not None
    assert parts["coefficient"] in raw
    assert all(value in raw for value in parts.values())


@pytest.mark.parametrize("raw", [
    "1 × 103", "1,234", "1,1", "1–2", "1 to 2", "≤1", "~1", "1 ± 0.1", "NaN", "inf",
    " 1", "1 ", "1 S/cm", "１", "1\x001", "1x10-4", "1.1 × 10", "1.1 × 10 ^",
])
def test_unsupported_notation_is_not_repaired(raw: str) -> None:
    assert scalar_notation(raw) is None


def test_complete_exact_but_semantically_wrong_fields_never_become_accepted(tmp_path: Path) -> None:
    bundle = make_bundle(tmp_path)
    data = bundle.model_dump(mode="json")
    data["records"][0]["sample_label"] = data["records"][0]["method"]
    wrong = CandidateBundle.model_validate(data)
    before = wrong.model_dump_json()
    report = check_bundle(wrong)[0]
    assert report.technical_outcome == "unresolved"
    assert report.review_state == "needs_review" and report.scientific_admission == "not_evaluated"
    checks = {check.rule_id: check for check in report.checks}
    assert checks["required.sample_label"].status == "pass"
    assert checks["record.scientific_identity"].status == "unknown"
    assert checks["linkage.sample_value.scientific_support"].status == "unknown"
    assert wrong.model_dump_json() == before


@pytest.mark.parametrize("mutation,rule", [
    ("missing_method", "required.method"),
    ("missing_link", "linkage.conditions_measurement.unique_proposal"),
    ("duplicate_link", "linkage.sample_value.unique_proposal"),
])
def test_missing_conditions_and_ambiguous_proposals_block_technical_completeness(tmp_path: Path, mutation: str, rule: str) -> None:
    data = make_bundle(tmp_path).model_dump(mode="json")
    record = data["records"][0]
    if mutation == "missing_method":
        record["method"] = dict(status="not_found_in_context", note="Explicit synthetic missing condition.")
    elif mutation == "missing_link":
        record["linkage"].pop()
    else:
        record["linkage"].append(record["linkage"][0])
    report = check_bundle(CandidateBundle.model_validate(data))[0]
    assert report.technical_outcome == "incomplete"
    assert next(check for check in report.checks if check.rule_id == rule).status == "fail"


def test_evidence_tampered_through_pydantic_copy_is_revalidated(tmp_path: Path) -> None:
    bundle = make_bundle(tmp_path)
    broken = bundle.records[0].sample_label.evidence[0].model_copy(update={"quote": "invented"})
    observation = bundle.records[0].sample_label.model_copy(update={"evidence": (broken,)})
    record = bundle.records[0].model_copy(update={"sample_label": observation})
    with pytest.raises(ValueError):
        check_bundle(bundle.model_copy(update={"records": (record,)}))


@pytest.mark.parametrize("representation,value", [("range", "1–2"), ("bound", "≤1"), ("unparsed", "43")])
def test_ranges_bounds_and_unparsed_values_keep_unknown_without_conversion(tmp_path: Path, representation: str, value: str) -> None:
    data = make_bundle(tmp_path, value=value).model_dump(mode="json")
    data["records"][0]["value"]["representation"] = representation
    candidate = CandidateBundle.model_validate(data)
    report = check_bundle(candidate)[0]
    check = next(check for check in report.checks if check.rule_id == "quantity.scalar_notation")
    assert check.status == "unknown" and not check.details
    assert candidate.records[0].value.raw_value.raw_text == value


def test_export_roundtrip_frozen_scope_links_and_repeated_outputs(tmp_path: Path) -> None:
    bundle = make_bundle(tmp_path, ocr=True)
    negative = bundle.model_copy(update={"run_id": uuid4(), "records": ()})
    paths = [save_bundle(tmp_path / "candidate.json", bundle), save_bundle(tmp_path / "context.json", negative)]
    before = {path: path.read_bytes() for path in paths + [tmp_path / "original.pdf", tmp_path / "ocr.pdf"]}
    first = export_table(paths, tmp_path / "first", source_root=ROOT)
    second = export_table(paths, tmp_path / "second", source_root=ROOT)
    assert first == second
    assert first["summary"] == dict(input_bundles=2, empty_bundles=1, records=1, incomplete=0, unresolved=1,
                                    scientific_admission="not_evaluated")
    for path, original in before.items():
        assert path.read_bytes() == original
    for name in ("table.json", "table.csv", "review.html", "manifest.json", "inputs/0001.json", "inputs/0002.json"):
        assert (tmp_path / "first" / name).read_bytes() == (tmp_path / "second" / name).read_bytes()
    assert (tmp_path / "first/inputs/0001.json").read_bytes() == paths[0].read_bytes()
    restored = CandidateBundle.model_validate(first["cases"][0]["candidate_bundle"])
    assert restored == bundle
    manifest = json.loads((tmp_path / "first/manifest.json").read_text(encoding="utf-8"))
    for name, digest in manifest["outputs"].items():
        assert hashlib.sha256((tmp_path / "first" / name).read_bytes()).hexdigest() == digest
    page = (tmp_path / "first/review.html").read_text(encoding="utf-8")
    assert (tmp_path / "original.pdf").as_uri() + "#page=2" in page
    assert (tmp_path / "ocr.pdf").as_uri() + "#page=2" in page
    assert "Hidden prefix." in page and "Hidden suffix." in page
    assert "Нет предложенных записей" in page
    rows = list(csv.DictReader(io.StringIO((tmp_path / "first/table.csv").read_text(encoding="utf-8"))))
    assert len(rows) == 1
    assert rows[0]["value.raw_value"] == "1.1 × 10 −4"
    assert rows[0]["evidence_json_pointer"] == "table.json#/cases/0/records/0"


@pytest.mark.parametrize("sample", ["=1+1", "+SUM(A1)", "-1+2", "@SUM(A1)", "  =1+1", "\tSample", "\nSample"])
def test_csv_declares_formula_safety_prefix_but_json_keeps_exact_raw(tmp_path: Path, sample: str) -> None:
    bundle = make_bundle(tmp_path, sample=sample)
    path = save_bundle(tmp_path / "candidate.json", bundle)
    report = export_table([path], tmp_path / "out", source_root=ROOT)
    row = next(csv.DictReader(io.StringIO((tmp_path / "out/table.csv").read_text(encoding="utf-8"))))
    assert row["sample_label"] == "'" + sample
    assert "sample_label" in json.loads(row["csv_escaped_columns"])
    assert report["cases"][0]["records"][0]["candidate"]["sample_label"]["raw_text"] == sample


def test_html_untrusted_source_is_text_and_local_pdf_paths_are_url_encoded(tmp_path: Path) -> None:
    sample = '</script><img src=x onerror="alert(1)"> & <source>'
    folder = tmp_path / "space # and &"
    folder.mkdir()
    bundle = make_bundle(folder, sample=sample)
    path = save_bundle(tmp_path / "candidate.json", bundle)
    export_table([path], tmp_path / "out", source_root=ROOT)
    page = (tmp_path / "out/review.html").read_text(encoding="utf-8")
    assert sample not in page
    assert "&lt;/script&gt;&lt;img" in page
    assert "%23" in page and "%20" in page
    assert "innerHTML" not in page


@pytest.mark.parametrize("failure", ["changed_pdf", "missing_pdf", "changed_ocr", "broken_span", "duplicate", "copy", "empty_inputs"])
def test_invalid_input_and_file_failures_leave_no_successful_output(tmp_path: Path, failure: str) -> None:
    bundle = make_bundle(tmp_path, ocr=True)
    path = save_bundle(tmp_path / "candidate.json", bundle)
    paths = [path]
    if failure == "changed_pdf":
        (tmp_path / "original.pdf").write_bytes(b"tampered original")
    elif failure == "missing_pdf":
        (tmp_path / "original.pdf").unlink()
    elif failure == "changed_ocr":
        (tmp_path / "ocr.pdf").write_bytes(b"tampered derived file")
    elif failure == "broken_span":
        data = bundle.model_dump(mode="json")
        data["records"][0]["sample_label"]["evidence"][0]["start"] += 1
        path.write_text(json.dumps(data), encoding="utf-8")
    elif failure == "duplicate":
        paths.append(path)
    elif failure == "copy":
        copy = tmp_path / "copy.json"
        copy.write_bytes(path.read_bytes())
        paths.append(copy)
    else:
        paths = []
    with pytest.raises((ValueError, FileNotFoundError)):
        export_table(paths, tmp_path / "out", source_root=ROOT)
    assert not (tmp_path / "out").exists()


def test_overwrite_refusal_preserves_existing_output(tmp_path: Path) -> None:
    path = save_bundle(tmp_path / "candidate.json", make_bundle(tmp_path))
    output = tmp_path / "out"
    output.mkdir()
    marker = output / "marker.txt"
    marker.write_text("preserve", encoding="utf-8")
    with pytest.raises(FileExistsError):
        export_table([path], output, source_root=ROOT)
    assert marker.read_text(encoding="utf-8") == "preserve"


def test_empty_scope_bundle_stays_visible_without_fake_negative_accuracy(tmp_path: Path) -> None:
    bundle = make_bundle(tmp_path).model_copy(update={"records": ()})
    path = save_bundle(tmp_path / "context.json", bundle)
    report = export_table([path], tmp_path / "out", source_root=ROOT)
    assert report["summary"]["records"] == 0 and report["summary"]["empty_bundles"] == 1
    rows = list(csv.DictReader(io.StringIO((tmp_path / "out/table.csv").read_text(encoding="utf-8"))))
    assert rows == []
    assert report["cases"][0]["candidate_bundle"]["regions"]
