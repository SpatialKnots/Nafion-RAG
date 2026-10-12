"""Compare saved single-field outputs with provisional source-bound expectations."""

from __future__ import annotations

import hashlib
import html
import json
import platform
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import ValidationError

from app.records.reference import DevelopmentReference, FieldExpectation, ReferenceCase
from app.records.schema import TextObservation, text_hash
from app.records.smoke import SingleFieldReply, SpanFieldReply, resolve_single_field, resolve_span_field


def compare_observation(expected: FieldExpectation, actual: TextObservation) -> dict[str, str]:
    """Finite declared raw-answer/anchor agreement, not an open-ended semantic judge."""
    if expected.criterion == "deferred":
        return {"field_agreement": "deferred", "reference_anchor": "deferred", "abstention": "deferred"}
    abstained = actual.status != "present"
    if expected.criterion == "abstain":
        return {"field_agreement": "match" if abstained else "mismatch", "reference_anchor": "not_applicable",
                "abstention": "correct" if abstained else "false_assertion"}
    matches = [answer for answer in expected.answers if answer.raw_text == actual.raw_text] if not abstained else []
    anchored = any(
        span.region_id == anchor.region_id and span.start <= anchor.start and span.end >= anchor.end
        for answer in matches for anchor in answer.anchors for span in actual.evidence
    )
    return {"field_agreement": "match" if matches else "mismatch",
            "reference_anchor": "match" if anchored else "mismatch",
            "abstention": "missed_expected_field" if abstained else "not_applicable"}


