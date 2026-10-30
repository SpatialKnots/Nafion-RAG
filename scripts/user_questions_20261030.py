"""Freeze three verbatim user questions and capture current /answer preparation, without live inference."""

from __future__ import annotations

import argparse
import json
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import gigachat_answer_smoke as smoke  # noqa: E402

VERSION = "user_questions_20261030_v0.1"
CASES = ROOT / "docs/records/user_questions_2026-10-30_v0.1.json"
PROTOCOL = ROOT / "docs/records/user_questions_2026-10-30_protocol_v0.1.md"
EXPECTED = (
    ("q1_swelling_forms", "Покажи как меняется степень набухания мембраны Нафион пре переходе от протонированной к литированной форме"),
    ("q2_best_mixture", "Какая смесь растворителей даёт наилучшую ионную проводимость для Li-Nafion"),
    ("q3_lithiation_methods", "Какие существуют методики литирования Nafion?"),
)


def load_cases() -> list[dict[str, Any]]:
    value = json.loads(CASES.read_bytes())
    if value["version"] != VERSION or [(c["id"], c["question"]) for c in value["cases"]] != list(EXPECTED):
        raise ValueError("Verbatim user question inventory differs")
    if value["reference_answers"] is not None or value["independent_scientific_annotations"] is not None:
        raise ValueError("No independent reference answers were supplied with these questions")
    return value["cases"]


@contextmanager
def case_scope(case: dict[str, Any]):
    with patch.object(smoke, "QUESTION", case["question"]), patch.object(smoke, "VERSION", VERSION), patch.object(
            smoke, "PROTOCOL", PROTOCOL):
        yield


def prepare(root: Path, case: dict[str, Any], policy: smoke.NetworkPolicy) -> dict[str, Any]:
    settings = smoke.configure()
    folder = root / case["id"] / "prepared"
    folder.mkdir(parents=True, exist_ok=False)
    bindings = smoke.bindings([Path(__file__), CASES, PROTOCOL, ROOT / "tests/unit/test_user_questions_20261030.py"])
    request = {"question": case["question"], "collection": settings.default_collection,
               "method": settings.rag_retrieval_method, "top_k": settings.rag_top_k,
               "answer_style": "claims", "answer_language": "auto"}
    smoke.write(folder / "api_request.json", request)
    stopped = False
    with case_scope(case):
        observer = smoke.Observation(folder, settings, policy)
        try:
            response = smoke.run_route(observer, request)
            smoke.write(folder / "gate_response.json", {"http_status": response.status_code, "body": response.json()})
        except smoke.PreparedBoundary:
            stopped = True
        if observer.trace is None or observer.sources is None:
            raise ValueError("Actual answer/source trace was not captured")
        bindings.update(smoke.source_inputs(settings, observer))
    size = len(observer.body) if observer.body else 0
    blockers = []
    if not stopped:
        blockers.append("production_gate_or_route_did_not_reach_generation")
    if size > 100000:
        blockers.append("native_request_over_100000_bytes_no_clipping")
    if observer.sources["diagnostics"]:
        blockers.append("source_registry_diagnostics_present")
    if policy.denied:
        raise ValueError("Unexpected network attempt during preparation")
    smoke.verify(bindings)
    contract = {"version": VERSION, "question": case["question"], "id": case["id"], "input_bindings": bindings,
        "generation_reached": stopped, "preparation_status": "ready_for_explicit_scope_authorization" if not blockers else "blocked",
        "blocking_reasons": blockers, "request_sha256": smoke.sha(observer.body) if observer.body else None,
        "request_bytes": size, "model": settings.rag_model, "max_output_tokens": settings.rag_gigachat_max_tokens,
        "per_http_timeout_seconds": settings.rag_timeout_seconds, "scope": settings.gigachat_scope,
        "authorization": "offline_preparation_only_new_live_calls_not_authorized", "maximum_model_attempts": 0,
        "maximum_oauth_attempts": 0, "automatic_retries": 0, "fallbacks": 0, "new_slot_reservations": 0,
        "new_model_calls": 0, "new_oauth_calls": 0, "qualifier_check": observer.result.get("qualifier_check"),
        "metadata_diagnostics": observer.result.get("metadata_diagnostics"), "network_denials": policy.denied,
        "scientific_acceptance": "not_evaluated", "independent_reference_answers": None,
        "process_scope": "fresh_process_not_long_lived_cache_validation"}
    smoke.write(folder / "contract.json", contract)
    smoke.manifest(folder)
    return {k: contract[k] for k in ("id", "preparation_status", "request_bytes", "request_sha256", "blocking_reasons",
                                    "new_model_calls", "new_oauth_calls")}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--case-id", choices=[c[0] for c in EXPECTED], required=True)
    args = parser.parse_args()
    case = next(c for c in load_cases() if c["id"] == args.case_id)
    policy = smoke.NetworkPolicy()
    sys.addaudithook(policy)
    print(json.dumps(prepare(args.root, case, policy), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
