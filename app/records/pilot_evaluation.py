"""One-to-one finite-reference record agreement; never automatic scientific gold."""

from __future__ import annotations

import hashlib
import html
import json
from collections import Counter, deque
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal, Self

from pydantic import Field, model_validator

from app.records.full_evaluation import DIMENSIONS, FullRecordCase, compare_record, observations
from app.records.schema import CandidateBundle, ContractModel, NonEmpty, RecordCandidate, Sha256
from app.records.sources import file_hash

VERSION = "records_pilot_evaluation_v0.1"


class ExpectedRecord(ContractModel):
    record: RecordCandidate
    deferred: dict[str, NonEmpty] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_deferred(self) -> Self:
        if not set(self.deferred) <= set(DIMENSIONS):
            raise ValueError("Unknown deferred record dimension")
        for name, observation in observations(self.record).items():
            if observation.status in {"unsupported", "ambiguous"} and name not in self.deferred:
                raise ValueError(f"Unresolved reference dimension must be deferred: {name}")
        roles = [link.role for link in self.record.linkage]
        if len(roles) != len(set(roles)):
            raise ValueError("Reference cannot contain duplicate linkage roles")
        return self


class PilotReferenceCase(ContractModel):
    case_id: NonEmpty
    context_path: NonEmpty
    context_sha256: Sha256
    context: CandidateBundle
    scope_note: NonEmpty
    exhaustive_scope: bool
    annotation_state: Literal["annotated", "unannotated"]
    expected: tuple[ExpectedRecord, ...] = ()

    @model_validator(mode="after")
    def validate_scope(self) -> Self:
        if self.context.records:
            raise ValueError("Pilot reference context must be source-only")
        if self.annotation_state == "unannotated" and self.expected:
            raise ValueError("Unannotated input cannot assert reference records")
        data = self.context.model_dump()
        CandidateBundle.model_validate({**data, "records": tuple(item.record for item in self.expected)})
        signatures = [json.dumps(item.record.model_dump(mode="json", exclude={"record_id"}), sort_keys=True)
                      for item in self.expected]
        if len(set(signatures)) != len(signatures):
            raise ValueError("Duplicate exact reference records with different IDs")
        return self


