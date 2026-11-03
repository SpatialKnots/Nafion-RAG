"""Freeze one external reference and prepare its question; no reference enters inference."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import gigachat_answer_smoke as smoke  # noqa: E402

VERSION = "external_user_reference_preparation_v0.1"
CASES = ROOT / "docs/records/independent_reference_candidates_2026-10-30_v0.1.json"
PROTOCOL = ROOT / "docs/records/user_reference_preparation_protocol_v0.1.md"


def run(output: Path, policy: smoke.NetworkPolicy) -> dict:
    value = json.loads(CASES.read_bytes())
    case, = value["cases"]
    if value["model_answers"] is not None or value["scientific_scores"] is not None or value["new_live_authorization"]:
        raise ValueError("Expected unscored/unrun reference without live authorization")
    # Confirm code was frozen before receipt of this external reference.
    runtime = ROOT / "output/lithiation_runtime_20261030/review_v05/report.json"
    smoke.verify(json.loads(runtime.read_bytes())["bindings"])
    settings = smoke.configure()
    output.mkdir(parents=True, exist_ok=False)
    bindings = smoke.bindings([Path(__file__), CASES, PROTOCOL, runtime])
    smoke.write(output / "user_reference_original.json", value)
    request = {"question": case["question"], "collection": settings.default_collection,
               "method": settings.rag_retrieval_method, "top_k": settings.rag_top_k,
               "answer_style": "claims", "answer_language": "auto"}
    smoke.write(output / "api_request.json", request)
    stopped = False
    with patch.object(smoke, "QUESTION", case["question"]), patch.object(smoke, "VERSION", VERSION), \
            patch.object(smoke, "PROTOCOL", PROTOCOL):
        observer = smoke.Observation(output, settings, policy)
        try:
            response = smoke.run_route(observer, request)
            smoke.write(output / "gate_response.json", {"http_status": response.status_code, "body": response.json()})
        except smoke.PreparedBoundary:
            stopped = True
        if observer.trace is None or observer.sources is None:
            raise ValueError("Actual source trace missing")
        bindings.update(smoke.source_inputs(settings, observer))
    if policy.denied:
        raise ValueError("Unexpected network attempt")
    size = len(observer.body) if observer.body else 0
    blockers = []
    if not stopped:
        blockers.append("production_gate_did_not_reach_generation")
    if size > 100000:
        blockers.append("native_over_proposed_100000_byte_review_cap_no_clipping")
    smoke.verify(bindings)
    contract = {"version": VERSION, "id": case["id"], "question": case["question"], "input_bindings": bindings,
                "reference_provider": value["reference_provider"], "annotation_method": value["annotation_method"],
                "reference_or_expected_pdf_passed_to_inference": False,
                "generation_reached": stopped, "blocking_reasons": blockers,
                "request_sha256": smoke.sha(observer.body) if observer.body else None, "request_bytes": size,
                "model": settings.rag_model, "max_output_tokens": settings.rag_gigachat_max_tokens,
                "per_http_timeout_seconds": settings.rag_timeout_seconds,
                "maximum_model_attempts": 0, "maximum_oauth_attempts": 0, "new_slot_reservations": 0,
                "real_model_oauth_calls": 0, "automatic_retries": 0, "fallbacks": 0,
                "authorization": "offline_preparation_only_no_new_live_authorization",
                "scientific_scores": None, "scientific_acceptance": "not_established",
                "process_scope": "fresh_process_not_cache_orm_validation"}
    smoke.write(output / "contract.json", contract)
    smoke.manifest(output)
    return {key: contract[key] for key in ("id", "generation_reached", "blocking_reasons", "request_bytes",
                                          "request_sha256", "real_model_oauth_calls", "new_slot_reservations")}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    policy = smoke.NetworkPolicy()
    sys.addaudithook(policy)
    print(json.dumps(run(args.output, policy), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
