"""One new thirty-case live allowance; frozen requests, no retries, explicit closure."""

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

from scripts import audit_answer_series_20261111 as audit
from scripts import gigachat_answer_smoke as f
from scripts import kondo_nambu_peng_transfer_20261110 as previous

BASE = f.ROOT / "output/answer_series_live_20261111"
LEDGER = f.ROOT / "data/experiments/answer_series_live_20261111"
SCOPE = f.ROOT / "docs/records/answer_series_live_2026-11-11_v0.1.md"
FIXED = audit.BASE / "source_freeze_v01"
VERSION = "answer_series_live_v0.1"


def read(path):
    return json.loads(path.read_bytes())


def require(condition, message):
    if not condition:
        raise ValueError(message)


class InferenceReadGuard:
    def __init__(self):
        self.denied = []

    def __call__(self, event, args):
        if event != "open" or isinstance(args[0], int):
            return
        path = Path(os.fsdecode(args[0])).resolve()
        forbidden = path == previous.USER_FILE.resolve() or path.name.casefold().startswith("ariadne_qa_")
        if path.is_relative_to(f.ROOT / "output"):
            forbidden |= any(p.startswith(("review_", "assessment_", "private_"))
                             for p in path.relative_to(f.ROOT / "output").parts[:-1])
        if forbidden:
            self.denied.append(str(path))
            raise PermissionError("Inference cannot open references or historical assessments")


def initialize():
    require(not BASE.exists(), "New live scope already initialized")
    f.verify_manifest(FIXED)
    f.verify_manifest(audit.FINAL)
    version = read(FIXED / "version.json")
    require(version["freeze_id"] == "8a3740426404b02e4a99a8da2387d67935745f32395992b9e1c443438199a287",
            "Unexpected source freeze")
    app = f.bindings(audit.app_paths())
    require(all(version["bindings"].get(k) == v for k, v in app.items()), "Runtime differs from audited freeze")
    require(subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=f.ROOT, text=True).strip()
            == "c5a72d3dd5068fc05819d7612d76c51f6aed9810", "Unexpected runtime Git baseline")
    original = audit.QUESTIONS / "questions.json"
    questions = read(original)["cases"]
    require([r["id"] for r in questions] == audit.IDS, "Question set changed")
    BASE.mkdir()
    folder = BASE / "input_freeze_v01"
    folder.mkdir()
    bindings = {**app, **f.bindings([Path(__file__), SCOPE, f.ROOT / "pyproject.toml", original,
        audit.FINAL / "manifest.json", FIXED / "manifest.json", Path(previous.__file__), Path(f.__file__)])}
    f.write(folder / "questions.json", {"cases": questions, "references_included": False, "development_exposed": True})
    f.write(folder / "authorization.json", {"raw_user_instruction": "давай", "version": VERSION,
        "recorded_at_utc": datetime.now(UTC).isoformat(), "maximum_model_attempts": 30, "maximum_oauth_attempts": 30,
        "attempts_per_question": 1, "automatic_retries": 0, "fallbacks": 0, "continuations": 0,
        "model": "GigaChat-2-Max", "max_output_tokens": 1200, "per_HTTP_timeout_seconds": 120,
        "actual_cost": None, "scientific_accuracy": None, "all_previous_scopes_remain_closed": True})
    f.write(folder / "bindings.json", bindings)
    f.save(folder / "executed_script.py", Path(__file__).read_bytes())
    f.manifest(folder)
    return {"cases": 30, "real_model_calls": 0, "real_oauth_calls": 0}


def verify_runtime():
    folder = BASE / "input_freeze_v01"
    f.verify_manifest(folder)
    expected = read(folder / "bindings.json")
    f.verify(expected)
    app = f.bindings(audit.app_paths())
    require({k: v for k, v in expected.items() if Path(k).is_relative_to(f.ROOT / "app")} == app,
            "Application file set changed")
    require(not (BASE / "scope_closed_v01.json").exists(), "Scope is closed; dispatch/preparation forbidden")
    return read(folder / "questions.json")["cases"]