class PilotReference(ContractModel):
    schema_version: Literal["records_pilot_reference_v0.1"] = "records_pilot_reference_v0.1"
    author: NonEmpty
    author_kind: Literal["human", "assistant"]
    reference_kind: Literal["development_reference", "independent_annotation_declared"]
    annotated_before_predictions: bool
    provenance_note: NonEmpty
    cases: tuple[PilotReferenceCase, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_provenance(self) -> Self:
        if not self.author.strip() or not self.provenance_note.strip():
            raise ValueError("Reference author and provenance note must not be whitespace")
        if len({case.case_id for case in self.cases}) != len(self.cases):
            raise ValueError("Duplicate reference case ID")
        if self.reference_kind == "independent_annotation_declared" and (
                self.author_kind != "human" or not self.annotated_before_predictions):
            raise ValueError("Independent annotation requires a declared human and annotation before outputs")
        return self


def maximum_matching(edges: list[list[int]], initial: Mapping[int, int] | None = None) -> dict[int, int]:
    """Deterministic maximum bipartite matching using augmenting paths, no recursion."""
    prediction_to_reference = dict(initial or {})
    if (len(set(prediction_to_reference.values())) != len(prediction_to_reference)
            or any(not 0 <= i < len(edges) or j not in edges[i] for i, j in prediction_to_reference.items())):
        raise ValueError("Initial assignment is not a valid one-to-one matching")
    reference_to_prediction = {j: i for i, j in prediction_to_reference.items()}
    for root in range(len(edges)):
        if root in prediction_to_reference:
            continue
        queue = deque([root])
        seen_predictions = {root}
        parents: dict[int, int] = {}
        free = None
        while queue and free is None:
            prediction = queue.popleft()
            for reference in edges[prediction]:
                if reference in parents:
                    continue
                parents[reference] = prediction
                if reference not in reference_to_prediction:
                    free = reference
                    break
                occupied = reference_to_prediction[reference]
                if occupied not in seen_predictions:
                    seen_predictions.add(occupied)
                    queue.append(occupied)
        while free is not None:
            prediction = parents[free]
            previous = prediction_to_reference.get(prediction)
            prediction_to_reference[prediction] = free
            reference_to_prediction[free] = prediction
            free = previous
    return prediction_to_reference


def _pair(case: PilotReferenceCase, expected: ExpectedRecord, prediction: RecordCandidate) -> dict[str, Any]:
    # Reuse the existing twenty-dimension policy without altering its reference or tolerances.
    single = FullRecordCase(case_id=case.case_id, input_sha256=case.context_sha256, task=case.scope_note,
                            context=case.context, expected=(expected.record,), deferred=expected.deferred,
                            rationale="Finite-reference matching adapter; not an inference request or scientific admission.")
    if prediction.article_id != expected.record.article_id:
        return {"full_record_agreement": "mismatch", "diagnostic": "Different article identities"}
    result = compare_record(single, prediction)
    repeated = [role for role, count in Counter(link.role for link in prediction.linkage).items() if count > 1]
    result["duplicate_linkage_roles"] = sorted(repeated)
    if repeated:
        result["full_record_agreement"] = "mismatch"
        result["diagnostic"] = "Duplicate role proposals block matching; none was silently discarded"
    return result


def compare_case(case: PilotReferenceCase, prediction: CandidateBundle) -> dict[str, Any]:
    case = PilotReferenceCase.model_validate_json(case.model_dump_json())
    prediction = CandidateBundle.model_validate_json(prediction.model_dump_json())
    if prediction.regions != case.context.regions:
        raise ValueError(f"Prediction source regions differ from frozen reference: {case.case_id}")
    base: dict[str, Any] = {"case_id": case.case_id, "expected_records": len(case.expected),
                            "proposed_records": len(prediction.records), "scope_note": case.scope_note,
                            "exhaustive_scope": case.exhaustive_scope, "annotation_state": case.annotation_state,
                            "candidate_bundle": prediction.model_dump(mode="json")}
    if case.annotation_state == "unannotated":
        return base | {"status": "unannotated", "known_tp": 0, "known_fp": 0, "known_fn": 0,
                       "unresolved_pairs": 0, "diagnostic": "No reference; empty annotations are not a scientific negative"}
    pairs = [[_pair(case, expected, record) for expected in case.expected] for record in prediction.records]
    exact = maximum_matching([[j for j, pair in enumerate(row) if pair["full_record_agreement"] == "match"] for row in pairs])
    # Augmentation may reassign an exact pair to accommodate a deferred reference,
    # but never unmatches an already matched fully evaluable reference.
    combined = maximum_matching([[j for j, pair in enumerate(row)
                                  if pair["full_record_agreement"] in {"match", "deferred"}] for row in pairs], initial=exact)
    exact = {i: j for i, j in combined.items() if pairs[i][j]["full_record_agreement"] == "match"}
    unresolved = {i: j for i, j in combined.items() if pairs[i][j]["full_record_agreement"] == "deferred"}
    return base | {
        "status": "evaluated", "known_tp": len(exact),
        "known_fp": len(prediction.records) - len(exact) - len(unresolved),
        "known_fn": len(case.expected) - len(exact) - len(unresolved), "unresolved_pairs": len(unresolved),
        "exact_assignments": [{"prediction_index": i, "reference_index": j} for i, j in sorted(exact.items())],
        "deferred_assignments": [{"prediction_index": i, "reference_index": j} for i, j in sorted(unresolved.items())],
        "pair_comparisons": pairs,
        "empty_result": "reference_agreement" if not prediction.records and not case.expected else "not_applicable",
    }


def summarize(reference: PilotReference, rows: list[dict[str, Any]]) -> dict[str, Any]:
    if len(rows) != len(reference.cases):
        raise ValueError("Every declared case must remain in the evaluation")
    expected_count = sum(len(case.expected) for case in reference.cases)
    counts = {name: sum(row.get(name, 0) for row in rows) for name in ("known_tp", "known_fp", "known_fn", "unresolved_pairs")}
    deferred = sum(len(item.deferred) for case in reference.cases for item in case.expected)
    unavailable = [row for row in rows if row["status"] in {"unavailable", "invalid"}]
    incomplete = bool(unavailable or deferred or any(row["status"] == "unannotated" for row in rows))
    predictions = sum(row["proposed_records"] for row in rows if row["proposed_records"] is not None)
    return {
        "cases": len(rows), "expected_records": expected_count, "available_proposed_records": predictions,
        **counts, "deferred_dimensions": deferred, "unavailable_cases": len(unavailable),
        "unavailable_expected_records": sum(row["expected_records"] for row in unavailable),
        "precision_exact_reference": counts["known_tp"] / predictions if predictions and not incomplete else None,
        "recall_exact_reference": (counts["known_tp"] / expected_count if expected_count and not incomplete
                                   and all(case.exhaustive_scope for case in reference.cases) else None),
        "metric_basis": "Exact finite-reference text/status/anchor agreement; not scientific accuracy",
        "reference_kind": reference.reference_kind, "independence": "Caller-declared, not authenticated",
        "scientific_admission": "not_evaluated", "human_time_savings": None,
    }


def _render(reference: PilotReference, report: dict[str, Any]) -> str:
    sections = []
    for case, row in zip(reference.cases, report["cases"], strict=True):
        sources = []
        for region in case.context.regions:
            uri = Path(region.original_pdf_path).resolve().as_uri() + f"#page={region.page_number}"
            sources.append(f'<details><summary>PDF p.{region.page_number} · {html.escape(region.text_layer)}</summary>'
                           f'<a href="{html.escape(uri, quote=True)}">Оригинал</a><pre>{html.escape(region.quote)}</pre></details>')
        sections.append(f'<article><h2>{html.escape(case.case_id)}</h2><p>{html.escape(case.scope_note)}</p>'
                        f'<p>Status: {html.escape(row["status"])}</p><details><summary>Полный результат и назначения</summary>'
                        f'<pre>{html.escape(json.dumps(row, ensure_ascii=False, indent=2))}</pre></details>'
                        + "".join(sources) + '</article>')
    return ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>ARIADNE — record reference agreement</title>'
            '<style>body{font:15px system-ui;margin:24px;max-width:1200px}pre{white-space:pre-wrap;overflow-wrap:anywhere}'
            'article{border-top:1px solid #ccd4df;padding:12px 0}details{margin:10px 0}[hidden]{display:none!important}</style>'
            f'<h1>Records: {VERSION}</h1><p>Это сравнение с конечным эталоном. Научная точность не установлена.</p>'
            '<pre>' + html.escape(json.dumps(report["summary"], ensure_ascii=False, indent=2)) + '</pre>'
            '<label>Поиск <input id="search" type="search"></label>' + "".join(sections)
            + '<script>document.getElementById("search").addEventListener("input",e=>{const q=e.target.value.toLocaleLowerCase();'
            'document.querySelectorAll("article").forEach(a=>a.hidden=!a.textContent.toLocaleLowerCase().includes(q));});</script></html>\n')


