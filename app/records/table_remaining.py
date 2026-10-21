"""Finish the declared numeric source-slot scope without mutating frozen parent stages."""

from __future__ import annotations

import html
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError

from app.evaluation.context_compaction import SourcePage
from app.records.checks import check_bundle
from app.records.extraction import write_json
from app.records.multi import parse_multi_reply, resolve_multi_reply
from app.records.multi_html import render_smoke
from app.records.multi_run import MAX_OUTPUT_TOKENS, MODEL, TIMEOUT_SECONDS, _safe, verify_hashes
from app.records.openai_backend import ENDPOINT, responses_content, send_openai_request
from app.records.readiness import assess_readiness
from app.records.schema import CandidateBundle
from app.records.sources import file_hash
from app.records.table_cells import bind_reply, token_address
from app.records.table_continuation import build_request, guard_request, load_prepared, render_ledger

VERSION = "records_table_remaining_v0.1"
CASE_IDS = tuple(f"remaining_{i:02}" for i in range(4, 12))
TARGET_COUNT = 23
MAX_CALLS = 8
CODE = ("app/records/table_remaining.py", "scripts/records_table_remaining.py",
        "tests/unit/test_record_table_remaining.py", "docs/records/table_remaining_protocol_v0.1.md")


def accounting(ledger: dict[str, Any]) -> dict[str, Any]:
    previous, added, numeric = set(), set(), set()
    identifiers, records = set(), set()
    for cell in ledger["slots"]:
        identifier = cell["cell_id"]
        if identifier in identifiers:
            raise ValueError("Duplicate source-cell identity in inherited ledger")
        identifiers.add(identifier)
        history = cell["previous_proposals"] + [p["record_id"] for p in cell["new_proposals"]]
        current = [p["record_id"] for p in cell.get("stage22_proposals", [])]
        for record in history + current:
            if record in records:
                raise ValueError("Repeated record identity in ledger proposal history")
            records.add(record)
        if cell["source_state"] == "numeric_source_proposal":
            numeric.add(identifier)
        elif history or current:
            raise ValueError("Non-numeric source slot carries a numeric proposal")
        if history:
            previous.add(identifier)
        if current:
            if history or len(current) > 1:
                raise ValueError("Stage22 must not revisit or duplicate a source cell")
            added.add(identifier)
    result = dict(ledger["summary"])
    result.update(previous_covered_cells=len(previous), new_covered_cells=len(added),
                  combined_covered_cells=len(previous | added), remaining_numeric_cells=len(numeric - previous - added))
    if len(numeric) != result["numeric_source_proposal"] or len(identifiers) != result["logical_slots"]:
        raise ValueError("Inherited source denominator differs from actual ledger slots")
    if len(numeric) != len(previous) + len(added) + result["remaining_numeric_cells"]:
        raise ValueError("Numeric-slot conservation failed")
    return result


def target_cases(bundle: CandidateBundle, ledger: dict[str, Any]) -> list[dict[str, Any]]:
    counts = accounting(ledger)
    if (counts["logical_slots"] != 42 or counts["numeric_source_proposal"] != 36
            or counts["previous_covered_cells"] != 13 or counts["new_covered_cells"] != 0
            or counts["remaining_numeric_cells"] != TARGET_COUNT):
        raise ValueError("Expected immutable stage21 scope: 42 slots, 36 numeric, 13 covered, 23 remaining")
    if any(s.get("stage22_outcomes") for s in ledger["slots"]):
        raise ValueError("Prepared ledger already contains stage22 execution outcomes")
    remaining = [s for s in ledger["slots"] if s["source_state"] == "numeric_source_proposal"
                 and not (s["previous_proposals"] or s["new_proposals"])]
    if [(s["row"], s["column"]) for s in remaining] != sorted((s["row"], s["column"]) for s in remaining):
        raise ValueError("Remaining source-cell order differs from declared row/column order")
    table = bundle.regions[0]
    if table.region_id != ledger["region_id"]:
        raise ValueError("Prepared table source region differs from inherited ledger")
    cases = []
    for index, case_id in enumerate(CASE_IDS):
        selected = remaining[index * 3:index * 3 + 3]
        targets = [{"cell_id": s["cell_id"], "sample": token_address(table, s["sample"]["start"], s["sample"]["end"]),
                    "column": token_address(table, s["header"]["start"], s["header"]["end"])} for s in selected]
        cases.append({"case_id": case_id, "input": f"{case_id}/input.json", "request": f"{case_id}/request.json",
                      "targets": targets, "revisit": False})
    return cases


