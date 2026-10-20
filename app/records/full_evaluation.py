"""Full bounded record agreement against declared development references, not accuracy."""

from __future__ import annotations

import hashlib
import html
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Self
from uuid import UUID

from pydantic import Field, model_validator

from app.records.compact import VERSION as COMPACT_VERSION
from app.records.compact import build_compact_request, parse_compact_completion, resolve_compact_reply
from app.records.extraction import (
    FIELDS,
    LINK_ROLES,
    VERSION,
    build_record_request,
    parse_completion,
    require_source_only,
    resolve_reply,
    write_json,
)
from app.records.openai_backend import (
    FORMAT_VERSIONS,
    WireFormat,
    build_openai_request,
    openai_identity,
    resolve_openai_response,
)
from app.records.openai_backend import (
    VERSIONS as OPENAI_VERSIONS,
)
from app.records.runs import build_manifest
from app.records.schema import (
    CandidateBundle,
    ContractModel,
    EvidenceSpan,
    LinkageProposal,
    NonEmpty,
    RecordCandidate,
    Sha256,
    TextObservation,
    text_hash,
)

DIMENSIONS = (*FIELDS, "representation", *LINK_ROLES)


def unavailable_dimensions(case: FullRecordCase, outcome: str) -> dict[str, dict[str, str]]:
    return {name: {"outcome": outcome, "diagnostic": "No resolved record available for this expected dimension"}
            for name in DIMENSIONS} if case.expected else {}


def observations(record: RecordCandidate) -> dict[str, TextObservation]:
    quantity = record.value
    return {name: getattr(record, name) for name in FIELDS if name not in {"value", "unit", "approximation", "uncertainty"}} | {
        "value": quantity.raw_value, "unit": quantity.raw_unit,
        "approximation": quantity.approximation, "uncertainty": quantity.uncertainty,
    }


class FullRecordCase(ContractModel):
    case_id: NonEmpty
    input_sha256: Sha256
    task: NonEmpty
    context: CandidateBundle
    expected: tuple[RecordCandidate, ...] = Field(max_length=1)
    deferred: dict[str, NonEmpty]
    rationale: NonEmpty

    @model_validator(mode="after")
    def validate_case(self) -> Self:
        require_source_only(self.context)
        if not self.task.strip():
            raise ValueError("Nonempty task required")
        if not set(self.deferred) <= set(DIMENSIONS):
            raise ValueError("Unknown deferred dimension")
        data = self.context.model_dump()
        CandidateBundle.model_validate({**data, "records": self.expected})
        if not self.expected and self.deferred:
            raise ValueError("Empty reference cannot declare record dimensions")
        if self.expected:
            for name, obs in observations(self.expected[0]).items():
                if obs.status in {"ambiguous", "unsupported"} and name not in self.deferred:
                    raise ValueError(f"Unresolved reference dimension must be deferred: {name}")
        return self


