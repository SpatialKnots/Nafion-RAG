"""Frozen targeted table continuation with immutable old proposals and source-cell accounting."""

from __future__ import annotations

import html
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError

from app.evaluation.context_compaction import SourcePage, require_no_complete_pages
from app.records.checks import check_bundle
from app.records.extraction import write_json
from app.records.multi import build_multi_messages, parse_multi_reply, resolve_multi_reply
from app.records.multi_html import render_smoke
from app.records.multi_run import (
    CODE,
    MAX_OUTPUT_TOKENS,
    MAX_REQUEST_BYTES,
    MODEL,
    TIMEOUT_SECONDS,
    _load_prepared,
    _safe,
    build_multi_request,
    verify_hashes,
)
from app.records.openai_backend import ENDPOINT, responses_content, send_openai_request
from app.records.readiness import assess_readiness
from app.records.schema import CandidateBundle, SourceRegion, source_identity, text_hash
from app.records.sources import file_hash
from app.records.table_cells import bind_reply, build_cell_ledger, token_address

VERSION = "records_table_continuation_v0.1"
CASE_IDS = ("remaining_01", "remaining_02", "remaining_03", "method_revisit")
NEW_CODE = ("app/records/table_cells.py", "app/records/table_continuation.py", "scripts/records_table_continue.py",
            "tests/unit/test_record_table_continuation.py", "docs/records/table_continuation_protocol_v0.1.md")


def build_request(bundle: CandidateBundle, targets: list[dict[str, Any]]) -> dict[str, Any]:
    task = (
        "Propose ONLY the explicitly targeted conductivity source cells, each at most once. All other cells are outside "
        "this task, not negative results. Target sample and column token addresses identify cells, not reference answers. "
        "Keep the complete protected table, footnotes, author wording and source order. R2 is a separately selected complete "
        "PDF text block from the SAME article's methods, with a right-boundary sentence continuation NOT INCLUDED. "
        "Do not infer omitted text. If proposing a method, select its exact R2 span and include BOTH R1 and R2 source "
        "evidence in conditions_measurement. This is a proposed cross-region association, never scientific confirmation. "
        "Missing method stays explicitly missing. Keep all sixteen fields. Do not select blank, dash or shared-row values. "
        "Sample label must select its exact row numeral, temperature the full printed column temperature, "
        "unit the complete printed unit, value the complete printed cell. No conversions or numeric rewriting. "
        "Coverage refers ONLY to targets. Missing or unsupported targets must retain exact unresolved source evidence. "
        "Targets: " + json.dumps(targets, ensure_ascii=False, sort_keys=True)
    )
    request = build_multi_request(bundle)
    request["input"] = build_multi_messages(bundle, task)
    old = "Select source token spans for ALL supported conductivity observations in the supplied context, up to FOUR proposals."
    if old not in request["input"][0]["content"]:
        raise ValueError("Frozen parent prompt changed")
    request["input"][0]["content"] = request["input"][0]["content"].replace(
        old, "Select source token spans ONLY for the task's declared target cells, up to FOUR proposals.")
    return request


def guard_request(request: dict[str, Any], bundle: CandidateBundle, targets: list[dict[str, Any]], pages: list[SourcePage]) -> None:
    if request != build_request(bundle, targets):
        raise ValueError("Continuation request differs from frozen source/targets/settings")
    if len(bundle.regions) != 2 or bundle.regions[0].article_id != bundle.regions[1].article_id:
        raise ValueError("Continuation requires table and same-article method regions")
    user = json.loads(request["input"][1]["content"])
    require_no_complete_pages("\n".join([user["task"], *[r["source"] for r in user["context"]]]), pages)
    require_no_complete_pages(request["input"][1]["content"], pages)
    if len(json.dumps(request, ensure_ascii=False).encode("utf-8")) > MAX_REQUEST_BYTES:
        raise ValueError("Continuation request exceeds frozen byte ceiling; no clipping")


