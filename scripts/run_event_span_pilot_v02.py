"""Freeze and execute at most three v0.2 event requests, each once, no retry."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import gigachat_answer_smoke as files  # noqa: E402
from scripts.event_spans_v02 import parse_proposal  # noqa: E402

VERSION = "event_span_live_pilot_v0.2"
BASE = ROOT / "output/event_span_live_pilot_20261029_v02"
PARENT = ROOT / "output/event_spans_v02_20261029/review_v02"
IDS = ("dispersion_hold_then_spectra", "impedance_equilibrium_criterion", "protonation_missing_time")
PROTOCOL = ROOT / "docs/records/event_spans_live_pilot_v0.2_protocol.md"


def prepare() -> dict:
    settings = files.configure()
    files.verify_manifest(PARENT)
    previous = json.loads((PARENT / "report.json").read_bytes())
    files.verify(previous["bindings"])
    schema_folder = PARENT.parent / "schema_check_v01"
    files.verify_manifest(schema_folder)
    schema = json.loads((schema_folder / "report.json").read_bytes())
    files.verify(schema["bindings"])
    bindings = {**previous["bindings"], **schema["bindings"], **files.bindings([
        PARENT / "report.json", PARENT / "manifest.json", schema_folder / "report.json", schema_folder / "manifest.json",
        Path(__file__), ROOT / "tests/unit/test_event_span_pilot_v02.py",
        ROOT / "scripts/review_event_span_pilot_v02.py",
        ROOT / "output/event_span_pilot_v02_preflight_20261029_v01.xml", PROTOCOL])}
    if settings.gigachat_ca_bundle_file:
        bindings.update(files.bindings([Path(settings.gigachat_ca_bundle_file)]))
    entries, artifacts = [], []
    for case_id in IDS:
        row = next(r for r in previous["cases"] if r["case"]["id"] == case_id)
        raw = (PARENT / "requests" / (case_id + ".json")).read_bytes()
        if files.sha(raw) != row["request_sha256"] or len(raw) > 100000 or (files.LEDGER / files.sha(raw)).exists():
            raise ValueError("Request drift, excessive body size or previously consumed SHA slot")
        request = json.loads(raw)
        if request["model"] != settings.rag_model or request["max_tokens"] != settings.rag_gigachat_max_tokens:
            raise ValueError("Frozen request model or token ceiling differs from current settings")
        if json.loads(request["messages"][1]["content"]) != {"question": row["case"]["question"], "source": row["source"]}:
            raise ValueError("Question/source body differs")
        entries.append({"id": case_id, "request_sha256": files.sha(raw), "request_bytes": len(raw)})
        artifacts.append((case_id, raw, row))
    BASE.mkdir(parents=True, exist_ok=False)
    for case_id, raw, row in artifacts:
        prepared = BASE / "cases" / case_id / "prepared"
        prepared.mkdir(parents=True)
        files.save(prepared / "request.json", raw)
        files.write(prepared / "input.json", row)
        files.manifest(prepared)
        bindings.update(files.bindings([p for p in prepared.iterdir() if p.is_file()]))
    snapshot = BASE / "source_snapshot_v01"
    for name, digest in bindings.items():
        path = Path(name)
        if path.is_relative_to(ROOT) and path.suffix in {".py", ".md", ".json"} and path.relative_to(ROOT).parts[0] in {
                "app", "scripts", "tests", "docs"}:
            target = snapshot / path.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            raw = path.read_bytes()
            if files.sha(raw) != digest:
                raise ValueError("Source changed during freeze")
            files.save(target, raw)
    files.manifest(snapshot)
    bindings.update(files.bindings([snapshot / "manifest.json"]))
    files.verify(bindings)
    files.write(BASE / "study_contract_v01.json", {
        "version": VERSION, "user_instruction": "го сл этап", "authorization": "user_next_stage_with_declared_three_case_limit",
        "cases": entries, "bindings": bindings, "maximum_model_attempts": 3, "maximum_oauth_attempts": 3,
        "automatic_retries": 0, "fallbacks": 0, "stop_after_transport_failure": True,
        "model": settings.rag_model, "scope": settings.gigachat_scope, "max_tokens": settings.rag_gigachat_max_tokens,
        "timeout_seconds": settings.rag_timeout_seconds, "ca_bundle_file": settings.gigachat_ca_bundle_file,
        "scientific_acceptance": "not_evaluated"})
    return {"cases": entries, "maximum_model_attempts": 3, "maximum_oauth_attempts": 3, "new_api_calls": 0}


def read_study() -> dict:
    study = json.loads((BASE / "study_contract_v01.json").read_bytes())
    if study["version"] != VERSION or tuple(c["id"] for c in study["cases"]) != IDS or (
            study["maximum_model_attempts"], study["maximum_oauth_attempts"], study["automatic_retries"], study["fallbacks"],
            study["stop_after_transport_failure"]) != (3, 3, 0, 0, True):
        raise ValueError("Frozen scope or limits differ")
    files.verify(study["bindings"])
    files.verify_manifest(BASE / "source_snapshot_v01")
    for c in study["cases"]:
        prepared = BASE / "cases" / c["id"] / "prepared"
        files.verify_manifest(prepared)
        if files.sha((prepared / "request.json").read_bytes()) != c["request_sha256"]:
            raise ValueError("Frozen native request differs")
    return study


def send(case_id: str, *, authorized: bool, policy: files.NetworkPolicy) -> dict:
    if not authorized:
        raise ValueError("Explicit authorization for the declared v0.2 pilot required")
    study = read_study()
    settings = files.configure()
    if case_id not in IDS or (settings.rag_model, settings.gigachat_scope, settings.rag_gigachat_max_tokens,
                             settings.rag_timeout_seconds, settings.gigachat_ca_bundle_file) != (
            study["model"], study["scope"], study["max_tokens"], study["timeout_seconds"], study["ca_bundle_file"]):
        raise ValueError("Case or transport/model settings differ")
    for previous_id in IDS:
        path = BASE / "cases" / previous_id / "live" / "result.json"
        if path.exists() and json.loads(path.read_bytes())["status"] == "transport_failed":
            raise ValueError("Pilot stopped after a transport failure; no remaining sends authorized")
    entry = next(c for c in study["cases"] if c["id"] == case_id)
    prepared, live = (BASE / "cases" / case_id / name for name in ("prepared", "live"))
    raw_request = (prepared / "request.json").read_bytes()
    attempt = {"version": VERSION, "case": case_id, "request_sha256": entry["request_sha256"],
               "authorization": study["authorization"], "maximum_model_attempts": 1, "maximum_oauth_attempts": 1,
               "reserved_at_utc": datetime.now(UTC).isoformat(), "output": str(live.resolve())}
    slot = files.reserve(entry["request_sha256"], attempt)
    live.mkdir(exist_ok=False)
    files.write(live / "attempt.json", attempt)
    from app.generation.gigachat import AUTH_URL, CHAT_URL, GigaChatAnswerProvider, _json
    from app.generation.providers import GenerationUnavailableError
    result = {"version": VERSION, "case": case_id, "status": "interrupted", "model_attempts": 0, "oauth_attempts": 0,
              "automatic_retries": 0, "fallbacks": 0, "scientific_acceptance": "not_evaluated",
              "native_success_http_metadata": "not_exposed_by_transport", "phase": "before_oauth"}
    token = ""
    started = time.perf_counter()
    try:
        provider = GigaChatAnswerProvider(credentials=settings.gigachat_credentials, scope=settings.gigachat_scope,
                                        model=settings.rag_model, timeout_seconds=settings.rag_timeout_seconds,
                                        max_tokens=settings.rag_gigachat_max_tokens, ca_bundle_file=settings.gigachat_ca_bundle_file)
        policy.external = True
        result.update(oauth_attempts=1, phase="oauth")
        auth = provider._post(AUTH_URL, urlencode({"scope": settings.gigachat_scope}).encode(),
                              "Basic " + settings.gigachat_credentials, oauth=True)
        auth_data = _json(auth)
        candidate_token = auth_data.get("access_token") if isinstance(auth_data, dict) else None
        if not isinstance(candidate_token, str) or not candidate_token or any(c.isspace() for c in candidate_token):
            raise ValueError("OAuth did not return a valid token")
        token = candidate_token
        files.save(live / "request.json", raw_request)
        result.update(model_attempts=1, phase="model")
        raw = provider._post(CHAT_URL, raw_request, "Bearer " + token)
        files.save(live / "response.bin", raw)
        result["phase"] = "local_validation"
        native = _json(raw)
        if isinstance(native, dict):
            result.update(returned_model=native.get("model"), usage=native.get("usage"))
            choices = native.get("choices")
            if isinstance(choices, list) and choices and isinstance(choices[0], dict):
                result["finish_reason"] = choices[0].get("finish_reason")
        source = json.loads((prepared / "input.json").read_bytes())["source"]
        files.write(live / "restored.json", parse_proposal(raw, source))
        result["status"] = "integrity_valid_scientific_assignment_unverified"
    except (GenerationUnavailableError, ValueError, UnicodeError, OSError) as exc:
        message = str(exc)
        for secret in (settings.gigachat_credentials, token):
            if secret:
                message = message.replace(secret, "[REDACTED]")
        result.update(status="output_rejected" if (live / "response.bin").exists() else "transport_failed",
                      error_type=type(exc).__name__, error=message)
    finally:
        policy.external = False
        result.update(elapsed_seconds=time.perf_counter() - started, network_denials=policy.denied,
                      completed_at_utc=datetime.now(UTC).isoformat())
        files.write(live / "result.json", result)
        files.write(slot / "result.json", result)
        files.manifest(live)
    files.verify(study["bindings"])
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "send_all"))
    parser.add_argument("--authorize-three-case-live-pilot", action="store_true")
    args = parser.parse_args()
    policy = files.NetworkPolicy()
    sys.addaudithook(policy)
    if args.mode == "prepare":
        print(json.dumps(prepare(), ensure_ascii=False), flush=True)
    else:
        for case_id in IDS:
            result = send(case_id, authorized=args.authorize_three_case_live_pilot, policy=policy)
            print(json.dumps({k: result.get(k) for k in (
                "case", "status", "model_attempts", "oauth_attempts", "phase", "finish_reason", "usage", "error")},
                ensure_ascii=False), flush=True)
            if result["status"] == "transport_failed":
                break


if __name__ == "__main__":
    main()