def prepare(case, policy, guard):
    verify_runtime()
    cid, settings = case["id"], f.configure()
    folder = BASE / "prepared_v01" / cid
    folder.mkdir(parents=True, exist_ok=False)
    api = read(audit.FINAL / cid / "api_request.json")
    require(api["question"] == case["question"], "Original question changed")
    f.write(folder / "api_request.json", api)
    observation = previous.Observation(folder, settings, policy, case=case)
    reached = False
    with patch.object(f, "QUESTION", case["question"]), patch.object(f, "PROTOCOL", SCOPE):
        try:
            response = previous.run_route(observation, api)
            f.write(folder / "unexpected_response.json", {"http_status": response.status_code, "body": response.json()})
        except f.PreparedBoundary:
            reached = True
        require(reached and observation.scope_ok and observation.readonly == "on" and observation.sources is not None,
                "Fresh API preparation did not reach bounded transport stop")
        require(observation.trace == read(audit.FINAL / cid / "after.json")["trace"], "Fresh full trace changed")
        require(observation.body == (audit.FINAL / cid / "request_unsent.json").read_bytes(), "Fresh native changed")
        require(not observation.sources["diagnostics"] and not policy.denied and not guard.denied,
                "Registry/network/reference diagnostics block preparation")
        require(len(observation.body) <= 100000, "Native exceeds byte ceiling")
        bindings = f.source_inputs(settings, observation)
    bindings.update(read(BASE / "input_freeze_v01/bindings.json"))
    verify_runtime()
    f.verify(bindings)
    contract = {"id": cid, "case": case, "request_sha256": f.sha(observation.body),
        "request_bytes": len(observation.body), "input_bindings": bindings, "dispatch_allowed": True,
        "trace_exact": True, "native_exact": True, "transaction_read_only": "on", "transaction_end": "rollback",
        "network_denials": policy.denied, "reference_read_denials": guard.denied, "model_calls": 0, "oauth_calls": 0}
    f.write(folder / "contract.json", contract)
    f.manifest(folder)
    return {"id": cid, "prepared": True, "request_bytes": len(observation.body), "model_calls": 0}


def seal():
    cases, rows = verify_runtime(), []
    for case in cases:
        folder = BASE / "prepared_v01" / case["id"]
        f.verify_manifest(folder)
        contract = read(folder / "contract.json")
        f.verify(contract["input_bindings"])
        require(contract["case"] == case and contract["dispatch_allowed"], "Preparation scope drift")
        require(contract["request_sha256"] == f.sha((folder / "request.json").read_bytes()), "Prepared request drift")
        rows.append({"id": case["id"], "request_sha256": contract["request_sha256"]})
    digests = [r["request_sha256"] for r in rows]
    require(len(digests) == len(set(digests)) and not any((LEDGER / d).exists() for d in digests),
            "Duplicate/already reserved request in this new scope")
    f.write(BASE / "approval_v01.json", {"cases": rows, "maximum_model_attempts": 30, "maximum_oauth_attempts": 30,
        "raw_user_instruction": "давай", "scope_sha256": f.sha(SCOPE.read_bytes()),
        "input_freeze_sha256": f.sha((BASE / "input_freeze_v01/manifest.json").read_bytes())})
    return {"sealed_requests": 30, "model_calls": 0, "oauth_calls": 0}


def send(case, policy):
    verify_runtime()
    cid = case["id"]
    approval = read(BASE / "approval_v01.json")
    require(approval["scope_sha256"] == f.sha(SCOPE.read_bytes())
            and approval["input_freeze_sha256"] == f.sha((BASE / "input_freeze_v01/manifest.json").read_bytes()),
            "Sealed scope changed")
    for prior in audit.IDS[:audit.IDS.index(cid)]:
        result = read(BASE / "live" / prior / "result.json")
        require(result.get("http_status") in (200, 502) and result.get("postflight_hashes") == "verified",
                "Earlier transport/internal outcome stops further dispatch")
    prepared = BASE / "prepared_v01" / cid
    f.verify_manifest(prepared)
    contract = read(prepared / "contract.json")
    f.verify(contract["input_bindings"])
    require(next(r["request_sha256"] for r in approval["cases"] if r["id"] == cid) == contract["request_sha256"],
            "Approved request changed")
    folder = BASE / "live" / cid
    folder.mkdir(parents=True, exist_ok=False)
    attempt = {"id": cid, "request_sha256": contract["request_sha256"], "scope_sha256": f.sha(SCOPE.read_bytes()),
               "maximum_model_attempts": 1, "maximum_oauth_attempts": 1, "reserved_at_utc": datetime.now(UTC).isoformat()}
    with patch.object(f, "LEDGER", LEDGER):
        slot = f.reserve(contract["request_sha256"], attempt)
    f.write(folder / "attempt.json", attempt)
    observation = previous.Observation(folder, f.configure(), policy, expected=prepared, case=case)
    started = time.perf_counter()
    try:
        with patch.object(f, "QUESTION", case["question"]):
            response = previous.run_route(observation, read(prepared / "api_request.json"))
        payload = response.json()
        f.write(folder / "api_response.json", {"http_status": response.status_code, "body": payload})
        observation.result.update(http_status=response.status_code, status="runtime_api_result",
            delivery_status=payload.get("delivery_status"), answer_status=payload.get("answer", {}).get("status"))
        verify_runtime()
        f.verify(contract["input_bindings"])
        observation.result["postflight_hashes"] = "verified"
    finally:
        if (folder / "response.bin").exists():
            from app.generation.gigachat import _json
            try:
                native = _json((folder / "response.bin").read_bytes())
            except (ValueError, UnicodeError) as exc:
                observation.result["native_metadata_parse_error"] = type(exc).__name__
            else:
                if isinstance(native, dict):
                    observation.result.update(returned_model=native.get("model"), usage=native.get("usage"),
                        finish_reasons=[c.get("finish_reason") for c in native.get("choices", [])])
        observation.result.update(elapsed_seconds=time.perf_counter() - started, allowance_closed=True,
            resend_authorized=False, network_denials=policy.denied)
        f.write(folder / "result.json", observation.result)
        f.write(slot / "result.json", observation.result)
        f.write(slot / "closed.json", {"allowance_closed": True, "resend_authorized": False})
        f.manifest(folder)
    return {"id": cid, **{k: observation.result.get(k) for k in
            ("http_status", "answer_status", "delivery_status", "model_attempts", "oauth_attempts", "usage")}}