def method_region(page: dict[str, Any], table: SourceRegion) -> tuple[SourceRegion, dict[str, Any]]:
    if page["article_id"] != str(table.article_id) or not page["source_gaps"]["text_geometry_proven"]:
        raise ValueError("Method source is foreign or geometry-unproven")
    blocks = [b for b in page["mapping"]["blocks"] if page["page_text"][b["page_start"]:b["page_end"]].startswith(
        "Электропроводность измеряли в поперечном")]
    if len(blocks) != 1:
        raise ValueError("Method block not uniquely identified")
    block = blocks[0]
    if any(block["block_number"] in g["block_numbers"] for g in page["protected_groups"]):
        raise ValueError("Selected method block intersects a protected group")
    data = table.model_dump(mode="json")
    start, end = block["page_start"], block["page_end"]
    data.update(page_number=page["page_number"], text_layer_id=page["text_layer_id"], text_layer=page["text_layer"],
                original_pdf_path=page["original_pdf_path"], original_pdf_sha256=page["original_pdf_sha256"],
                layer_pdf_path=page["selected_pdf_path"], layer_pdf_sha256=page["selected_pdf_sha256"],
                page_text=page["page_text"], page_text_sha256=page["page_text_sha256"], start=start, end=end,
                quote=page["page_text"][start:end], quote_sha256=text_hash(page["page_text"][start:end]),
                selection_basis="manual_development", selection_note="Stage21 complete method block; sentence continues outside context.")
    data["region_id"] = source_identity(data)
    region = SourceRegion.model_validate(data)
    if (region.original_pdf_sha256 != table.original_pdf_sha256 or region.original_pdf_path != table.original_pdf_path):
        raise ValueError("Method PDF differs from table PDF")
    return region, {"block": block, "selection": "new_development_block_not_deferred_page_activation",
                    "paragraph_completeness": "incomplete_sentence_at_right_boundary",
                    "source_order": "following_registered_blocks_contain_formula_fragments_before_prose_continuation",
                    "layout_diagnostics": page["layout_diagnostics"], "page_diagnostics": page["diagnostics"]}