class FullRecordReference(ContractModel):
    schema_version: Literal["records_full_reference_v0.1"] = "records_full_reference_v0.1"
    reference_id: UUID
    created_at: datetime
    author: NonEmpty
    status: Literal["needs_independent_review"] = "needs_independent_review"
    cases: tuple[FullRecordCase, ...] = Field(min_length=1)
    limitations: tuple[NonEmpty, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_identity(self) -> Self:
        if self.created_at.utcoffset() is None:
            raise ValueError("Reference timestamp must include timezone")
        if len({case.case_id for case in self.cases}) != len(self.cases):
            raise ValueError("Duplicate reference case")
        return self


def covers(proposed: tuple[EvidenceSpan, ...], expected: tuple[EvidenceSpan, ...]) -> bool:
    return all(any(p.region_id == e.region_id and p.start <= e.start and p.end >= e.end for p in proposed) for e in expected)


def compare_record(case: FullRecordCase, candidate: RecordCandidate) -> dict[str, Any]:
    expected = case.expected[0]
    if candidate.article_id != expected.article_id:
        raise ValueError("Candidate belongs to a different article")
    actual_fields = observations(candidate)
    dimensions: dict[str, dict[str, Any]] = {}
    for name, obs in observations(expected).items():
        actual = actual_fields[name]
        raw_match = actual.status == obs.status and actual.raw_text == obs.raw_text
        anchor_match = obs.status != "present" or covers(actual.evidence, obs.evidence)
        dimensions[name] = {
            "outcome": "match" if raw_match and anchor_match else "mismatch", "raw_agreement": raw_match,
            "anchor_agreement": anchor_match, "expected": obs.model_dump(mode="json"), "actual": actual.model_dump(mode="json"),
        }
    dimensions["representation"] = {"outcome": "match" if candidate.value.representation == expected.value.representation else "mismatch",
                                     "expected": expected.value.representation, "actual": candidate.value.representation}
    actual_links: dict[str, LinkageProposal] = {link.role: link for link in candidate.linkage}
    expected_links: dict[str, LinkageProposal] = {link.role: link for link in expected.linkage}
    for role in LINK_ROLES:
        actual_link, expected_link = actual_links.get(role), expected_links.get(role)
        match = (actual_link is None) if expected_link is None else (
            actual_link is not None and covers(actual_link.evidence, expected_link.evidence))
        dimensions[role] = {"outcome": "match" if match else "mismatch",
                            "expected": expected_link.model_dump(mode="json") if expected_link else None,
                            "actual": actual_link.model_dump(mode="json") if actual_link else None,
                            "meaning": "Role and source-anchor agreement only; scientific entailment is not evaluated"}
    for name, reason in case.deferred.items():
        dimensions[name].update(outcome="deferred", reason=reason)
    outcomes = Counter(row["outcome"] for row in dimensions.values())
    return {"dimensions": dimensions, "dimension_outcomes": dict(outcomes),
            "full_record_agreement": "mismatch" if outcomes["mismatch"] else "deferred" if outcomes["deferred"] else "match"}


def inspect_extraction(case: FullRecordCase, directory: Path) -> dict[str, Any]:
    row: dict[str, Any] = {"case_id": case.case_id, "expected_records": len(case.expected), "proposed_records": None,
                           "status": "unavailable", "full_record_agreement": "unavailable",
                           "abstention": "unavailable", "deferred": case.deferred,
                           "dimensions": unavailable_dimensions(case, "unavailable")}
    missing = [name for name in ("input.json", "manifest.json", "request.json", "runtime_identity.json")
               if not (directory / name).is_file()]
    if missing:
        row["diagnostic"] = "Required run artifacts unavailable: " + ", ".join(missing)
        return row
    # Binding errors are invalid experiments and stop evaluation, rather than becoming low accuracy.
    raw_input = (directory / "input.json").read_bytes()
    manifest_raw, request_raw = (directory / "manifest.json").read_bytes(), (directory / "request.json").read_bytes()
    manifest, request = json.loads(manifest_raw), json.loads(request_raw)
    if hashlib.sha256(raw_input).hexdigest() != case.input_sha256:
        raise ValueError("Run input differs from fixed reference bytes")
    context = CandidateBundle.model_validate_json(raw_input)
    if context != case.context:
        raise ValueError("Run source context differs from reference")
    version = manifest.get("extraction_version")
    if (version not in {VERSION, COMPACT_VERSION, *OPENAI_VERSIONS} or manifest.get("input_sha256") != case.input_sha256
            or manifest.get("task") != case.task or manifest.get("task_sha256") != text_hash(case.task)
            or manifest.get("request_sha256") != hashlib.sha256(request_raw).hexdigest()):
        raise ValueError("Run manifest input/task/request binding mismatch")
    is_openai = version in OPENAI_VERSIONS
    if is_openai:
        api_format: WireFormat = next(name for name, identifier in FORMAT_VERSIONS.items() if identifier == version)
        expected_request = build_openai_request(context, case.task, request["model"], request["max_output_tokens"],
                                               api_format, request["reasoning"]["effort"])
    else:
        builder = build_compact_request if version == COMPACT_VERSION else build_record_request
        expected_request = builder(context, case.task, request["model"], request["max_tokens"], request["seed"])
    if request != expected_request:
        raise ValueError("Run request differs from the fixed bounded extraction contract")
    runtime_raw = (directory / "runtime_identity.json").read_bytes()
    if hashlib.sha256(runtime_raw).hexdigest() != manifest.get("runtime_identity_sha256"):
        raise ValueError("Run runtime declaration checksum mismatch")
    identity = json.loads(runtime_raw)
    if not isinstance(identity, dict) or identity.get("model_alias") != request["model"]:
        raise ValueError("Run model differs from declared runtime")
    if is_openai and identity != openai_identity(request, api_format):
        raise ValueError("OpenAI runtime declaration differs from fixed backend settings")
    response_path = directory / "response.json"
    if not response_path.is_file():
        row["diagnostic"] = "Raw response unavailable; transport/missing run remains in denominator"
        row["dimensions"] = unavailable_dimensions(case, "unavailable")
        return row
    try:
        raw_response = response_path.read_bytes()
        if is_openai:
            _, prediction = resolve_openai_response(context, raw_response, api_format)
        else:
            prediction = (resolve_compact_reply(context, parse_compact_completion(raw_response)) if version == COMPACT_VERSION
                          else resolve_reply(context, parse_completion(raw_response)))
    except ValueError as exc:
        row.update(status="invalid", diagnostic=str(exc), dimensions=unavailable_dimensions(case, "unavailable"))
        return row
    row.update(status="integrity_valid", proposed_records=len(prediction.records),
               candidates=prediction.model_dump(mode="json"),
               missed_records=max(0, len(case.expected) - len(prediction.records)),
               extra_records=max(0, len(prediction.records) - len(case.expected)))
    if not case.expected:
        row.update(abstention="correct" if not prediction.records else "false_assertion",
                   full_record_agreement="not_applicable")
    elif not prediction.records:
        row.update(abstention="missed_record", full_record_agreement="mismatch", dimensions=unavailable_dimensions(case, "missed"))
    else:
        row.update(abstention="not_applicable", **compare_record(case, prediction.records[0]))
    return row


def render_evaluation(report: dict[str, Any]) -> str:
    def escaped(value: object) -> str:
        return html.escape(json.dumps(value, ensure_ascii=False, indent=2))

    rows: list[str] = []
    for row in report["cases"]:
        source_links = []
        for region in row["source_context"]:
            url = Path(region["original_pdf_path"]).resolve().as_uri() + f'#page={region["page_number"]}'
            label = f'PDF page {region["page_number"]} · {region["text_layer"]}'
            source_links.append(f'<details><summary><a href="{html.escape(url, quote=True)}">{html.escape(label)}</a>'
                                f'</summary><pre>{html.escape(region["quote"])}</pre></details>')
        details = {key: value for key, value in row.items() if key != "source_context"}
        rows.append(f'<tr><td>{html.escape(row["case_id"])}</td><td>{row["expected_records"]}</td>'
                    f'<td>{row.get("proposed_records")}</td><td>{row["status"]}</td>'
                    f'<td>{row["full_record_agreement"]}</td><td>{row["abstention"]}</td>'
                    f'<td><details><summary>Fields, links and diagnostics</summary><pre>{escaped(details)}</pre></details>'
                    + ''.join(source_links) + '</td></tr>')
    return ('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
            '<title>ARIADNE bounded record development evaluation</title><style>'
            'body{font:16px system-ui;margin:24px}table{border-collapse:collapse;width:100%}td,th{border:1px solid #bbb;'
            'padding:8px;vertical-align:top}pre{white-space:pre-wrap;overflow-wrap:anywhere;max-width:75vw}</style>'
            '<h1>Bounded record development evaluation</h1><p>Reference: needs_independent_review. '
            'Finite source-bound agreement; scientific admission: not_evaluated. Missing and failed runs retained.</p>'
            f'<pre>{escaped(report["summary"])}</pre><table><thead><tr><th>Case</th><th>Expected</th><th>Proposed</th>'
            '<th>Integrity</th><th>Full record</th><th>Abstention</th><th>Details</th></tr></thead><tbody>'
            + ''.join(rows) + '</tbody></table></html>')


def evaluate_extractions(reference_path: Path, runs: dict[str, Path], output_dir: Path, *, source_root: Path) -> dict[str, Any]:
    raw_reference = reference_path.read_bytes()
    reference = FullRecordReference.model_validate_json(raw_reference)
    if not set(runs) <= {case.case_id for case in reference.cases}:
        raise ValueError("Unknown run case")
    rows: list[dict[str, Any]] = []
    artifacts = []
    captured: dict[str, bytes] = {"reference.json": raw_reference}
    for index, case in enumerate(reference.cases):
        if case.case_id not in runs:
            rows.append({"case_id": case.case_id, "expected_records": len(case.expected), "proposed_records": None,
                         "status": "unavailable", "full_record_agreement": "unavailable", "abstention": "unavailable",
                         "diagnostic": "Missing run; retained in denominator", "deferred": case.deferred,
                         "source_context": [r.model_dump(mode="json") for r in case.context.regions],
                         "dimensions": unavailable_dimensions(case, "unavailable")})
            continue
        directory = runs[case.case_id]
        row = inspect_extraction(case, directory)
        row["source_context"] = [r.model_dump(mode="json") for r in case.context.regions]
        for name in ("input.json", "manifest.json", "request.json", "runtime_identity.json", "response.json", "result.json"):
            path = directory / name
            if path.is_file():
                raw = path.read_bytes()
                target = f"runs/{index}/{name}"
                captured[target] = raw
                artifacts.append({"case_id": case.case_id, "source_path": str(path.resolve()), "snapshot_path": target,
                                  "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)})
        rows.append(row)
    summary = {
        "cases": len(rows), "expected_records": sum(row["expected_records"] for row in rows),
        "expected_record_dimensions": len(DIMENSIONS) * sum(row["expected_records"] for row in rows),
        "proposed_records_in_valid_runs": sum(row["proposed_records"] or 0 for row in rows),
        "integrity_valid_cases": sum(row["status"] == "integrity_valid" for row in rows),
        "failed_or_missing_cases": sum(row["status"] != "integrity_valid" for row in rows),
        "expected_records_in_failed_or_missing_cases": sum(row["expected_records"] for row in rows if row["status"] != "integrity_valid"),
        "missed_records_in_valid_runs": sum(row.get("missed_records", 0) for row in rows),
        "extra_records_in_valid_runs": sum(row.get("extra_records", 0) for row in rows),
        "full_record_outcomes": dict(Counter(row["full_record_agreement"] for row in rows)),
        "abstention_outcomes": dict(Counter(row["abstention"] for row in rows)),
        "dimension_outcomes": dict(Counter(d["outcome"] for row in rows for d in row.get("dimensions", {}).values())),
    }
    first_context = reference.cases[0].context
    # Capture current evaluator code using the existing manifest helper, without a database read.
    output_dir.mkdir(parents=True, exist_ok=False)
    for name, content in captured.items():
        destination = output_dir / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
    write_json(output_dir / "context_for_code_manifest.json", first_context.model_dump(mode="json"))
    evaluator = build_manifest(output_dir / "context_for_code_manifest.json", operation="context_export", source_root=source_root)
    report = {"evaluation_version": "records_full_evaluation_v0.1", "created_at": datetime.now(UTC).isoformat(),
              "reference_status": reference.status, "reference_sha256": hashlib.sha256(raw_reference).hexdigest(),
              "scientific_admission": "not_evaluated", "summary": summary, "cases": rows,
              "artifacts": artifacts, "evaluator": evaluator, "limitations": list(reference.limitations)}
    write_json(output_dir / "report.json", report)
    with (output_dir / "review.html").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(render_evaluation(report))
    return report