def evaluate_pilot(reference_path: Path, predictions: Mapping[str, Path], output_dir: Path, *, source_root: Path) -> dict[str, Any]:
    if output_dir.exists():
        raise FileExistsError(f"Evaluation output already exists: {output_dir}")
    raw_reference = reference_path.read_bytes()
    reference = PilotReference.model_validate_json(raw_reference)
    if not set(predictions) <= {case.case_id for case in reference.cases}:
        raise ValueError("Prediction map contains unknown cases")
    rows = []
    snapshots: dict[Path, str] = {reference_path.resolve(): hashlib.sha256(raw_reference).hexdigest()}
    inputs: dict[str, bytes] = {"reference.json": raw_reference}
    for index, case in enumerate(reference.cases):
        context_path = Path(case.context_path).resolve()
        context_raw = context_path.read_bytes()
        if hashlib.sha256(context_raw).hexdigest() != case.context_sha256:
            raise ValueError(f"Changed reference source input: {case.case_id}")
        if CandidateBundle.model_validate_json(context_raw) != case.context:
            raise ValueError(f"Reference embedded context differs from bound input: {case.case_id}")
        snapshots[context_path] = case.context_sha256
        for region in case.context.regions:
            for stored_path, expected in ((region.original_pdf_path, region.original_pdf_sha256),
                                   (region.layer_pdf_path, region.layer_pdf_sha256)):
                resolved = Path(stored_path).resolve()
                if resolved in snapshots and snapshots[resolved] != expected:
                    raise ValueError(f"Conflicting source identity: {resolved}")
                snapshots[resolved] = expected
        unavailable = {"case_id": case.case_id, "expected_records": len(case.expected), "proposed_records": None}
        path = predictions.get(case.case_id)
        if path is None or not path.is_file():
            rows.append(unavailable | {"status": "unavailable", "diagnostic": "Declared prediction artifact unavailable"})
            continue
        raw = path.read_bytes()
        snapshots[path.resolve()] = hashlib.sha256(raw).hexdigest()
        inputs[f"prediction_{index + 1:04d}.json"] = raw
        try:
            bundle = CandidateBundle.model_validate_json(raw)
        except ValueError as exc:
            rows.append(unavailable | {"status": "invalid", "diagnostic": str(exc)})
            continue
        rows.append(compare_case(case, bundle))
    for path, expected in snapshots.items():
        if file_hash(path) != expected:
            raise ValueError(f"Source/input checksum mismatch: {path}")
    report = {"version": VERSION, "summary": summarize(reference, rows), "cases": rows,
              "reference_provenance": reference.model_dump(mode="json", exclude={"cases"}),
              "limitations": ["Saved candidates are caller-declared outputs, not raw model/runtime attestation.",
                              "Reference agreement and declarations of independence do not establish scientific acceptance.",
                              "Unavailable and deferred cases remain in the declared expected count."]}
    rendered = _render(reference, report)
    output_dir.mkdir(parents=True, exist_ok=False)
    for name, raw in inputs.items():
        (output_dir / name).write_bytes(raw)
    (output_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_dir / "review.html").write_text(rendered, encoding="utf-8")
    files = ("app/records/pilot_evaluation.py", "app/records/full_evaluation.py", "app/records/schema.py",
             "scripts/records_pilot_evaluate.py", "pyproject.toml")
    manifest = {"version": VERSION, "inputs": {str(path): expected for path, expected in snapshots.items()},
                "code": {name: file_hash(source_root / name) for name in files},
                "outputs": {path.name: file_hash(path) for path in sorted(output_dir.iterdir()) if path.is_file()}}
    (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report
