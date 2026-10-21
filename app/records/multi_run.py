"""Frozen multi-record smoke preparation, guarded live calls and raw-response replay."""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError

from app.evaluation.context_compaction import SourcePage, require_no_complete_pages
from app.records.checks import check_bundle
from app.records.extraction import write_json
from app.records.multi import VERSION, MultiReply, build_multi_messages, parse_multi_reply, resolve_multi_reply
from app.records.openai_backend import ENDPOINT, responses_content, send_openai_request
from app.records.readiness import assess_readiness
from app.records.schema import CandidateBundle
from app.records.sources import file_hash

CASES = (
    ("sanginov_abstract", "bb8ddb09defe9e75907352cddb97e7d0a8a3d76c60b7890b63f6fe24a61ccaeb"),
    ("istomina_prior_work", "b2f4442678f51b9c6339e798f9701c7fcf21c7847869cc46cf72fc5f92584fdf"),
    ("istomina_methods", "ba348bbe9ec470bce6f1e774781ea14ad3efefced206fb5898f25340163f5670"),
    ("kayumov_table", "9ce019ff311edf6345ce5abfe635c952b2743cd4db0f4eadf429a9a92875a446"),
)
TASK = (
    "Propose all supported conductivity observations in this exact development context, within the operational record budget. "
    "Preserve each author's property wording and own-work/cited-prior-work origin. "
    "Do not borrow present-article methods for prior-work results. Preserve distinct samples/temperatures, "
    "ranges, merged-cell ambiguity, footnote overrides and explicit missingness. "
    "Method-only or bibliography-only text without a supported measurement yields no measurement proposal. "
    "For insufficient source or budget, preserve exact unresolved spans and partial/unsupported coverage. "
    "Do not infer graph values, independent experimental identity or scientific acceptance."
)
MODEL = "gpt-6-astra"
MAX_OUTPUT_TOKENS = 8192
TIMEOUT_SECONDS = 180
MAX_REQUEST_BYTES = 100000
CODE = (
    "app/records/multi.py", "app/records/multi_run.py", "app/records/multi_html.py", "scripts/records_multi.py",
    "app/records/fixed_links.py", "app/records/spans.py", "app/records/schema.py", "app/records/extraction.py",
    "app/records/compact.py", "app/records/readiness.py", "app/records/checks.py", "app/records/review.py",
    "app/records/sources.py", "app/records/openai_backend.py", "app/records/article_windows.py",
    "app/evaluation/context_compaction.py", "app/generation/providers.py", "docs/records/multi_record_protocol_v0.1.md",
    "pyproject.toml",
)


def build_multi_request(bundle: CandidateBundle) -> dict[str, Any]:
    return {"model": MODEL, "input": build_multi_messages(bundle, TASK), "max_output_tokens": MAX_OUTPUT_TOKENS,
            "reasoning": {"effort": "medium"}, "store": False, "stream": False, "truncation": "disabled",
            "service_tier": "default", "text": {"format": {"type": "json_schema", "name": "ariadne_multi_fixed",
                                                              "strict": True, "schema": MultiReply.model_json_schema()}}}


def guard_request(request: dict[str, Any], bundle: CandidateBundle, pages: list[SourcePage]) -> None:
    expected = build_multi_request(bundle)
    if request != expected:
        raise ValueError("Prepared multi-record request differs from source/task/settings binding")
    user = json.loads(request["input"][1]["content"])
    require_no_complete_pages("\n".join([user["task"], *[r["source"] for r in user["context"]]]), pages)
    require_no_complete_pages(request["input"][1]["content"], pages)
    if len(json.dumps(request, ensure_ascii=False).encode("utf-8")) > MAX_REQUEST_BYTES:
        raise ValueError("Multi-record request exceeds frozen serialized-request ceiling; no clipping")


def verify_hashes(entries: dict[str, str]) -> None:
    for name, expected in entries.items():
        if file_hash(Path(name)) != expected:
            raise ValueError(f"Frozen multi-record input/source/code changed: {name}")


