"""One approved attempt per frozen question; immutable preparation and no retries."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

from scripts import gigachat_answer_smoke as files
from scripts import prepare_benchmark_inputs_20261103 as prep
from scripts import review_benchmark_inputs_20261103 as frozen

ROOT = prep.ROOT
BASE = ROOT / "output/user_benchmark_live_20261104"
SCOPE = ROOT / "docs/records/user_benchmark_live_scope_2026-11-04_v0.1.md"
APPROVAL = BASE / "approval_v01.json"
TESTS = ROOT / "tests/unit/test_user_benchmark_live_20261104.py"
VERSION = "user_benchmark_live_v0.1"
IDS = tuple(f"Q{i:02d}" for i in range(1, 6))


def validate_approval(value: dict[str, Any], requests: dict[str, str]) -> None:
    required = {"case_ids": list(IDS), "request_sha256": requests,
                "maximum_model_attempts": 5, "maximum_oauth_attempts": 5,
                "model": "GigaChat-2-Max", "max_output_tokens": 1200,
                "per_http_timeout_seconds": 120, "automatic_retries": 0, "fallbacks": 0}
    if any(value.get(k) != v for k, v in required.items()) or not value.get("raw_user_approval"):
        raise ValueError("Approval differs from the five frozen requests and limits")


def read_scope() -> tuple[dict[str, Any], dict[str, Path]]:
    review = prep.BASE / "review_v01"
    bundle = prep.BASE / "inputs_v01"
    files.verify_manifest(review)
    files.verify_manifest(bundle)
    report = frozen.read(review / "report.json")
    files.verify(report["bindings"])
    files.verify(frozen.read(bundle / "manifest.json")["parent_bindings"])
    cases = prep.load_cases()
    if [r["case"] for r in report["cases"]] != cases:
        raise ValueError("Frozen question-only identities differ")
    selected = frozen.read(frozen.SELECTION)["prepared"]
    if set(selected) != set(IDS):
        raise ValueError("Prepared inventory differs")
    folders = {key: Path(value) for key, value in selected.items()}
    for row in report["cases"]:
        case, contract = row["case"], row["contract"]
        folder = folders[case["id"]]
        files.verify_manifest(folder)
        if frozen.read(folder / "contract.json") != contract:
            raise ValueError("Original preparation contract differs")
        files.verify(contract["input_bindings"])
        if (contract["version"] != prep.VERSION or not contract["generation_reached"]
                or contract["blocking_reasons"] or contract.get("infrastructure_continuation_of") is not None):
            raise ValueError("Expected ready original preparation without continuation")
        if any(contract[k] != 0 for k in ("maximum_model_attempts", "maximum_oauth_attempts",
                                          "new_model_calls", "new_oauth_calls", "new_slot_reservations")):
            raise ValueError("Original preparation is not zero-budget")
        raw = (folder / "request.json").read_bytes()
        frozen.verify_native(raw, contract, case["question"])
        if len(raw) > 100000 or raw != (bundle / (case["id"] + "_request.json")).read_bytes():
            raise ValueError("Frozen native body differs or exceeds review cap")
    validate_approval(frozen.read(APPROVAL), {r["case"]["id"]: r["contract"]["request_sha256"]
                                             for r in report["cases"]})
    return report, folders


def run(case_id: str, policy: files.NetworkPolicy, *, authorized: bool) -> dict[str, Any]:
    if not authorized:
        raise PermissionError("Explicit five-request user approval required before operations")
    if case_id not in IDS:
        raise ValueError("Case outside approved scope")
    report, folders = read_scope()
    row = next(r for r in report["cases"] if r["case"]["id"] == case_id)
    prepared, output = folders[case_id], BASE / case_id
    contract = row["contract"]
    # Require sequential dispatch; a missing/unknown preceding outcome is not permission to continue.
    for previous in IDS[:IDS.index(case_id)]:
        result = frozen.read(BASE / previous / "live/result.json")
        if result["status"] in {"unhandled_or_interrupted", "failed"}:
            raise ValueError("Earlier unknown or failed outcome stops batch")
    if (files.LEDGER / contract["request_sha256"]).exists() or output.exists():
        raise FileExistsError("Request already has a slot/output; no repeat allowed")
    files.configure()  # Verify configured limits before reserving any live slot.
    output.mkdir(parents=True, exist_ok=False)
    approved = output / "authorized_inputs"
    approved.mkdir()
    for path in prepared.iterdir():
        if path.is_file() and path.name not in {"contract.json", "manifest.json"}:
            shutil.copyfile(path, approved / path.name)
    derived = {**contract, "authorization": "explicit_user_five_frozen_questions_2026-11-04",
               "maximum_model_attempts": 1, "maximum_oauth_attempts": 1,
               "approval_file": str(APPROVAL), "original_preparation": str(prepared),
               "input_bindings": {**contract["input_bindings"], **files.bindings([
                   *[p for p in prepared.iterdir() if p.is_file()], APPROVAL, SCOPE, Path(__file__), TESTS])}}
    files.write(approved / "contract.json", derived)
    files.manifest(approved)
    with patch.object(files, "VERSION", VERSION), patch.object(files, "QUESTION", contract["question"]), \
            patch.object(files, "PROTOCOL", SCOPE):
        result = files.send(approved, output / "live", policy)
    return {"id": case_id, **{k: result.get(k) for k in
                              ("status", "http_status", "model_attempts", "oauth_attempts", "usage")}}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-id", choices=IDS, required=True)
    parser.add_argument("--authorize-five-frozen-requests", action="store_true")
    args = parser.parse_args()
    policy, guard = files.NetworkPolicy(), prep.GoldReadGuard()
    guard.allowed.add(SCOPE.resolve())
    sys.addaudithook(policy)
    sys.addaudithook(guard)
    print(json.dumps(run(args.case_id, policy, authorized=args.authorize_five_frozen_requests), ensure_ascii=False))


if __name__ == "__main__":
    main()