def close():
    closed = BASE / "scope_closed_v01.json"
    if closed.exists():
        return read(closed)
    approval = read(BASE / "approval_v01.json")
    rows = []
    for row in approval["cases"]:
        path = BASE / "live" / row["id"] / "result.json"
        slot = LEDGER / row["request_sha256"]
        uncertain = not path.exists() and slot.exists()
        value = read(path) if path.exists() else {
            "status": "reserved_outcome_unknown" if uncertain else "not_dispatched",
            "model_attempts": None if uncertain else 0, "oauth_attempts": None if uncertain else 0}
        rows.append({**row, **value, "allowance_closed": True, "resend_authorized": False})
    unknown = any(r[k] is None for r in rows for k in ("model_attempts", "oauth_attempts"))
    value = {"cases": rows, "remaining_allowance": 0,
             "model_attempts": None if unknown else sum(r["model_attempts"] for r in rows),
             "oauth_attempts": None if unknown else sum(r["oauth_attempts"] for r in rows),
             "all_previous_scopes_remain_closed": True, "scientific_accuracy": None}
    require(unknown or (value["model_attempts"] <= 30 and value["oauth_attempts"] <= 30), "Allowance exceeded")
    f.write(closed, value)
    return value


def batch(mode):
    cases, settings, rows = verify_runtime(), f.configure(), []
    for case in cases:
        command = [sys.executable, "-X", "utf8", "-B", "-m", "scripts.run_answer_series_live_20261111",
                   mode, "--case-id", case["id"]]
        done = subprocess.run(command, cwd=f.ROOT, capture_output=True, encoding="utf-8")
        folder = BASE / "worker_logs" / case["id"]
        folder.mkdir(parents=True, exist_ok=True)
        for label, content in (("stdout", done.stdout), ("stderr", done.stderr)):
            for secret in (settings.gigachat_credentials, settings.database_url):
                if secret:
                    content = content.replace(secret, "[REDACTED]")
            f.save(folder / (mode + "_" + label + ".txt"), content.encode())
        row = {"id": case["id"], "exit_code": done.returncode}
        if done.returncode == 0:
            row.update(json.loads(done.stdout.strip().splitlines()[-1]))
        rows.append(row)
        print(json.dumps(row), flush=True)
        if done.returncode or (mode == "send" and row.get("http_status") not in (200, 502)):
            break
    summary = {"mode": mode, "cases": rows, "finished_all": len(rows) == 30 and all(r["exit_code"] == 0 for r in rows)}
    f.write(BASE / (mode + "_batch_v01.json"), summary)
    if mode == "send":
        close()
    return {"mode": mode, "finished_all": summary["finished_all"], "workers": len(rows)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("init", "prepare", "prepare-all", "seal", "send", "send-all", "close"))
    parser.add_argument("--case-id", choices=audit.IDS)
    args = parser.parse_args()
    policy, guard = f.NetworkPolicy(), InferenceReadGuard()
    sys.dont_write_bytecode = True
    sys.addaudithook(policy)
    if args.mode != "init":
        sys.addaudithook(guard)
    if args.mode == "init":
        result = initialize()
    elif args.mode.endswith("-all"):
        result = batch(args.mode.split("-")[0])
    elif args.mode == "seal":
        result = seal()
    elif args.mode == "close":
        result = close()
    else:
        require(args.case_id is not None, "Worker needs an explicit case ID")
        case = next(c for c in verify_runtime() if c["id"] == args.case_id)
        result = prepare(case, policy, guard) if args.mode == "prepare" else send(case, policy)
    require(not policy.denied and not guard.denied, "Forbidden network/reference access attempted")
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
