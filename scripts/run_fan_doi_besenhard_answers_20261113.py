"""One authorized 26-case answer pass over exact post-rewriting native requests."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from scripts import fan_doi_besenhard_rewriting_20261113 as profile
from scripts import fan_doi_besenhard_rewriting_prepare_20261113 as preparation

f = profile.f
BASE = f.ROOT / "output/fan_doi_besenhard_answer_live_20261113"
LEDGER = f.ROOT / "data/experiments/fan_doi_besenhard_answer_live_20261113"
SCOPE = f.ROOT / "docs/records/fan_doi_besenhard_answer_live_2026-11-13_v0.1.md"
PROPOSAL = profile.BASE / "live_review_v01/prospective_answer_scope.json"
TESTS = f.ROOT / "tests/unit/test_fan_doi_besenhard_answer_scope.py"


def read(path):
    return json.loads(path.read_bytes())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate_case(case, approved, contract, native):
    require(case["id"] == approved["id"] and contract["case"] == case, "Approved case differs")
    require(contract["generation_reached"] and contract["eligible_for_future_scope"]
        and contract["article_scope_matches"] and not contract["dispatch_allowed"], "Original preparation not eligible")
    require(contract["request_sha256"] == approved["request_sha256"] == f.sha(native)
        and contract["request_bytes"] == len(native) <= 100000, "Approved native request differs")
    require(contract["transaction_read_only"] == "on" and contract["transaction_end"] == "rollback"
        and not contract["network_denials"] and not contract["reference_read_denials"], "Preparation diagnostics block dispatch")
    wire = json.loads(native)
    require(wire["model"] == "GigaChat-2-Max" and wire["max_tokens"] == 1200, "Model/token budget differs")


def initialize():
    require(not BASE.exists() and not LEDGER.exists(), "Answer scope already exists")
    preparation.verify()
    cases = {c["id"]: c for c in profile.cases()}
    f.verify_manifest(profile.BASE / "live_review_v01")
    proposal = read(PROPOSAL)
    require(len(proposal["cases"]) == proposal["maximum_model_attempts_if_authorized"]
        == proposal["maximum_oauth_attempts_if_authorized"] == 26, "Unexpected prospective scope")
    require(proposal["plans_manifest_sha256"] == f.sha((profile.BASE / "plans_freeze_v01/manifest.json").read_bytes()),
            "Approved rewrite plans changed")
    rows, paths, common = [], [Path(__file__), SCOPE, TESTS, PROPOSAL,
        profile.BASE / "plans_freeze_v01/manifest.json", preparation.EXTENSION / "manifest.json"], {}
    for approved in proposal["cases"]:
        case = cases[approved["id"]]
        folder = profile.BASE / "prepared_v01" / case["id"]
        f.verify_manifest(folder)
        contract = read(folder / "contract.json")
        validate_case(case, approved, contract, (folder / "request.json").read_bytes())
        profile.load_plan(case)
        plan_bindings = profile.BASE / "answer_plan_bindings_v01" / case["id"]
        f.verify_manifest(plan_bindings)
        f.verify(read(plan_bindings / "bindings.json"))
        for path, digest in contract["input_bindings"].items():
            require(path not in common or common[path] == digest, "Conflicting frozen input hashes")
            common[path] = digest
        paths += [folder / "manifest.json", folder / "contract.json", plan_bindings / "manifest.json"]
        rows.append({**approved, "case": case, "prepared_folder": str(folder),
                     "preparation_manifest_sha256": f.sha((folder / "manifest.json").read_bytes())})
    require(len({r["request_sha256"] for r in rows}) == 26, "Duplicate answer requests")
    f.verify(common)
    folder = BASE / "authorized_inputs_v01"
    folder.mkdir(parents=True)
    f.write(folder / "authorization.json", {"raw_user_authorization": "Да, запускай",
        "recorded_at_utc": datetime.now(UTC).isoformat(), "cases": rows,
        "maximum_model_attempts": 26, "maximum_oauth_attempts": 26, "attempts_per_case": 1,
        "automatic_retries": 0, "fallbacks": 0, "continuations": 0, "model": "GigaChat-2-Max",
        "max_output_tokens": 1200, "per_http_timeout_seconds": 120, "cost": None,
        "rewriting_allowance_remains_closed": True, "all_previous_allowances_remain_closed": True})
    f.write(folder / "bindings.json", {**common, **f.bindings(paths)})
    f.save(folder / "executed_script.py", Path(__file__).read_bytes())
    f.manifest(folder)
    return {"authorized_answer_cases": 26, "model_calls": 0, "oauth_calls": 0}


def authorization():
    folder = BASE / "authorized_inputs_v01"
    f.verify_manifest(folder)
    f.verify(read(folder / "bindings.json"))
    return read(folder / "authorization.json")


class ReferenceGuard(preparation.StableReferenceGuard):
    def __call__(self, event, args):
        if event == "open" and not isinstance(args[0], int):
            path = Path(os.fsdecode(args[0])).resolve()
            if path == SCOPE:
                return
            if path.is_relative_to(BASE) and not any(part.startswith(("review_", "assessment_", "private_"))
                                                    for part in path.relative_to(BASE).parts):
                return
        return super().__call__(event, args)


def send(row, policy, guard):
    require(not (BASE / "scope_closed_v01.json").exists(), "Answer scope closed; resend forbidden")
    approved = authorization()
    require(row in approved["cases"], "Case outside authorized scope")
    for prior in approved["cases"][:approved["cases"].index(row)]:
        result = read(BASE / "live" / prior["id"] / "result.json")
        require(result.get("http_status") in (200, 502) and result.get("postflight_hashes") == "verified",
                "Earlier transport/internal failure stops remaining dispatch")
    case = row["case"]
    prepared = Path(row["prepared_folder"])
    f.verify_manifest(prepared)
    require(f.sha((prepared / "manifest.json").read_bytes()) == row["preparation_manifest_sha256"], "Preparation changed")
    contract = read(prepared / "contract.json")
    validate_case(case, row, contract, (prepared / "request.json").read_bytes())
    plan = profile.load_plan(case)
    require(plan is not None, "Rewrite meaning decision no longer accepted")
    folder = BASE / "live" / case["id"]
    folder.mkdir(parents=True, exist_ok=False)
    attempt = {"id": case["id"], "request_sha256": row["request_sha256"],
        "authorization_sha256": f.sha((BASE / "authorized_inputs_v01/manifest.json").read_bytes()),
        "maximum_model_attempts": 1, "maximum_oauth_attempts": 1, "reserved_at_utc": datetime.now(UTC).isoformat()}
    with patch.object(f, "LEDGER", LEDGER):
        slot = f.reserve(row["request_sha256"], attempt)
    f.write(folder / "attempt.json", attempt)
    observation = profile.baseline.route.Observation(folder, f.configure(), policy, expected=prepared, case=case)
    started = time.perf_counter()
    try:
        with profile.activate(case, plan), patch.object(f, "QUESTION", case["question"]):
            response = profile.baseline.route.run_route(observation, read(prepared / "api_request.json"))
        payload = response.json()
        f.write(folder / "api_response.json", {"http_status": response.status_code, "body": payload})
        observation.result.update(http_status=response.status_code, status="runtime_api_result",
            answer_status=payload.get("answer", {}).get("status"), delivery_status=payload.get("delivery_status"))
        authorization()
        f.verify_manifest(prepared)
        f.verify(contract["input_bindings"])
        profile.load_plan(case)
        require(not guard.denied and not policy.denied, "Forbidden inference read/network access")
        observation.result["postflight_hashes"] = "verified"
    finally:
        if (folder / "response.bin").exists():
            try:
                native = profile.qr_old._json((folder / "response.bin").read_bytes())
            except (ValueError, UnicodeError) as exc:
                observation.result["native_metadata_parse_error"] = type(exc).__name__
            else:
                if isinstance(native, dict):
                    observation.result.update(returned_model=native.get("model"), usage=native.get("usage"),
                        finish_reasons=[c.get("finish_reason") for c in native.get("choices", [])])
        observation.result.update(elapsed_seconds=time.perf_counter() - started, allowance_closed=True,
            resend_authorized=False, network_denials=policy.denied, reference_read_denials=guard.denied)
        f.write(folder / "result.json", observation.result)
        f.write(slot / "result.json", observation.result)
        f.write(slot / "closed.json", {"allowance_closed": True, "resend_authorized": False})
        f.manifest(folder)
    return {"id": case["id"], **{k: observation.result.get(k) for k in
            ("http_status", "answer_status", "delivery_status", "model_attempts", "oauth_attempts", "usage")}}


def close():
    path = BASE / "scope_closed_v01.json"
    if path.exists():
        return read(path)
    rows = []
    for row in read(BASE / "authorized_inputs_v01/authorization.json")["cases"]:
        result_path = BASE / "live" / row["id"] / "result.json"
        slot = LEDGER / row["request_sha256"]
        reserved_unknown = not result_path.exists() and slot.exists()
        value = read(result_path) if result_path.exists() else {
            "status": "reserved_outcome_unknown" if reserved_unknown else "not_dispatched",
            "model_attempts": None if reserved_unknown else 0, "oauth_attempts": None if reserved_unknown else 0}
        record = {"id": row["id"], **value, "allowance_closed": True, "resend_authorized": False}
        if slot.exists() and not (slot / "closed.json").exists():
            f.write(slot / "closed.json", record)
        rows.append(record)
    result = {"cases": rows, "remaining_model_allowance": 0, "remaining_oauth_allowance": 0}
    f.write(path, result)
    return result


def batch():
    approved, rows = authorization(), []
    require(not (BASE / "scope_closed_v01.json").exists(), "Scope closed")
    try:
        for row in approved["cases"]:
            log = BASE / "worker_logs_v01" / row["id"]
            log.mkdir(parents=True, exist_ok=False)
            done = subprocess.run([sys.executable, "-X", "utf8", "-B", "-m", __spec__.name,
                                   "send", "--case-id", row["id"]], cwd=f.ROOT,
                                  capture_output=True, text=True, encoding="utf-8", check=False)
            settings = f.configure()
            for name, value in (("stdout", done.stdout), ("stderr", done.stderr)):
                for secret in (settings.gigachat_credentials, settings.database_url):
                    if secret:
                        value = value.replace(secret, "[REDACTED]")
                f.save(log / (name + ".txt"), value.encode())
            result = {"id": row["id"], "exit_code": done.returncode}
            if done.returncode == 0:
                result.update(json.loads(done.stdout.strip().splitlines()[-1]))
            rows.append(result)
            print(json.dumps(result), flush=True)
            if done.returncode or result.get("http_status") not in (200, 502):
                break
    finally:
        close()
    f.write(BASE / "batch_v01.json", {"cases": rows, "finished_all": len(rows) == 26 and all(r["exit_code"] == 0 for r in rows)})
    return {"cases": len(rows), "remaining_allowance": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("init", "send", "send-all", "close"))
    parser.add_argument("--case-id")
    args = parser.parse_args()
    policy, guard = f.NetworkPolicy(), ReferenceGuard()
    sys.addaudithook(policy)
    sys.addaudithook(guard)
    if args.mode == "init":
        result = initialize()
    elif args.mode == "send-all":
        result = batch()
    elif args.mode == "close":
        result = close()
    else:
        require(args.case_id is not None, "Case required")
        row = next(c for c in authorization()["cases"] if c["id"] == args.case_id)
        result = send(row, policy, guard)
    require(not guard.denied and not policy.denied, "Forbidden access")
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