def inspect_run(case: ReferenceCase, expected: FieldExpectation, directory: Path) -> tuple[dict[str, Any], list[tuple[Path, bytes]]]:
    files = [directory / name for name in ("input.json", "manifest.json", "request.json", "runtime_identity.json", "result.json")]
    snapshots = [(path, path.read_bytes()) for path in files]
    raw_input = snapshots[0][1]
    if hashlib.sha256(raw_input).hexdigest() != case.input_sha256:
        raise ValueError(f"Run input does not match frozen reference: {directory}")
    if case.context != type(case.context).model_validate_json(raw_input):
        raise ValueError(f"Reference source context disagrees with input: {directory}")
    manifest = json.loads(snapshots[1][1])
    request_bytes, identity_bytes = snapshots[2][1], snapshots[3][1]
    if manifest.get("request_sha256") != hashlib.sha256(request_bytes).hexdigest():
        raise ValueError(f"Request checksum mismatch: {directory}")
    if manifest.get("runtime_identity_sha256") != hashlib.sha256(identity_bytes).hexdigest():
        raise ValueError(f"Runtime identity checksum mismatch: {directory}")
    if manifest.get("requested_field") != expected.field or text_hash(manifest.get("task", "")) != case.task_sha256:
        raise ValueError(f"Run task or field differs from reference: {directory}")
    request = json.loads(request_bytes)
    user = json.loads(request["messages"][1]["content"])
    source_context = [
        {"region": f"R{index}", "article_id": str(region.article_id), "page": region.page_number,
         "text_layer": region.text_layer, "text": region.quote}
        for index, region in enumerate(case.context.regions, start=1)
    ]
    if user.get("field") != expected.field or text_hash(user.get("task", "")) != case.task_sha256:
        raise ValueError(f"Actual request task or field differs from reference: {directory}")
    if user.get("context") != source_context:
        raise ValueError(f"Actual request context differs from reference: {directory}")
    contract = manifest.get("output_contract")
    if contract not in {"records_smoke_single_field_v0.2", "records_smoke_span_field_v0.3"}:
        raise ValueError(f"Unsupported comparison contract: {contract}")
    recorded = json.loads(snapshots[4][1])
    row: dict[str, Any] = {
        "case": case.case_id, "field": expected.field, "criterion": expected.criterion,
        "expected_raw": [answer.raw_text for answer in expected.answers], "rationale": expected.rationale,
        "model_alias": manifest["model_alias"], "runtime_identity": json.loads(identity_bytes),
        "request_settings": {key: request.get(key) for key in ("model", "temperature", "seed", "max_tokens")},
        "system_prompt_sha256": text_hash(request["messages"][0]["content"]),
        "directory": str(directory), "recorded_status": recorded["status"], "elapsed_seconds": recorded.get("elapsed_seconds"),
        "wire_contract": "unavailable", "literal_integrity": "unavailable", "field_agreement": "unavailable",
        "reference_anchor": "unavailable", "abstention": "unavailable", "reference_agreement": False,
        "linkage": [item.model_dump(mode="json") for item in case.linkage], "scientific_admission": "not_evaluated",
    }
    response_path = directory / "response.json"
    if not response_path.is_file():
        row.update(diagnostic="Model response unavailable; recorded failure remains in denominator", recorded_error=recorded.get("error"))
        return row, snapshots
    response_bytes = response_path.read_bytes()
    snapshots.append((response_path, response_bytes))
    stage = "response_envelope"
    try:
        envelope = json.loads(response_bytes)
        choices = envelope.get("choices") if isinstance(envelope, dict) else None
        if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict):
            raise ValueError("Expected exactly one completion choice")
        message = choices[0].get("message")
        if not isinstance(message, dict) or not isinstance(message.get("content"), str):
            raise ValueError("Completion content is unavailable")
        content = message["content"]
        row["finish_reason"] = choices[0].get("finish_reason")
        output_path = directory / "model_output.txt"
        if output_path.is_file():
            output_bytes = output_path.read_bytes()
            snapshots.append((output_path, output_bytes))
            # Account only for the text copy's platform newline encoding; parse scientific text from raw response below.
            if output_bytes not in {content.encode("utf-8"), content.replace("\n", "\r\n").encode("utf-8")}:
                raise ValueError("Saved model text differs from raw response")
        if choices[0].get("finish_reason") != "stop":
            raise ValueError(f"Incomplete completion: {choices[0].get('finish_reason')}")
        stage = "wire_contract"
        output = SingleFieldReply.model_validate_json(content) if contract.endswith("v0.2") else SpanFieldReply.model_validate_json(content)
        row["wire_contract"] = "valid"
        row["wire_output"] = output.model_dump(mode="json")
        stage = "literal_integrity"
        observation = (
            resolve_single_field(case.context, output, expected.field) if isinstance(output, SingleFieldReply)
            else resolve_span_field(case.context, output, expected.field)
        )[expected.field]
        row.update(literal_integrity="valid", observation=observation.model_dump(mode="json"))
        row.update(compare_observation(expected, observation))
        row["reference_agreement"] = (
            row["field_agreement"] == "match" and row["reference_anchor"] in {"match", "not_applicable"}
        )
    except (ValueError, ValidationError) as exc:
        row.update(diagnostic=str(exc), failed_stage=stage)
        row[stage] = "invalid"
    if (row["literal_integrity"] == "valid") != (recorded["status"] == "integrity_valid"):
        row["recorded_outcome_disagrees"] = True
    return row, snapshots


def _cell(value: object) -> str:
    return html.escape(json.dumps(value, ensure_ascii=False), quote=False).replace("|", "&#124;").replace("`", "&#96;")


def render_comparison(report: dict[str, Any]) -> str:
    lines = ["# Development reference comparison", "", "Reference status: needs_independent_review. Scientific admission: not_evaluated.",
             "", "Counts measure agreement with provisional raw answers and source anchors, not independent scientific accuracy.",
             "Sample, condition and origin linkage decisions remain visible in report.json and require independent review.", ""]
    for batch in report["batches"]:
        lines.extend([f"## Batch {_cell(batch['path'])}", "", f"Summary: {_cell(batch['summary'])}", "",
                      "| Case | Field | Expected raw | Proposed raw | Wire | Literal | Field agreement |"
                      " Anchor | Abstention | Reference agreement |",
                      "|---|---|---|---|---|---|---|---|---|---|"])
        for row in batch["rows"]:
            wire = row.get("wire_output", {})
            proposed = wire.get("raw_text", wire.get("text"))
            values = [row["case"], row["field"], row["expected_raw"], proposed, row["wire_contract"], row["literal_integrity"],
                      row["field_agreement"], row["reference_anchor"], row["abstention"], row["reference_agreement"]]
            lines.append("| " + " | ".join(_cell(value) for value in values) + " |")
        lines.append("")
    return "\n".join(lines)