def prepare_continuation(previous: Path, windows: Path, output: Path, *, source_root: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(output)
    previous, windows = previous.resolve(), windows.resolve()
    _, pages, inputs = _load_prepared(previous.parent / "prepared_v01")
    prior_manifest = previous / "manifest.json"
    parent = json.loads(prior_manifest.read_bytes())
    inputs[str(prior_manifest)] = file_hash(prior_manifest)
    inputs.update({str(_safe(previous, name)): expected for name, expected in parent["artifacts"].items()})
    code = {str((source_root / name).resolve()): file_hash(source_root / name) for name in (*CODE, *NEW_CODE)}
    report_path = windows / "report.json"
    if str(report_path) not in inputs:
        raise ValueError("Window report was not bound by parent preparation")
    verify_hashes(inputs | code)
    old_bundle = CandidateBundle.model_validate_json((previous / "kayumov_table/input.json").read_bytes())
    old_reply = parse_multi_reply((previous / "kayumov_table/reply.json").read_text(encoding="utf-8"))
    old_candidates = CandidateBundle.model_validate_json((previous / "kayumov_table/candidates.json").read_bytes())
    replay, _ = resolve_multi_reply(old_bundle, old_reply)
    if replay.records != old_candidates.records or replay.regions != old_candidates.regions:
        raise ValueError("Previous table proposals differ from raw replay")
    window_report = json.loads(report_path.read_bytes())
    table = old_bundle.regions[0]
    page = next(p for p in window_report["pages"] if p["article_id"] == str(table.article_id) and p["page_number"] == table.page_number)
    ledger = build_cell_ledger(page, table)
    old_ids = bind_reply(old_bundle, old_reply, ledger)
    for cell_id, record in zip(old_ids, old_candidates.records, strict=True):
        next(s for s in ledger["slots"] if s["cell_id"] == cell_id)["previous_proposals"].append(str(record.record_id))
    method_page = next(p for p in window_report["pages"] if p["article_id"] == str(table.article_id) and p["page_number"] == 3)
    method, diagnostic = method_region(method_page, table)
    bundle = old_bundle.model_copy(update={"producer": VERSION, "regions": (table, method)})
    remaining = [s for s in ledger["slots"] if s["source_state"] == "numeric_source_proposal" and not s["previous_proposals"]]
    if len(remaining) < 9 or not old_ids:
        raise ValueError("Insufficient unproposed numeric cells or previous proposals for declared plan")
    selections = [remaining[i:i + 3] for i in (0, 3, 6)] + [[next(s for s in ledger["slots"] if s["cell_id"] == old_ids[0])]]
    cases: list[dict[str, Any]] = []
    payloads = []
    for case_id, selected in zip(CASE_IDS, selections, strict=True):
        targets = [{"cell_id": s["cell_id"], "sample": token_address(table, s["sample"]["start"], s["sample"]["end"]),
                    "column": token_address(table, s["header"]["start"], s["header"]["end"])} for s in selected]
        request = build_request(bundle, targets)
        guard_request(request, bundle, targets, pages)
        cases.append({"case_id": case_id, "input": f"{case_id}/input.json", "request": f"{case_id}/request.json",
                      "targets": targets, "revisit": case_id == "method_revisit"})
        payloads.append(json.dumps(request, ensure_ascii=False).encode("utf-8"))
    output.mkdir(parents=True, exist_ok=False)
    for case, payload in zip(cases, payloads, strict=True):
        (output / case["case_id"]).mkdir()
        write_json(output / case["input"], bundle.model_dump(mode="json"))
        (output / case["request"]).write_bytes(payload)
    write_json(output / "ledger.json", ledger)
    write_json(output / "method_source.json", diagnostic)
    write_json(output / "page_registry.json", [vars(page) for page in pages])
    write_json(output / "plan.json", {"version": VERSION, "cases": cases, "endpoint": ENDPOINT, "model": MODEL,
                                      "maximum_calls": 4, "max_output_tokens_per_call": MAX_OUTPUT_TOKENS,
                                      "maximum_output_tokens_all_calls": 4 * MAX_OUTPUT_TOKENS, "timeout_seconds": TIMEOUT_SECONDS})
    verify_hashes(inputs | code)
    write_json(output / "manifest.json", {"version": VERSION, "inputs": inputs, "code": code,
                                           "artifacts": {p.relative_to(output).as_posix(): file_hash(p)
                                                         for p in sorted(output.rglob("*")) if p.is_file()}})
    return {"version": VERSION, "cases": len(cases), "source_accounting": ledger["summary"],
            "previous_cells": len(old_ids), "new_targets": 9, "revisit_targets": 1, "new_model_calls": 0}


def load_prepared(prepared: Path) -> tuple[dict[str, Any], dict[str, Any], list[SourcePage], dict[str, str]]:
    manifest_path = prepared / "manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    if manifest["version"] != VERSION:
        raise ValueError("Unexpected continuation version")
    bindings = manifest["inputs"] | manifest["code"] | {str(manifest_path.resolve()): file_hash(manifest_path)}
    bindings.update({str(_safe(prepared, name)): expected for name, expected in manifest["artifacts"].items()})
    verify_hashes(bindings)
    plan = json.loads((prepared / "plan.json").read_bytes())
    if ([c["case_id"] for c in plan["cases"]] != list(CASE_IDS) or plan["model"] != MODEL or plan["endpoint"] != ENDPOINT
            or plan["maximum_calls"] != 4 or plan["max_output_tokens_per_call"] != MAX_OUTPUT_TOKENS
            or plan["maximum_output_tokens_all_calls"] != 4 * MAX_OUTPUT_TOKENS or plan["timeout_seconds"] != TIMEOUT_SECONDS):
        raise ValueError("Frozen continuation plan/settings changed")
    ledger = json.loads((prepared / "ledger.json").read_bytes())
    pages = [SourcePage(**p) for p in json.loads((prepared / "page_registry.json").read_bytes())]
    return plan, ledger, pages, bindings


def render_ledger(ledger: dict[str, Any]) -> str:
    rows = []
    for cell in ledger["slots"]:
        value = cell["value"]["text"] if cell["value"] else "unresolved"
        rows.append('<tr class="slot"><td>' + str(cell["row"]) + '</td><td>' + html.escape(cell["header"]["text"])
                    + '</td><td>' + html.escape(value) + '</td><td>' + html.escape(cell["source_state"])
                    + '</td><td><details><summary>Proposals / exact source</summary><pre>'
                    + html.escape(json.dumps(cell, ensure_ascii=False, indent=2)) + '</pre></details></td></tr>')
    return ('<!doctype html><meta charset="utf-8"><title>ARIADNE table source ledger</title>'
            '<style>body{font:15px system-ui;margin:24px}td,th{border:1px solid #ccc;padding:8px}'
            'table{border-collapse:collapse}pre{white-space:pre-wrap}[hidden]{display:none}</style>'
            '<h1>Table source-cell proposals</h1><p>Source accounting, not scientific acceptance or independent experiments. '
            'Shared cells unresolved. Revisit proposals do not add a new covered cell.</p><a href="'
            + html.escape(Path(ledger["original_pdf_path"]).resolve().as_uri(), quote=True)
            + f'#page={ledger["page"]}">Original PDF</a> · <a href="review.html">All inference cases / raw diagnostics</a>'
            + '<pre>' + html.escape(json.dumps({"version": ledger["version"], "summary": ledger["summary"]}, indent=2))
            + '</pre><label>Search <input id="q" type="search"></label><table><thead><tr><th>Sample</th><th>Column</th>'
            '<th>Literal value</th><th>Source state</th><th>Evidence and proposals</th></tr></thead><tbody>'
            + ''.join(rows) + '</tbody></table><script>document.getElementById("q").oninput=e=>{'
            'for(const r of document.querySelectorAll("tr.slot"))r.hidden=!r.textContent.toLocaleLowerCase()'
            '.includes(e.target.value.toLocaleLowerCase());};</script>\n')


def run_continuation(prepared: Path, output: Path, *, api_key: str) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(output)
    if not api_key.strip():
        raise ValueError("Configured OpenAI credential unavailable; no model call")
    plan, ledger, pages, bindings = load_prepared(prepared)
    output.mkdir(parents=True, exist_ok=False)
    for cell in ledger["slots"]:
        cell.update(new_proposals=[], continuation_outcomes=[])
    rows: list[dict[str, Any]] = []
    stopped = None
    for case in plan["cases"]:
        row: dict[str, Any] = {**case, "status": "unattempted", "model_calls": 0, "usage": None}
        rows.append(row)
        if stopped:
            row["stop_reason"] = stopped
            continue
        directory = output / case["case_id"]
        directory.mkdir()
        started, stage = time.perf_counter(), "frozen_binding"
        try:
            verify_hashes(bindings)
            raw = _safe(prepared, case["input"]).read_bytes()
            payload = _safe(prepared, case["request"]).read_bytes()
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
                next(s for s in ledger["slots"] if s["cell_id"] == identifier)["new_proposals"].append(
                    {"record_id": str(record.record_id), "case_id": case["case_id"], "revisit": case["revisit"]})
            row.update(status="integrity_valid", records=len(candidates.records), bound_cells=ids, coverage=reply.coverage,
                       missing_targets=[t["cell_id"] for t in case["targets"] if t["cell_id"] not in ids],
                       readiness=[assess_readiness(r).to_dict() for r in candidates.records],
                       scientific_acceptance="not_established", scientific_exhaustiveness="not_established")
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            if isinstance(exc, HTTPError):
                (directory / "http_error_redacted.bin").write_bytes(exc.read().replace(api_key.encode(), b"<redacted>"))
            row.update(status="failed", stage=stage, error_type=type(exc).__name__, error=str(exc).replace(api_key, "<redacted>"))
            stopped = f'{case["case_id"]}: {stage}: {row["error_type"]}'
        row.update(elapsed_seconds=round(time.perf_counter() - started, 3), completed_at=datetime.now(UTC).isoformat())
        write_json(directory / "result.json", row)
    for row in rows:
        for target in row["targets"]:
            cell = next(s for s in ledger["slots"] if s["cell_id"] == target["cell_id"])
            outcome = "proposed" if target["cell_id"] in row.get("bound_cells", []) else (
                "omitted_or_abstained" if row["status"] == "integrity_valid" else row["status"])
            cell["continuation_outcomes"].append({"case_id": row["case_id"], "outcome": outcome})
    source_integrity: dict[str, Any] = {"status": "verified"}
    try:
        verify_hashes(bindings)
    except ValueError as exc:
        source_integrity = {"status": "failed", "error": str(exc)}
    ledger["summary"].update(previous_covered_cells=sum(bool(s["previous_proposals"]) for s in ledger["slots"]),
                             new_covered_cells=sum(bool(s["new_proposals"]) and not s["previous_proposals"] for s in ledger["slots"]),
                             combined_covered_cells=sum(bool(s["new_proposals"] or s["previous_proposals"]) for s in ledger["slots"]),
                             remaining_numeric_cells=sum(s["source_state"] == "numeric_source_proposal"
                                                         and not (s["new_proposals"] or s["previous_proposals"]) for s in ledger["slots"]))
    report = {"version": VERSION, "cases": rows, "final_source_integrity": source_integrity,
              "prepared_manifest_sha256": bindings[str((prepared / "manifest.json").resolve())],
              "summary": {"declared_cases": len(rows), "model_calls": sum(r["model_calls"] for r in rows),
                          "integrity_valid": sum(r["status"] == "integrity_valid" for r in rows),
                          "failed": sum(r["status"] == "failed" for r in rows),
                          "unattempted": sum(r["status"] == "unattempted" for r in rows),
                          "proposed_records": sum(r.get("records", 0) for r in rows),
                          "source_accounting": ledger["summary"], "scientific_precision": None, "scientific_recall": None}}
    write_json(output / "report.json", report)
    write_json(output / "ledger.json", ledger)
    review = (render_smoke(report, output, prepared) if source_integrity["status"] == "verified" else
              '<!doctype html><meta charset="utf-8"><h1>Source integrity failed</h1>'
              '<p>Source preview withheld because frozen inputs changed. Full diagnostics follow.</p><pre>'
              + html.escape(json.dumps(report, ensure_ascii=False, indent=2)) + '</pre>')
    (output / "review.html").write_text(review, encoding="utf-8")
    (output / "ledger.html").write_text(render_ledger(ledger), encoding="utf-8")
    write_json(output / "manifest.json", {"version": VERSION, "prepared_manifest_sha256": report["prepared_manifest_sha256"],
                                           "artifacts": {p.relative_to(output).as_posix(): file_hash(p)
                                                         for p in sorted(output.rglob("*")) if p.is_file()}})
    return report