def verify_parent_outputs(prepared: Path, previous: Path) -> tuple[CandidateBundle, dict[str, Any], list[SourcePage], dict[str, str]]:
    plan, source_ledger, pages, inputs = load_prepared(prepared)
    previous = previous.resolve()
    manifest_path = previous / "manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    if manifest["version"] != "records_table_continuation_v0.1":
        raise ValueError("Unexpected parent run version")
    if manifest["prepared_manifest_sha256"] != file_hash(prepared / "manifest.json"):
        raise ValueError("Parent run is bound to a different preparation")
    inputs[str(manifest_path)] = file_hash(manifest_path)
    inputs.update({str(_safe(previous, name)): expected for name, expected in manifest["artifacts"].items()})
    verify_hashes(inputs)
    report = json.loads((previous / "report.json").read_bytes())
    if (report["final_source_integrity"]["status"] != "verified" or len(report["cases"]) != len(plan["cases"])
            or any(r["status"] != "integrity_valid" for r in report["cases"])):
        raise ValueError("Parent run is incomplete or failed")
    ledger = json.loads((previous / "ledger.json").read_bytes())
    if len(ledger["slots"]) != len(source_ledger["slots"]):
        raise ValueError("Parent ledger inventory changed")
    for original, cell in zip(source_ledger["slots"], ledger["slots"], strict=True):
        if any(cell.get(key) != value for key, value in original.items()):
            raise ValueError("Parent ledger altered an inherited source field")
    expected_history: dict[str, list[dict[str, Any]]] = {s["cell_id"]: [] for s in ledger["slots"]}
    reference: CandidateBundle | None = None
    for case, row in zip(plan["cases"], report["cases"], strict=True):
        if row["case_id"] != case["case_id"] or row["targets"] != case["targets"]:
            raise ValueError("Parent case scope/order differs from preparation")
        directory = previous / case["case_id"]
        raw_input, payload = (prepared / case["input"]).read_bytes(), (prepared / case["request"]).read_bytes()
        if raw_input != (directory / "input.json").read_bytes() or payload != (directory / "request.json").read_bytes():
            raise ValueError("Parent actual input/request bytes differ from preparation")
        bundle = CandidateBundle.model_validate_json(raw_input)
        guard_request(json.loads(payload), bundle, case["targets"], pages)
        if reference is not None and bundle != reference:
            raise ValueError("Parent continuation cases used different source bundles")
        reference = bundle
        reply = parse_multi_reply(responses_content((directory / "response.json").read_bytes()))
        saved_reply = parse_multi_reply((directory / "reply.json").read_text(encoding="utf-8"))
        restored, unresolved = resolve_multi_reply(bundle, reply)
        saved = CandidateBundle.model_validate_json((directory / "candidates.json").read_bytes())
        if (reply != saved_reply or restored.records != saved.records or restored.regions != saved.regions
                or unresolved != json.loads((directory / "unresolved.json").read_bytes())):
            raise ValueError("Parent native response replay differs from saved output")
        ids = bind_reply(bundle, reply, ledger, targets=[t["cell_id"] for t in case["targets"]], require_method_region=True)
        expected_bindings = [{"cell_id": identifier, "record_id": str(record.record_id)}
                             for identifier, record in zip(ids, saved.records, strict=True)]
        if ids != row["bound_cells"] or expected_bindings != json.loads((directory / "cell_bindings.json").read_bytes()):
            raise ValueError("Parent replay source-cell bindings differ")
        for identifier, record in zip(ids, saved.records, strict=True):
            expected_history[identifier].append({"record_id": str(record.record_id), "case_id": case["case_id"],
                                                 "revisit": case["revisit"]})
    if reference is None:
        raise ValueError("Parent run has no source bundle")
    if any(cell["new_proposals"] != expected_history[cell["cell_id"]] for cell in ledger["slots"]):
        raise ValueError("Parent proposal history differs from native replay")
    target_cases(reference, ledger)
    return reference, ledger, pages, inputs