def compare_batches(reference_path: Path, batch_paths: list[Path], output_dir: Path, *, source_root: Path) -> dict[str, Any]:
    raw_reference = reference_path.read_bytes()
    reference = DevelopmentReference.model_validate_json(raw_reference)
    cases = {case.case_id: case for case in reference.cases}
    artifacts: dict[str, dict[str, Any]] = {}

    def capture(path: Path, raw: bytes) -> None:
        artifacts[str(path.resolve())] = {"path": str(path.resolve()), "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}

    capture(reference_path, raw_reference)
    batches = []
    for path in batch_paths:
        batch_bytes = path.read_bytes()
        batch = json.loads(batch_bytes)
        if not isinstance(batch, dict) or not isinstance(batch.get("runs"), list):
            raise ValueError("Batch must contain a runs array")
        capture(path, batch_bytes)
        entries = {}
        for run in batch["runs"]:
            key = (run["case"], run["field"])
            if key in entries or key[0] not in cases or key[1] not in {item.field for item in cases[key[0]].fields}:
                raise ValueError(f"Duplicate or unknown batch field: {key}")
            directory = Path(run["directory"])
            directory = (directory if directory.is_absolute() else source_root / directory).resolve()
            if not directory.is_relative_to(path.parent.resolve()):
                raise ValueError("Run directory must remain within its batch directory")
            entries[key] = directory
        rows: list[dict[str, Any]] = []
        for case in reference.cases:
            for expected in case.fields:
                field_directory = entries.get((case.case_id, expected.field))
                if field_directory is None:
                    rows.append({"case": case.case_id, "field": expected.field, "criterion": expected.criterion,
                                 "expected_raw": [answer.raw_text for answer in expected.answers], "reference_agreement": False,
                                 "wire_contract": "unavailable", "literal_integrity": "unavailable", "field_agreement": "unavailable",
                                 "reference_anchor": "unavailable", "abstention": "unavailable", "diagnostic": "Missing batch field",
                                 "linkage": [item.model_dump(mode="json") for item in case.linkage]})
                    continue
                row, files = inspect_run(case, expected, field_directory)
                rows.append(row)
                for file, raw in files:
                    capture(file, raw)
        summary = {"expected_fields": len(rows), "deferred_fields": sum(row["criterion"] == "deferred" for row in rows),
                   "literal_valid": sum(row["literal_integrity"] == "valid" for row in rows),
                   "reference_agreements": sum(row["reference_agreement"] for row in rows),
                   "field_outcomes": dict(Counter(row["field_agreement"] for row in rows)),
                   "abstention_outcomes": dict(Counter(row["abstention"] for row in rows))}
        batches.append({"path": str(path.resolve()), "summary": summary, "rows": rows})
    if not batches:
        raise ValueError("At least one comparison batch is required")
    source_root = source_root.resolve()
    if not (source_root / "app" / "records" / "comparison.py").is_file():
        raise ValueError("source_root must contain the ARIADNE comparison implementation")
    paths = sorted((source_root / "app").rglob("*.py")) + [source_root / "pyproject.toml"]
    code_files = [
        {"path": path.relative_to(source_root).as_posix(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in paths
    ]
    code = {"code_files": code_files, "code_fingerprint_sha256": text_hash(json.dumps(code_files, sort_keys=True)),
            "reference_schema_sha256": text_hash(json.dumps(DevelopmentReference.model_json_schema(), sort_keys=True)),
            "python": platform.python_version(), "platform": platform.platform()}
    report = {"comparison_version": "records_reference_comparison_v0.1", "report_id": str(uuid4()),
              "created_at": datetime.now(UTC).isoformat(), "reference_id": str(reference.reference_id),
              "reference_status": reference.status, "scientific_admission": "not_evaluated", "batches": batches,
              "artifacts": list(artifacts.values()), "evaluator": code, "limitations": list(reference.limitations)}
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "reference.json").write_bytes(raw_reference)
    with (output_dir / "report.json").open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    with (output_dir / "report.md").open("x", encoding="utf-8") as stream:
        stream.write(render_comparison(report) + "\n")
    return report
