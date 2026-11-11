"""Five one-shot real-provider calls on frozen evidence; no retrieval or default activation."""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from app.generation.answer_instruction_experiment import ExperimentalScientificAnswerProvider
from app.generation.answer_support import audit
from app.generation.gigachat import _json
from app.generation.providers import Evidence, GenerationOutputError, GenerationUnavailableError
from app.generation.service import _validate_claims
from scripts import gigachat_answer_smoke as f
from scripts.prepare_answer_instruction_experiment_v02_20261110 import capture_request

BASE = f.ROOT / "output/answer_instruction_pilot_20261110"
PARENT = f.ROOT / "output/answer_instruction_experiment_20261110"
PROTOCOL = f.ROOT / "docs/records/answer_instruction_pilot_2026-11-10_v0.1.md"
SELECTED = (("rewriting_v02", "Satoh_07"), ("rewriting_v02", "Fan_05"), ("rewriting_v02", "Satoh_06"),
            ("rewriting_v01", "Fan_10"), ("rewriting_v02", "Satoh_03"))


def read(path):
    return json.loads(path.read_bytes())


def initialize():
    settings = f.configure()
    freeze, paired = PARENT / "freeze_v02", PARENT / "preparation_v02"
    f.verify_manifest(freeze)
    f.verify_manifest(paired)
    f.verify(read(freeze / "bindings.json"))
    records = {(r["dataset"], r["id"]): r for r in read(freeze / "records.json")["records"]}
    rows = {(r["dataset"], r["id"]): r for r in read(paired / "report.json")["cases"]}
    output = BASE / "input_freeze_v01"
    output.mkdir(parents=True, exist_ok=False)
    paths = [*f.ROOT.joinpath("app").rglob("*.py"), *f.ROOT.joinpath("app").rglob("*.yaml"),
             Path(__file__), PROTOCOL, f.ROOT / "tests/unit/test_answer_instruction_pilot.py",
             f.ROOT / "scripts/gigachat_answer_smoke.py",
             f.ROOT / "scripts/prepare_answer_instruction_experiment_20261110.py",
             f.ROOT / "scripts/prepare_answer_instruction_experiment_v02_20261110.py", f.ROOT / "pyproject.toml"]
    cases = []
    for dataset, cid in SELECTED:
        original, row = records[(dataset, cid)], rows[(dataset, cid)]
        if row["previous_native_exact"] is not True:
            raise ValueError("Each selected case requires a matching actual historical native")
        original_native = Path(original["actual_native_folder"])
        f.verify_manifest(original_native)
        source = paired / dataset / cid
        raw = (source / "candidate_request.json").read_bytes()
        evidence = [Evidence(**e) for e in original["evidence"]]
        prepared = capture_request(ExperimentalScientificAnswerProvider, row["delivered_question"], evidence)
        if prepared.get("request") != raw:
            raise ValueError("Candidate no longer regenerates byte-exactly")
        digest = f.sha(raw)
        if (f.LEDGER / digest).exists():
            raise FileExistsError("Candidate request already has an attempt slot")
        folder = output / cid
        folder.mkdir()
        f.save(folder / "request.json", raw)
        f.save(folder / "baseline_request.json", (source / "baseline_request.json").read_bytes())
        f.write(folder / "input.json", {"id": cid, "dataset": dataset,
            "original_question": row["original_question"], "question": row["delivered_question"],
            "evidence": original["evidence"], "request_sha256": digest})
        # Baseline answers are review artifacts, never part of the generation input.
        f.write(folder / "historical_baseline.json", original["original_api_body"])
        cases.append({"id": cid, "dataset": dataset, "request_sha256": digest})
        paths.extend([source / "candidate_request.json", source / "baseline_request.json",
                      original_native / "manifest.json", original_native / "request.json",
                      Path(original["original_pdf_path"])])
    code = [p for p in paths if p.suffix != ".pdf"]
    for path in set(code):
        target = output / "source_snapshot" / path.relative_to(f.ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        f.save(target, path.read_bytes())
    f.write(output / "scope.json", {"raw_user_authorization": "давай проведём испытание", "cases": cases,
        "maximum_model_attempts": 5, "maximum_oauth_attempts": 5, "attempts_per_case": 1,
        "retries": 0, "fallbacks": 0, "continuations": 0, "model": settings.rag_model,
        "max_tokens": 1200, "timeout_seconds": 120, "evaluation": "exposed historical-baseline comparison"})
    f.write(output / "bindings.json", f.bindings([*paths, freeze / "manifest.json", paired / "manifest.json"]))
    f.manifest(output)
    return {"cases": len(cases), "maximum_model_attempts": 5, "new_model_calls": 0}


def send(cid, policy):
    freeze = BASE / "input_freeze_v01"
    f.verify_manifest(freeze)
    f.verify(read(freeze / "bindings.json"))
    if (BASE / "closed_v01.json").exists():
        raise FileExistsError("Pilot scope is closed")
    scope = read(freeze / "scope.json")
    ids = [r["id"] for r in scope["cases"]]
    for previous in ids[:ids.index(cid)]:
        result = read(BASE / "live" / previous / "result.json")
        if result["status"] not in {"provider_answered", "provider_abstained", "provider_output_rejected", "transport_failed"}:
            raise RuntimeError("Prior internal failure stops dispatch")
    prepared = freeze / cid
    contract = read(prepared / "input.json")
    settings = f.configure()
    evidence = [Evidence(**e) for e in contract["evidence"]]
    candidate = capture_request(ExperimentalScientificAnswerProvider, contract["question"], evidence)
    if candidate.get("request") != (prepared / "request.json").read_bytes():
        raise ValueError("Pre-OAuth regeneration drift")
    folder = BASE / "live" / cid
    folder.mkdir(parents=True, exist_ok=False)
    attempt = {"authorization": scope["raw_user_authorization"], "scope_sha256": f.sha((freeze / "scope.json").read_bytes()),
               "request_sha256": contract["request_sha256"], "maximum_model_attempts": 1, "maximum_oauth_attempts": 1,
               "reserved_at_utc": datetime.now(UTC).isoformat(), "output": str(folder)}
    slot = f.reserve(contract["request_sha256"], attempt)
    f.write(folder / "attempt.json", attempt)
    observation = f.Observation(folder, settings, policy, expected=prepared)
    client = ExperimentalScientificAnswerProvider(credentials=settings.gigachat_credentials,
        scope=settings.gigachat_scope, model=settings.rag_model, max_tokens=1200, timeout_seconds=120,
        ca_bundle_file=settings.gigachat_ca_bundle_file)
    observation.instrument(client)
    started = time.perf_counter()
    try:
        result = client.generate(contract["question"], evidence, answer_language="ru")
        f.write(folder / "provider_result.json", asdict(result))
        if result.answerable:
            _validate_claims(result.claims, evidence)
        f.write(folder / "audit.json", audit(contract["question"], result.claims, evidence))
        f.verify_manifest(freeze)
        f.verify(read(freeze / "bindings.json"))
        observation.result.update(status="provider_answered" if result.answerable else "provider_abstained",
                                  postflight_input_hashes="verified")
    except (GenerationOutputError, GenerationUnavailableError) as exc:
        message = str(exc)
        for secret in observation.secrets:
            if secret:
                message = message.replace(secret, "[REDACTED]")
        observation.result.update(status="transport_failed" if isinstance(exc, GenerationUnavailableError)
                                  else "provider_output_rejected", error_type=type(exc).__name__, error=message)
    finally:
        raw = folder / "response.bin"
        if raw.exists():
            try:
                native = _json(raw.read_bytes())
            except (ValueError, UnicodeError) as exc:
                observation.result["native_metadata_parse_error"] = type(exc).__name__
            else:
                if isinstance(native, dict):
                    observation.result.update(returned_model=native.get("model"), usage=native.get("usage"))
        observation.result.update(elapsed_seconds=time.perf_counter() - started,
            network_denials=policy.denied, completed_at_utc=datetime.now(UTC).isoformat(),
            provider_level_only=True, resend_authorized=False, allowance_closed=True)
        f.write(folder / "result.json", observation.result)
        f.write(slot / "result.json", observation.result)
        f.write(slot / "answer_instruction_pilot_closed_v01.json", {"resend_authorized": False, "allowance_closed": True})
        f.manifest(folder)
    return {k: observation.result.get(k) for k in ("status", "model_attempts", "oauth_attempts", "usage", "returned_model")}


def close():
    rows = []
    for case in read(BASE / "input_freeze_v01/scope.json")["cases"]:
        path = BASE / "live" / case["id"] / "result.json"
        reserved = (f.LEDGER / case["request_sha256"]).exists()
        result = read(path) if path.exists() else {"status": "unknown_reserved" if reserved else "not_dispatched"}
        rows.append({"id": case["id"], **result})
    value = {"cases": rows, "remaining_allowance": 0, "resend_authorized": False}
    f.write(BASE / "closed_v01.json", value)
    return {"cases": len(rows), "remaining_allowance": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("init", "send", "close"))
    parser.add_argument("--case-id", choices=[cid for _, cid in SELECTED])
    args = parser.parse_args()
    policy = f.NetworkPolicy()
    sys.dont_write_bytecode = True
    sys.addaudithook(policy)
    if args.mode == "send" and args.case_id is None:
        parser.error("--case-id is required for send")
    value = initialize() if args.mode == "init" else (send(args.case_id, policy) if args.mode == "send" else close())
    print(json.dumps(value), flush=True)
