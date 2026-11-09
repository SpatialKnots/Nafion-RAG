"""New bounded five-case test; immutable question-only preparation and one send each."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from scripts import capture_reference_quote_runtime_20261105 as capture
from scripts import gigachat_answer_smoke as files
from scripts.prepare_benchmark_inputs_20261103 import GoldReadGuard, load_cases

ROOT = files.ROOT
BASE = ROOT / "output/user_benchmark_retest_20261105"
SCOPE = ROOT / "docs/records/user_benchmark_retest_scope_2026-11-05_v0.1.md"
APPROVAL = BASE / "approval_v01.json"
TESTS = ROOT / "tests/unit/test_user_benchmark_retest_20261105.py"
IDS = tuple(f"Q{i:02d}" for i in range(1, 6))
KNOWN = {"runtime_answered", "runtime_http_error", "provider_abstained", "gate_rejected"}
VERSION = "user_benchmark_retest_20261105_v0.1"


def read(path):
    return json.loads(path.read_bytes())


def validate_approval(value, requests):
    required = {"case_ids": list(IDS), "request_sha256": requests, "maximum_model_attempts": 5,
                "maximum_oauth_attempts": 5, "model": "GigaChat-2-Max", "max_output_tokens": 1200,
                "per_http_timeout_seconds": 120, "automatic_retries": 0, "fallbacks": 0,
                "infrastructure_continuations": 0, "raw_user_approval": "Го новый тест"}
    if any(value.get(key) != expected for key, expected in required.items()):
        raise ValueError("Approval differs from new five-case scope")


def preparations():
    cases = load_cases()
    result = {}
    for case in cases:
        folder = BASE / "prepared_v01" / case["id"]
        files.verify_manifest(folder)
        contract = read(folder / "contract.json")
        files.verify(contract["input_bindings"])
        raw = (folder / "request.json").read_bytes()
        native = json.loads(raw)
        if (contract["case"] != case or read(folder / "api_request.json")["question"] != case["question"]
                or not contract["generation_reached"] or contract["request_sha256"] != files.sha(raw)
                or contract["request_bytes"] != len(raw) or len(raw) > 100000
                or contract["transaction_read_only"] != "on" or contract["transaction_end"] != "rollback"
                or contract["network_denials"] or contract["gold_read_denials"] or contract["source_registry_diagnostics"]
                or any(contract[k] != 0 for k in ("model_calls", "oauth_calls", "new_slots", "maximum_model_attempts",
                                                  "maximum_oauth_attempts", "automatic_retries", "fallbacks"))
                or (native["model"], native["max_tokens"], contract["timeout_seconds"]) != ("GigaChat-2-Max", 1200, 120)):
            raise ValueError("Preparation differs from frozen zero-budget question-only scope")
        result[case["id"]] = contract
    return result


def seal(*, authorized):
    if not authorized:
        raise PermissionError("New five-case user authorization required")
    contracts = preparations()
    value = {"case_ids": list(IDS), "request_sha256": {cid: c["request_sha256"] for cid, c in contracts.items()},
             "maximum_model_attempts": 5, "maximum_oauth_attempts": 5, "model": "GigaChat-2-Max",
             "max_output_tokens": 1200, "per_http_timeout_seconds": 120, "automatic_retries": 0,
             "fallbacks": 0, "infrastructure_continuations": 0, "raw_user_approval": "Го новый тест",
             "recorded_at_utc": datetime.now(UTC).isoformat(), "scope_sha256": files.sha(SCOPE.read_bytes())}
    validate_approval(value, value["request_sha256"])
    if any((files.LEDGER / digest).exists() for digest in value["request_sha256"].values()):
        raise FileExistsError("Previously attempted native body: do not reuse closed slot")
    files.write(APPROVAL, value)
    return value


def run(case_id, policy, *, authorized):
    if not authorized:
        raise PermissionError("New five-case user authorization required before reads")
    if case_id not in IDS:
        raise ValueError("Case outside scope")
    if (BASE / "scope_close_v01.json").exists() or (BASE / case_id).exists():
        raise FileExistsError("Existing output/closed scope: no repeat")
    for previous in IDS[:IDS.index(case_id)]:
        if read(BASE / previous / "live/result.json")["status"] not in KNOWN:
            raise ValueError("Unknown/interrupted/internal failure stops batch")
    contracts = preparations()
    approval = read(APPROVAL)
    validate_approval(approval, {cid: c["request_sha256"] for cid, c in contracts.items()})
    if approval["scope_sha256"] != files.sha(SCOPE.read_bytes()):
        raise ValueError("Scope changed after sealing")
    original = BASE / "prepared_v01" / case_id
    approved = BASE / case_id / "authorized_inputs"
    if (files.LEDGER / contracts[case_id]["request_sha256"]).exists():
        raise FileExistsError("Existing request slot: no repeat")
    approved.mkdir(parents=True, exist_ok=False)
    for path in original.iterdir():
        if path.is_file() and path.name not in {"manifest.json", "contract.json"}:
            shutil.copyfile(path, approved / path.name)
    contract = {**contracts[case_id], "authorization": "explicit_user_Go_new_test_five_cases_2026-11-05",
                "maximum_model_attempts": 1, "maximum_oauth_attempts": 1,
                "question": contracts[case_id]["case"]["question"], "original_preparation": str(original),
                "input_bindings": {**contracts[case_id]["input_bindings"],
                    **files.bindings([*original.iterdir(), APPROVAL, SCOPE, Path(__file__), TESTS])}}
    files.write(approved / "contract.json", contract)
    files.manifest(approved)
    with patch.object(files, "QUESTION", contract["question"]), patch.object(files, "PROTOCOL", SCOPE), \
            patch.object(files, "VERSION", VERSION):
        result = files.send(approved, BASE / case_id / "live", policy)
    return {"id": case_id, **{k: result.get(k) for k in
            ("status", "http_status", "model_attempts", "oauth_attempts", "usage")}}


def close():
    approval = read(APPROVAL)
    rows = []
    for cid in IDS:
        path = BASE / cid / "live/result.json"
        result = read(path) if path.exists() else {}
        row = {"id": cid, "allowance_closed": True, "resend_authorized": False,
               "request_sha256": approval["request_sha256"][cid],
               "model_attempts": result.get("model_attempts", 0), "oauth_attempts": result.get("oauth_attempts", 0),
               "status": result.get("status", "not_dispatched")}
        slot = files.LEDGER / row["request_sha256"]
        if slot.exists():
            files.write(slot / "scope_closed_retest_20261105_v01.json", row)
        rows.append(row)
    value = {"cases": rows, "remaining_allowance": 0, "all_older_budgets_remain_closed": True,
             "total_model_attempts": sum(r["model_attempts"] for r in rows),
             "total_oauth_attempts": sum(r["oauth_attempts"] for r in rows), "automatic_retries": 0, "fallbacks": 0}
    files.write(BASE / "scope_close_v01.json", value)
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "seal", "send", "close"))
    parser.add_argument("--case-id", choices=IDS)
    parser.add_argument("--authorize-new-five-case-test", action="store_true")
    args = parser.parse_args()
    policy = files.NetworkPolicy()
    guard = GoldReadGuard()
    guard.allowed.add(SCOPE.resolve())
    guard.blocked_roots += tuple(ROOT / "output" / p for p in (
        "ascii_quote_selection_20261105", "user_benchmark_live_20261104", "reference_quote_live_20261105"))
    sys.addaudithook(policy)
    sys.addaudithook(guard)
    if args.mode == "prepare":
        if args.case_id is None:
            raise ValueError("Case required")
        with patch.object(capture, "PROTOCOL", SCOPE):
            value = capture.capture(args.case_id, BASE / "prepared_v01" / args.case_id, policy)
    elif args.mode == "seal":
        value = seal(authorized=args.authorize_new_five_case_test)
    elif args.mode == "send":
        value = run(args.case_id, policy, authorized=args.authorize_new_five_case_test)
    else:
        value = close()
    if guard.denied:
        raise ValueError("Forbidden gold/review access attempted")
    print(json.dumps(value, ensure_ascii=True, indent=2), flush=True)


if __name__ == "__main__":
    main()
