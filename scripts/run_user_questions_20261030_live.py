"""Explicitly authorized, append-only two-case dispatch. Never invoked by question preparation."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import gigachat_answer_smoke as files  # noqa: E402
from scripts.user_questions_20261030 import VERSION, case_scope, load_cases  # noqa: E402

ELIGIBLE = ("q1_swelling_forms", "q2_best_mixture")


def read_scope(root: Path, review: Path) -> dict[str, Any]:
    files.verify_manifest(review)
    report = json.loads((review / "report.json").read_bytes())
    if (report["version"] != VERSION or report["summary"]["eligible_for_separate_live_authorization"] != list(ELIGIBLE)
            or report["summary"]["blocked_before_generation"] != ["q3_lithiation_methods"]):
        raise ValueError("Frozen eligibility differs; no dispatch")
    files.verify(report["bindings"])
    for case in report["cases"]:
        folder = root / case["case"]["id"] / "prepared"
        files.verify_manifest(folder)
        contract = json.loads((folder / "contract.json").read_bytes())
        if contract != case["contract"]:
            raise ValueError("Prepared contract differs from review")
        if case["case"]["id"] in ELIGIBLE:
            raw = (folder / "request.json").read_bytes()
            if files.sha(raw) != contract["request_sha256"]:
                raise ValueError("Prepared request differs")
    return report


def send_case(root: Path, review: Path, case_id: str, policy: files.NetworkPolicy, *, authorized: bool) -> dict[str, Any]:
    if not authorized or case_id not in ELIGIBLE:
        raise ValueError("Explicit two-case authorization and eligible ID required")
    marker = json.loads((root / "live_dispatch.json").read_bytes())
    if marker["eligible"] != list(ELIGIBLE) or marker["maximum_model_attempts"] != 2 or marker["maximum_oauth_attempts"] != 2:
        raise ValueError("Authorized dispatch marker differs")
    report = read_scope(root, review)
    if marker["review_sha256"] != files.sha((review / "report.json").read_bytes()):
        raise ValueError("Approved review binding differs")
    row = next(c for c in report["cases"] if c["case"]["id"] == case_id)
    prepared, live = root / case_id / "prepared", root / case_id / "live"
    if live.exists():
        raise FileExistsError(live)
    contract = row["contract"]
    attempt = {"version": VERSION, "case_id": case_id, "request_sha256": contract["request_sha256"],
        "authorization": "user_explicit_two_new_calls_in_this_chat",
        "dispatch_sha256": files.sha((root / "live_dispatch.json").read_bytes()),
        "maximum_model_attempts": 1, "maximum_oauth_attempts": 1, "automatic_retries": 0,
        "reserved_at_utc": datetime.now(UTC).isoformat(), "output": str(live.resolve())}
    slot = files.reserve(contract["request_sha256"], attempt)
    live.mkdir(parents=True, exist_ok=False)
    files.write(live / "attempt.json", attempt)
    started = time.perf_counter()
    settings = files.configure()
    case = next(c for c in load_cases() if c["id"] == case_id)
    with case_scope(case):
        observer = files.Observation(live, settings, policy, expected=prepared)
        try:
            request = json.loads((prepared / "api_request.json").read_bytes())
            response = files.run_route(observer, request)
            files.write(live / "api_response.json", {"http_status": response.status_code, "body": response.json()})
            status = "runtime_answered" if response.status_code == 200 and response.json().get("status") == "answered" else (
                "provider_abstained" if response.status_code == 200 else "runtime_http_error")
            observer.result.update(status=status, http_status=response.status_code)
            files.verify(report["bindings"])
        finally:
            # Preserve interrupted/exception outcomes without classifying them as model abstentions.
            observer.result.update(case_id=case_id, version=VERSION, completed_at_utc=datetime.now(UTC).isoformat(),
                                   elapsed_seconds=time.perf_counter() - started, network_denials=policy.denied)
            if (live / "response.bin").exists():
                from app.generation.gigachat import _json
                try:
                    native = _json((live / "response.bin").read_bytes())
                except (ValueError, UnicodeError) as exc:
                    observer.result["native_metadata_parse_error"] = type(exc).__name__
                else:
                    if isinstance(native, dict):
                        observer.result.update(returned_model=native.get("model"), usage=native.get("usage"))
                    else:
                        observer.result["native_metadata_parse_error"] = "root_not_object"
            files.write(live / "result.json", observer.result)
            files.write(slot / "result.json", observer.result)
            files.manifest(live)
    return {"id": case_id, **{k: observer.result.get(k) for k in
                             ("status", "http_status", "model_attempts", "oauth_attempts", "usage")}}


def dispatch(root: Path, review: Path, *, authorized: bool) -> dict[str, Any]:
    if not authorized:
        raise ValueError("Explicit user authorization for two new live calls required")
    report = read_scope(root, review)
    files.write(root / "live_dispatch.json", {"version": VERSION, "eligible": list(ELIGIBLE),
        "review_sha256": files.sha((review / "report.json").read_bytes()), "maximum_model_attempts": 2,
        "maximum_oauth_attempts": 2, "automatic_retries": 0, "fallbacks": 0,
        "authorization": "user_explicit_approval_of_two_frozen_questions_in_this_chat",
        "request_sha256": {r["case"]["id"]: r["contract"]["request_sha256"] for r in report["cases"] if r["case"]["id"] in ELIGIBLE}})
    results = []
    for case_id in ELIGIBLE:
        command = [sys.executable, "-B", "-X", "utf8", "-m", "scripts.run_user_questions_20261030_live",
                   "--root", str(root), "--review", str(review), "--worker", "--case-id", case_id,
                   "--authorize-two-new-model-calls"]
        process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=False)
        result_path = root / case_id / "live/result.json"
        # Raw process output may contain transport details; preserve a redacted diagnostic below.
        settings = files.configure()
        stderr = process.stderr
        for secret in (settings.gigachat_credentials, settings.database_url):
            if secret:
                stderr = stderr.replace(secret, "[REDACTED]")
        files.save(root / (case_id + "_live_worker_stderr.txt"), stderr.encode())
        if not result_path.is_file():
            results.append({"id": case_id, "status": "worker_outcome_unknown", "model_attempts": None, "oauth_attempts": None})
            break
        value = json.loads(result_path.read_bytes())
        results.append({"id": case_id, **{k: value.get(k) for k in ("status", "http_status", "model_attempts", "oauth_attempts", "usage")}})
        if process.returncode or value["status"] == "unhandled_or_interrupted":
            break
    summary = {"version": VERSION, "cases": results, "maximum_model_attempts": 2, "maximum_oauth_attempts": 2,
               "automatic_retries": 0, "fallbacks": 0, "blocked_case_not_sent": "q3_lithiation_methods"}
    files.write(root / "live_summary.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--authorize-two-new-model-calls", action="store_true")
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--case-id", choices=ELIGIBLE)
    args = parser.parse_args()
    policy = files.NetworkPolicy()
    sys.addaudithook(policy)
    result = send_case(args.root, args.review, args.case_id, policy, authorized=args.authorize_two_new_model_calls) if args.worker else (
        dispatch(args.root, args.review, authorized=args.authorize_two_new_model_calls))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
