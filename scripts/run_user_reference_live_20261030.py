"""One separately authorized attempt; original zero-budget preparation immutable."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import gigachat_answer_smoke as smoke  # noqa: E402

REQUEST_SHA = "2d25c492bc8d48baaf10193b44f99b267e17caa6700980ce3b03c96bee1ce6fb"
PREP_VERSION = "external_user_reference_preparation_v0.1"
VERSION = "external_user_reference_live_v0.1"
SCOPE = ROOT / "docs/records/user_reference_live_scope_v0.1.md"


def run(prepared: Path, output: Path, approval_file: Path, policy: smoke.NetworkPolicy, *, authorized: bool) -> dict[str, Any]:
    if not authorized:
        raise PermissionError("Explicit new one-call authorization is required before file/network operations")
    approval = json.loads(approval_file.read_bytes())
    required = {"request_sha256": REQUEST_SHA, "maximum_model_attempts": 1, "maximum_oauth_attempts": 1,
                "max_output_tokens": 1200, "per_http_timeout_seconds": 120, "automatic_retries": 0, "fallbacks": 0}
    if any(approval.get(key) != value for key, value in required.items()) or not approval.get("raw_user_approval"):
        raise ValueError("Approval does not match the bounded one-call scope")
    smoke.verify_manifest(prepared)
    contract = json.loads((prepared / "contract.json").read_bytes())
    smoke.verify(contract["input_bindings"])
    if contract.get("infrastructure_continuation_of") is not None:
        raise ValueError("Infrastructure continuation is forbidden")
    if (contract.get("version") != PREP_VERSION or not contract.get("generation_reached") or contract.get("blocking_reasons")
            or contract.get("maximum_model_attempts") != 0 or contract.get("maximum_oauth_attempts") != 0
            or contract.get("new_slot_reservations") != 0):
        raise ValueError("Expected ready original zero-budget preparation")
    raw = (prepared / "request.json").read_bytes()
    if smoke.sha(raw) != REQUEST_SHA or contract["request_sha256"] != REQUEST_SHA or len(raw) != contract["request_bytes"]:
        raise ValueError("Frozen native request identity differs")
    settings = smoke.configure()
    if (settings.rag_model != "GigaChat-2-Max" or settings.rag_gigachat_max_tokens != 1200
            or settings.rag_timeout_seconds != 120 or settings.gigachat_scope != "GIGACHAT_API_PERS" or len(raw) > 100000):
        raise ValueError("Configured model/scope/limits differ from approval")
    native = json.loads(raw)
    if native["model"] != settings.rag_model or native["max_tokens"] != 1200:
        raise ValueError("Native model/limit differs")
    if (smoke.LEDGER / REQUEST_SHA).exists() or output.exists():
        raise FileExistsError("This new request already has a slot or output; no repeat allowed")
    output.mkdir(parents=True, exist_ok=False)
    approved = output / "authorized_inputs"
    approved.mkdir()
    for path in prepared.iterdir():
        if path.is_file() and path.name not in {"contract.json", "manifest.json"}:
            shutil.copyfile(path, approved / path.name)
    new_contract = {**contract, "authorization": "explicit_user_new_scope_" + VERSION,
                    "maximum_model_attempts": 1, "maximum_oauth_attempts": 1,
                    "approval_file": str(approval_file.resolve()), "original_preparation": str(prepared.resolve()),
                    "new_slot_reservations": 0,
                    "input_bindings": {**contract["input_bindings"], **smoke.bindings([
                        *[p for p in prepared.iterdir() if p.is_file()], approval_file, SCOPE, Path(__file__),
                        ROOT / "tests/unit/test_user_reference_live_scope.py"])}}
    smoke.write(approved / "contract.json", new_contract)
    smoke.manifest(approved)
    with patch.object(smoke, "VERSION", VERSION), patch.object(smoke, "QUESTION", contract["question"]), \
            patch.object(smoke, "PROTOCOL", SCOPE):
        return smoke.send(approved, output / "live", policy)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--approval-file", type=Path, required=True)
    parser.add_argument("--authorize-one-new-call", action="store_true")
    args = parser.parse_args()
    policy = smoke.NetworkPolicy()
    sys.addaudithook(policy)
    print(json.dumps(run(args.prepared, args.output, args.approval_file, policy,
                         authorized=args.authorize_one_new_call), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