def prepare_remaining(prepared: Path, previous: Path, output: Path, *, source_root: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(output)
    bundle, ledger, pages, inputs = verify_parent_outputs(prepared.resolve(), previous.resolve())
    if len(pages) != 62:
        raise ValueError("Expected all 62 registered source pages")
    code = {str((source_root / name).resolve()): file_hash(source_root / name) for name in CODE}
    for cell in ledger["slots"]:
        cell.update(stage22_proposals=[], stage22_outcomes=[])
    ledger.update(continuation_version=VERSION, stage22_summary=accounting(ledger))
    cases = target_cases(bundle, ledger)
    payloads = []
    for case in cases:
        request = build_request(bundle, case["targets"])
        guard_request(request, bundle, case["targets"], pages)
        payloads.append(json.dumps(request, ensure_ascii=False).encode("utf-8"))
    verify_hashes(inputs | code)
    output.mkdir(parents=True, exist_ok=False)
    for case, payload in zip(cases, payloads, strict=True):
        (output / case["case_id"]).mkdir()
        write_json(output / case["input"], bundle.model_dump(mode="json"))
        (output / case["request"]).write_bytes(payload)
    write_json(output / "ledger.json", ledger)
    write_json(output / "page_registry.json", [vars(page) for page in pages])
    write_json(output / "plan.json", {"version": VERSION, "cases": cases, "endpoint": ENDPOINT, "model": MODEL,
                                      "maximum_calls": MAX_CALLS, "max_output_tokens_per_call": MAX_OUTPUT_TOKENS,
                                      "maximum_output_tokens_all_calls": MAX_CALLS * MAX_OUTPUT_TOKENS,
                                      "timeout_seconds": TIMEOUT_SECONDS, "declared_targets": TARGET_COUNT})
    verify_hashes(inputs | code)
    write_json(output / "manifest.json", {"version": VERSION, "inputs": inputs, "code": code,
                                           "artifacts": {p.relative_to(output).as_posix(): file_hash(p)
                                                         for p in sorted(output.rglob("*")) if p.is_file()}})
    return {"version": VERSION, "cases": len(cases), "targets": TARGET_COUNT,
            "source_accounting": ledger["stage22_summary"], "maximum_calls": MAX_CALLS, "new_model_calls": 0}


def load_remaining(prepared: Path) -> tuple[dict[str, Any], dict[str, Any], list[SourcePage], dict[str, str]]:
    manifest_path = prepared / "manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    if manifest["version"] != VERSION:
        raise ValueError("Unexpected remaining-table preparation version")
    bindings = manifest["inputs"] | manifest["code"] | {str(manifest_path.resolve()): file_hash(manifest_path)}
    bindings.update({str(_safe(prepared, name)): expected for name, expected in manifest["artifacts"].items()})
    verify_hashes(bindings)
    plan = json.loads((prepared / "plan.json").read_bytes())
    settings = {"version": VERSION, "endpoint": ENDPOINT, "model": MODEL, "maximum_calls": MAX_CALLS,
                "max_output_tokens_per_call": MAX_OUTPUT_TOKENS, "maximum_output_tokens_all_calls": MAX_CALLS * MAX_OUTPUT_TOKENS,
                "timeout_seconds": TIMEOUT_SECONDS, "declared_targets": TARGET_COUNT}
    if any(plan.get(key) != value for key, value in settings.items()):
        raise ValueError("Frozen remaining-table budget/settings changed")
    ledger = json.loads((prepared / "ledger.json").read_bytes())
    first = CandidateBundle.model_validate_json((prepared / f"{CASE_IDS[0]}/input.json").read_bytes())
    if plan["cases"] != target_cases(first, ledger) or ledger["stage22_summary"] != accounting(ledger):
        raise ValueError("Frozen remaining-table target partition/order/accounting changed")
    pages = [SourcePage(**p) for p in json.loads((prepared / "page_registry.json").read_bytes())]
    if len(pages) != 62:
        raise ValueError("Complete remaining-table page registry is required")
    return plan, ledger, pages, bindings


def attempt_case(case: dict[str, Any], prepared: Path, output: Path, ledger: dict[str, Any],
                 pages: list[SourcePage], bindings: dict[str, str], api_key: str) -> dict[str, Any]:
    row: dict[str, Any] = {**case, "status": "unattempted", "model_calls": 0, "usage": None}
    directory = output / case["case_id"]
    directory.mkdir()
    started, stage = time.perf_counter(), "frozen_binding"
    try:
        verify_hashes(bindings)
        raw, payload = _safe(prepared, case["input"]).read_bytes(), _safe(prepared, case["request"]).read_bytes()
        bundle = CandidateBundle.model_validate_json(raw)
        guard_request(json.loads(payload), bundle, case["targets"], pages)
        if payload != json.dumps(build_request(bundle, case["targets"]), ensure_ascii=False).encode("utf-8"):
            raise ValueError("Actual request bytes differ from frozen request")
        (directory / "input.json").write_bytes(raw)
        (directory / "request.json").write_bytes(payload)
        stage, row["model_calls"] = "transport", 1
        response, request_id = send_openai_request(payload, api_key, TIMEOUT_SECONDS)
        (directory / "response.json").write_bytes(response)
        stage = "completion_contract"
        envelope = json.loads(response)
        if isinstance(envelope, dict):
            row.update(request_id=request_id, response_id=envelope.get("id"), returned_model=envelope.get("model"),
                       response_status=envelope.get("status"), usage=envelope.get("usage"),
                       incomplete_details=envelope.get("incomplete_details"))
        reply = parse_multi_reply(responses_content(response))
        write_json(directory / "reply.json", reply.model_dump(mode="json"))
        stage = "source_cell_binding"
        candidates, unresolved = resolve_multi_reply(bundle, reply)
        ids = bind_reply(bundle, reply, ledger, targets=[t["cell_id"] for t in case["targets"]], require_method_region=True)
        if reply.coverage == "claimed_complete_in_context" and len(ids) != len(case["targets"]):
            raise ValueError("Claimed target completeness contradicts missing target cells")
        stage = "source_postflight"
        verify_hashes(bindings)
        write_json(directory / "candidates.json", candidates.model_dump(mode="json"))
        write_json(directory / "unresolved.json", unresolved)
        write_json(directory / "checks.json", [c.model_dump(mode="json") for c in check_bundle(candidates)])
        write_json(directory / "cell_bindings.json", [{"cell_id": identifier, "record_id": str(record.record_id)}
                                                      for identifier, record in zip(ids, candidates.records, strict=True)])
        for identifier, record in zip(ids, candidates.records, strict=True):
            next(s for s in ledger["slots"] if s["cell_id"] == identifier)["stage22_proposals"].append(
                {"record_id": str(record.record_id), "case_id": case["case_id"], "revisit": False})
        row.update(status="integrity_valid", records=len(candidates.records), bound_cells=ids, coverage=reply.coverage,
                   missing_targets=[t["cell_id"] for t in case["targets"] if t["cell_id"] not in ids],
                   readiness=[assess_readiness(r).to_dict() for r in candidates.records],
                   scientific_acceptance="not_established", scientific_exhaustiveness="not_established")
    except (HTTPError, URLError, TimeoutError, ValueError, FileNotFoundError) as exc:
        if isinstance(exc, HTTPError):
            (directory / "http_error_redacted.bin").write_bytes(exc.read().replace(api_key.encode(), b"<redacted>"))
        row.update(status="failed", stage=stage, error_type=type(exc).__name__, error=str(exc).replace(api_key, "<redacted>"))
    row.update(elapsed_seconds=round(time.perf_counter() - started, 3), completed_at=datetime.now(UTC).isoformat())
    write_json(directory / "result.json", row)
    return row


def run_remaining(prepared: Path, output: Path, *, api_key: str) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(output)
    if not api_key.strip():
        raise ValueError("Configured OpenAI credential unavailable; no model call")
    plan, ledger, pages, bindings = load_remaining(prepared)
    output.mkdir(parents=True, exist_ok=False)
    rows: list[dict[str, Any]] = []
    stopped = None
    for case in plan["cases"]:
        if stopped:
            row = {**case, "status": "unattempted", "model_calls": 0, "usage": None, "stop_reason": stopped}
        else:
            row = attempt_case(case, prepared, output, ledger, pages, bindings, api_key)
            if row["status"] == "failed":
                stopped = f'{case["case_id"]}: {row["stage"]}: {row["error_type"]}'
        rows.append(row)
        for target in case["targets"]:
            outcome = "proposed" if target["cell_id"] in row.get("bound_cells", []) else (
                "omitted_or_abstained" if row["status"] == "integrity_valid" else row["status"])
            next(s for s in ledger["slots"] if s["cell_id"] == target["cell_id"])["stage22_outcomes"].append(
                {"case_id": case["case_id"], "outcome": outcome})
    integrity: dict[str, Any] = {"status": "verified"}
    try:
        verify_hashes(bindings)
    except (ValueError, FileNotFoundError) as exc:
        integrity = {"status": "failed", "error_type": type(exc).__name__, "error": str(exc)}
    ledger["stage22_summary"] = accounting(ledger)
    report = {"version": VERSION, "cases": rows, "final_source_integrity": integrity,
              "prepared_manifest_sha256": bindings[str((prepared / "manifest.json").resolve())],
              "summary": {"declared_cases": len(rows), "model_calls": sum(r["model_calls"] for r in rows),
                          "integrity_valid": sum(r["status"] == "integrity_valid" for r in rows),
                          "failed": sum(r["status"] == "failed" for r in rows),
                          "unattempted": sum(r["status"] == "unattempted" for r in rows),
                          "proposed_records": sum(r.get("records", 0) for r in rows),
                          "source_accounting": ledger["stage22_summary"], "scientific_precision": None, "scientific_recall": None}}
    write_json(output / "report.json", report)
    write_json(output / "ledger.json", ledger)
    review = (render_smoke(report, output, prepared) if integrity["status"] == "verified" else
              '<!doctype html><meta charset="utf-8"><h1>Source integrity failed</h1><pre>'
              + html.escape(json.dumps(report, ensure_ascii=False, indent=2)) + '</pre>')
    (output / "review.html").write_text(review, encoding="utf-8")
    # Explicit display projection: persisted parent version/summary remain unchanged.
    display = {**ledger, "version": VERSION, "summary": ledger["stage22_summary"]}
    (output / "ledger.html").write_text(render_ledger(display), encoding="utf-8")
    write_json(output / "manifest.json", {"version": VERSION, "prepared_manifest_sha256": report["prepared_manifest_sha256"],
                                           "artifacts": {p.relative_to(output).as_posix(): file_hash(p)
                                                         for p in sorted(output.rglob("*")) if p.is_file()}})
    return report