def _safe(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Frozen artifact path escapes its root")
    return path


def prepare_smoke(windows: Path, output_dir: Path, *, source_root: Path) -> dict[str, Any]:
    if output_dir.exists():
        raise FileExistsError(f"Multi-record preparation already exists: {output_dir}")
    windows = windows.resolve()
    parent_path = windows / "manifest.json"
    parent = json.loads(parent_path.read_bytes())
    if parent["version"] != "records_article_windows_v0.1":
        raise ValueError("Expected frozen stage19 window plan")
    inputs = {str(parent_path): file_hash(parent_path)}
    inputs.update(parent["inputs"])
    inputs.update({str((source_root / name).resolve()): expected for name, expected in parent["code"].items()})
    for name, expected in parent["outputs"].items():
        inputs[str(_safe(windows, name))] = expected
    code = {str((source_root / name).resolve()): file_hash(source_root / name) for name in CODE}
    verify_hashes(inputs | code)
    plan = json.loads((windows / "report.json").read_bytes())
    pages = [SourcePage(p["article_id"], p["parent_region_id"], p["page_number"], p["text_layer"], p["text_layer_id"],
                        p["page_text"], p["original_pdf_path"], p["original_pdf_sha256"])
             for p in plan["pages"] if p.get("page_text")]
    if len(pages) != plan["summary"]["pdf_pages"] or len(pages) != 62:
        raise ValueError("Declared smoke requires exactly the complete 62-page source registry")
    context_by_id = {c["context_id"]: (p, c) for p in plan["pages"] for c in p["contexts"]}
    prepared = []
    payloads = []
    for case_id, identifier in CASES:
        page, context = context_by_id[identifier]
        if context["state"] != "bounded_context_proposal":
            raise ValueError(f"Frozen smoke context is no longer bounded: {case_id}")
        path = _safe(windows, context["bundle"])
        raw = path.read_bytes()
        bundle = CandidateBundle.model_validate_json(raw)
        if (len(bundle.regions) != 1 or bundle.regions[0].quote != context["quote"]
                or str(bundle.regions[0].article_id) != page["article_id"]):
            raise ValueError("Frozen context/bundle identity differs from source plan")
        request = build_multi_request(bundle)
        guard_request(request, bundle, pages)
        payload = json.dumps(request, ensure_ascii=False).encode("utf-8")
        prepared.append({"case_id": case_id, "context_id": identifier, "article_id": page["article_id"],
                         "page_number": page["page_number"], "input": f"{case_id}/input.json",
                         "request": f"{case_id}/request.json", "source_type": page["source_type"],
                         "scientific_adequacy": "not_established", "expected_records": None})
        payloads.append((case_id, raw, payload))
    output_dir.mkdir(parents=True, exist_ok=False)
    for case_id, raw, payload in payloads:
        case_dir = output_dir / case_id
        case_dir.mkdir()
        (case_dir / "input.json").write_bytes(raw)
        (case_dir / "request.json").write_bytes(payload)
    write_json(output_dir / "page_registry.json", [vars(page) for page in pages])
    write_json(output_dir / "plan.json", {"version": VERSION, "cases": prepared, "endpoint": ENDPOINT,
                                          "model": MODEL, "maximum_calls": 4, "max_output_tokens_per_call": MAX_OUTPUT_TOKENS,
                                          "maximum_output_tokens_all_calls": 4 * MAX_OUTPUT_TOKENS,
                                          "timeout_seconds": TIMEOUT_SECONDS, "scientific_acceptance": "not_established"})
    verify_hashes(inputs | code)
    manifest = {"version": VERSION, "inputs": inputs, "code": code,
                "artifacts": {p.relative_to(output_dir).as_posix(): file_hash(p)
                              for p in sorted(output_dir.rglob("*")) if p.is_file()}}
    write_json(output_dir / "manifest.json", manifest)
    return {"prepared_cases": len(prepared), "verified_source_pages": len(pages), "maximum_calls": 4,
            "maximum_output_tokens_all_calls": 4 * MAX_OUTPUT_TOKENS, "new_model_calls": 0}


def _load_prepared(prepared: Path) -> tuple[dict[str, Any], list[SourcePage], dict[str, str]]:
    manifest_path = prepared / "manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    if manifest["version"] != VERSION:
        raise ValueError("Unsupported frozen multi-record preparation")
    bindings = manifest["inputs"] | manifest["code"] | {str(manifest_path.resolve()): file_hash(manifest_path)}
    bindings.update({str(_safe(prepared, name)): expected for name, expected in manifest["artifacts"].items()})
    verify_hashes(bindings)
    plan = json.loads((prepared / "plan.json").read_bytes())
    if ([r["case_id"] for r in plan["cases"]] != [case for case, _ in CASES]
            or [r["context_id"] for r in plan["cases"]] != [identifier for _, identifier in CASES]
            or plan["maximum_calls"] != 4 or plan["model"] != MODEL or plan["timeout_seconds"] != TIMEOUT_SECONDS):
        raise ValueError("Frozen smoke plan order/settings differ from declared protocol")
    pages = [SourcePage(**row) for row in json.loads((prepared / "page_registry.json").read_bytes())]
    return plan, pages, bindings


def run_smoke(prepared: Path, output_dir: Path, *, api_key: str) -> dict[str, Any]:
    if output_dir.exists():
        raise FileExistsError(f"Multi-record run already exists: {output_dir}")
    if not api_key.strip():
        raise ValueError("Configured OpenAI credential unavailable; no model call")
    plan, pages, bindings = _load_prepared(prepared)
    output_dir.mkdir(parents=True, exist_ok=False)
    rows: list[dict[str, Any]] = []
    stopped: str | None = None
    for case in plan["cases"]:
        row: dict[str, Any] = {**case, "status": "unattempted", "model_calls": 0, "usage": None,
                               "scientific_acceptance": "not_established"}
        rows.append(row)
        if stopped is not None:
            row["stop_reason"] = stopped
            continue
        case_dir = output_dir / case["case_id"]
        case_dir.mkdir()
        stage = "frozen_binding"
        started = time.perf_counter()
        try:
            verify_hashes(bindings)
            raw_input = _safe(prepared, case["input"]).read_bytes()
            raw_request = _safe(prepared, case["request"]).read_bytes()
            bundle = CandidateBundle.model_validate_json(raw_input)
            guard_request(json.loads(raw_request), bundle, pages)
            if raw_request != json.dumps(build_multi_request(bundle), ensure_ascii=False).encode("utf-8"):
                raise ValueError("Actual request bytes differ from frozen request")
            (case_dir / "input.json").write_bytes(raw_input)
            (case_dir / "request.json").write_bytes(raw_request)
            stage = "transport"
            row["model_calls"] = 1
            response, request_id = send_openai_request(raw_request, api_key, TIMEOUT_SECONDS)
            (case_dir / "response.json").write_bytes(response)
            stage = "completion_contract"
            envelope = json.loads(response)
            if isinstance(envelope, dict):
                row.update(request_id=request_id, response_id=envelope.get("id"), returned_model=envelope.get("model"),
                           response_status=envelope.get("status"), usage=envelope.get("usage"),
                           incomplete_details=envelope.get("incomplete_details"))
            reply = parse_multi_reply(responses_content(response))
            write_json(case_dir / "reply.json", reply.model_dump(mode="json"))
            stage = "evidence_integrity"
            resolved, unresolved = resolve_multi_reply(bundle, reply)
            stage = "source_postflight"
            verify_hashes(bindings)
            write_json(case_dir / "candidates.json", resolved.model_dump(mode="json"))
            write_json(case_dir / "unresolved.json", unresolved)
            checks = check_bundle(resolved)
            write_json(case_dir / "checks.json", [check.model_dump(mode="json") for check in checks])
            row.update(status="integrity_valid", records=len(resolved.records), coverage=reply.coverage,
                       unresolved_cases=len(unresolved), readiness=[assess_readiness(record).to_dict() for record in resolved.records],
                       scientific_exhaustiveness="not_established_from_model_coverage_claim")
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            if isinstance(exc, HTTPError):
                (case_dir / "http_error_body_redacted.bin").write_bytes(exc.read().replace(api_key.encode(), b"<redacted>"))
                row["http_status"] = exc.code
            row.update(status="failed", stage=stage, error_type=type(exc).__name__, error=str(exc).replace(api_key, "<redacted>"))
            stopped = f'{case["case_id"]}: {stage}: {row["error_type"]}'
        row.update(elapsed_seconds=round(time.perf_counter() - started, 3), completed_at=datetime.now(UTC).isoformat())
        write_json(case_dir / "result.json", row)
    final_source_integrity: dict[str, Any] = {"status": "verified"}
    try:
        verify_hashes(bindings)
    except ValueError as exc:
        final_source_integrity = {"status": "failed", "error": str(exc)}
    report = {"version": VERSION, "prepared_manifest_sha256": bindings[str((prepared / "manifest.json").resolve())],
              "cases": rows, "final_source_integrity": final_source_integrity,
              "summary": {"declared_cases": len(rows), "model_calls": sum(r["model_calls"] for r in rows),
                          "integrity_valid": sum(r["status"] == "integrity_valid" for r in rows),
                          "failed": sum(r["status"] == "failed" for r in rows),
                          "unattempted": sum(r["status"] == "unattempted" for r in rows),
                          "proposed_records": sum(r.get("records", 0) for r in rows),
                          "scientific_precision": None, "scientific_recall": None, "human_time_savings": None}}
    write_json(output_dir / "report.json", report)
    from app.records.multi_html import render_smoke

    (output_dir / "review.html").write_text(render_smoke(report, output_dir, prepared), encoding="utf-8")
    write_json(output_dir / "manifest.json", {"version": VERSION, "prepared_manifest_sha256": report["prepared_manifest_sha256"],
                                               "artifacts": {p.relative_to(output_dir).as_posix(): file_hash(p)
                                                             for p in sorted(output_dir.rglob("*")) if p.is_file()}})
    return report
