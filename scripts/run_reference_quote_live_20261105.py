"""Exactly two approved frozen requests, one attempt each. No retry/continuation."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

from scripts import gigachat_answer_smoke as files
from scripts.prepare_benchmark_inputs_20261103 import GoldReadGuard, load_cases
from scripts.verify_reference_quote_runtime_20261105 import mypy_name_only_binding

ROOT = files.ROOT
BASE = ROOT / "output/reference_quote_live_20261105"
PREPARED = ROOT / "output/reference_quote_runtime_20261105/fresh_v01"
SCOPE = ROOT / "docs/records/reference_quote_live_scope_2026-11-05_v0.1.md"
APPROVAL = BASE / "approval_v01.json"
TESTS = ROOT / "tests/unit/test_reference_quote_live_20261105.py"
IDS = ("Q01", "Q05")
REQUESTS = {"Q01": "821446de48ea4256d654923a4679eb3ed2cfa60ada9d97bfb1606139c14fc2eb",
            "Q05": "f264b28d85dbbad9800811149dc44deb38e781b45bb748a603b4a34c4c218d63"}
SIZES = {"Q01": 5258, "Q05": 6533}
VERSION = "reference_quote_live_v0.1"


def read(path: Path) -> Any:
    return json.loads(path.read_bytes())


def validate_approval(value: dict[str, Any]) -> None:
    required = {"case_ids": list(IDS), "request_sha256": REQUESTS, "maximum_model_attempts": 2,
                "maximum_oauth_attempts": 2, "model": "GigaChat-2-Max", "max_output_tokens": 1200,
                "per_http_timeout_seconds": 120, "automatic_retries": 0, "fallbacks": 0,
                "infrastructure_continuations": 0, "raw_user_approval": "Давай, да"}
    if any(value.get(key) != expected for key, expected in required.items()):
        raise ValueError("Approval differs from the two frozen requests and limits")


def verify_original(case_id: str) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    folder = PREPARED / case_id
    files.verify_manifest(folder)
    contract, api = read(folder / "contract.json"), read(folder / "api_request.json")
    case = next(c for c in load_cases() if c["id"] == case_id)
    if contract["case"] != case or api["question"] != case["question"]:
        raise ValueError("Frozen question identity differs")
    if (not contract["generation_reached"] or contract["preparation_status"] != "prepared_unsent_no_live_authorization"
            or contract["source_registry_diagnostics"] or contract["network_denials"] or contract["gold_read_denials"]
            or contract["transaction_read_only"] != "on" or contract["transaction_end"] != "rollback"):
        raise ValueError("Original preparation is not ready/read-only/question-only")
    if any(contract[key] != 0 for key in ("model_calls", "oauth_calls", "new_slots", "maximum_model_attempts",
                                        "maximum_oauth_attempts", "automatic_retries", "fallbacks")):
        raise ValueError("Original zero-budget preparation changed")
    raw = (folder / "request.json").read_bytes()
    if files.sha(raw) != REQUESTS[case_id] or len(raw) != SIZES[case_id] or contract["request_sha256"] != REQUESTS[case_id]:
        raise ValueError("Frozen native bytes differ")
    native = json.loads(raw)
    if (native["model"], native["max_tokens"], contract["timeout_seconds"]) != ("GigaChat-2-Max", 1200, 120):
        raise ValueError("Frozen settings differ")
    mapped = []
    for name, digest in contract["input_bindings"].items():
        if files.sha(Path(name).read_bytes()) == digest:
            continue
        rename = mypy_name_only_binding(name, digest)
        if rename is not None:
            mapped.append(rename)
            continue
        snapshot = ROOT / "output/reference_quote_runtime_20261105/capture_driver_before_stdout_fix_v01.py"
        if (case_id == "Q01" and Path(name).name == "capture_reference_quote_runtime_20261105.py"
                and files.sha(snapshot.read_bytes()) == digest and snapshot.read_text(encoding="utf-8").replace(
                    "ensure_ascii=False", "ensure_ascii=True") == Path(name).read_text(encoding="utf-8")):
            mapped.append({"path": name, "original_sha256": digest, "current_sha256": files.sha(Path(name).read_bytes()),
                           "snapshot": str(snapshot), "change": "stdout_only_ensure_ascii"})
            continue
        raise ValueError("Unmapped preparation input drift: " + name)
    return contract, api, mapped


def run(case_id: str, policy: files.NetworkPolicy, *, authorized: bool) -> dict[str, Any]:
    if not authorized:
        raise PermissionError("Explicit two-request approval required before operations")
    if case_id not in IDS:
        raise ValueError("Case outside two-request scope")
    validate_approval(read(APPROVAL))
    if case_id == "Q05":
        previous = read(BASE / "Q01/live/result.json")
        if previous["status"] not in {"runtime_answered", "runtime_http_error", "provider_abstained", "gate_rejected"}:
            raise ValueError("Unknown/interrupted/internal failure stops batch")
    if (BASE / case_id).exists() or (files.LEDGER / REQUESTS[case_id]).exists() or (BASE / "scope_close_v01.json").exists():
        raise FileExistsError("Existing slot/output/closure: no repeat allowed")
    contract, _, mapped = verify_original(case_id)
    files.configure()
    output = BASE / case_id
    approved = output / "authorized_inputs"
    approved.mkdir(parents=True, exist_ok=False)
    folder = PREPARED / case_id
    for path in folder.iterdir():
        if path.is_file() and path.name not in {"contract.json", "manifest.json"}:
            shutil.copyfile(path, approved / path.name)
    # Explicit current binding amendment, retaining the complete original contract.
    current = files.bindings([Path(name) for name in contract["input_bindings"]])
    derived = {**contract, "authorization": "explicit_user_Q01_Q05_2026-11-05", "maximum_model_attempts": 1,
        "maximum_oauth_attempts": 1, "question": contract["case"]["question"], "original_preparation": str(folder),
        "original_contract_sha256": files.sha((folder / "contract.json").read_bytes()), "mapped_input_drifts": mapped,
        "input_bindings": {**current, **files.bindings([*folder.iterdir(), APPROVAL, SCOPE, Path(__file__), TESTS])}}
    files.write(approved / "contract.json", derived)
    files.manifest(approved)
    with patch.object(files, "VERSION", VERSION), patch.object(files, "QUESTION", derived["question"]), \
            patch.object(files, "PROTOCOL", SCOPE):
        result = files.send(approved, output / "live", policy)
    return {"id": case_id, **{key: result.get(key) for key in ("status", "http_status", "model_attempts", "oauth_attempts", "usage")}}


def guard() -> GoldReadGuard:
    result = GoldReadGuard()
    result.allowed.add(SCOPE.resolve())
    result.allowed.add((ROOT / "docs/records/reference_quote_runtime_protocol_2026-11-05_v0.2.md").resolve())
    # The input drift verifier reads code snapshots only; exclude whole review
    # packets and their gold/post-hoc annotations from inference workers.
    root = ROOT / "output/reference_quote_runtime_20261105"
    result.allowed.add((root / "review_v02/source_snapshot/app/generation/reference_quotes.py").resolve())
    result.blocked_roots += tuple(root / name for name in ("review_v01", "review_v02", "review_final_v01", "review_final_v02"))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-id", choices=IDS, required=True)
    parser.add_argument("--authorize-two-frozen-requests", action="store_true")
    args = parser.parse_args()
    policy, reference_guard = files.NetworkPolicy(), guard()
    sys.addaudithook(policy)
    sys.addaudithook(reference_guard)
    result = run(args.case_id, policy, authorized=args.authorize_two_frozen_requests)
    if reference_guard.denied:
        raise ValueError("Forbidden reference read attempted")
    print(json.dumps(result, ensure_ascii=True), flush=True)


if __name__ == "__main__":
    main()
