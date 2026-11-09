"""Fresh read-only, question-only native preparation; external transport forbidden."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from unittest.mock import patch

from scripts import gigachat_answer_smoke as files
from scripts.prepare_benchmark_inputs_20261103 import BoundaryObservation, GoldReadGuard, load_cases

ROOT = files.ROOT
PROTOCOL = ROOT / "docs/records/reference_quote_runtime_protocol_2026-11-05_v0.2.md"


def capture(case_id: str, output: Path, policy: files.NetworkPolicy):
    case = next(c for c in load_cases() if c["id"] == case_id)
    guard = GoldReadGuard()
    guard.allowed.add(PROTOCOL.resolve())
    sys.addaudithook(guard)
    settings = files.configure()
    from sqlalchemy import text

    from app.db.session import SessionLocal
    from app.generation import service

    output.mkdir(parents=True, exist_ok=False)
    request = {"question": case["question"], "collection": settings.default_collection, "method": settings.rag_retrieval_method,
               "top_k": settings.rag_top_k, "answer_style": "claims", "answer_language": "auto"}
    files.write(output / "api_request.json", request)
    observation = BoundaryObservation(output, settings, policy)
    factory = service.build_answer_provider
    stopped = False
    with SessionLocal() as session:
        session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
        session.execute(text("SET LOCAL statement_timeout = '120s'"))
        readonly = session.execute(text("SHOW transaction_read_only")).scalar_one()
        if readonly != "on":
            raise ValueError("Read-only transaction required")
        with patch.object(files, "QUESTION", case["question"]), patch.object(files, "PROTOCOL", PROTOCOL), \
                patch.object(service, "build_answer_provider", side_effect=lambda s: observation.instrument(factory(s))):
            try:
                response = service.answer_question(session, settings, case["question"], collection=request["collection"],
                    method=request["method"], top_k=request["top_k"], answer_style="claims", answer_language="auto",
                    trace_observer=lambda r, e, m: observation.observe(session, r, e, m))
                files.write(output / "gate_response.json", service.answer_response_to_dict(response))
            except files.PreparedBoundary:
                stopped = True
            bindings = files.source_inputs(settings, observation)
        session.rollback()
    if not stopped or observation.body is None or observation.trace is None or observation.sources is None:
        raise ValueError("Expected full native preparation stopped before external send")
    if policy.denied or guard.denied or observation.sources["diagnostics"]:
        raise ValueError("Unexpected network/reference/source binding diagnostic")
    if (observation.fake_oauth_calls, observation.native_boundary_calls) != (1, 1):
        raise ValueError("Expected exactly one simulated OAuth/native boundary")
    bindings.update(files.bindings([Path(__file__), PROTOCOL, ROOT / "scripts/prepare_benchmark_inputs_20261103.py"]))
    files.verify(bindings)
    result = {"case": case, "request_bytes": len(observation.body), "request_sha256": files.sha(observation.body),
        "input_bindings": bindings, "generation_reached": True, "preparation_status": "prepared_unsent_no_live_authorization",
        "transaction_read_only": readonly, "transaction_end": "rollback", "model_calls": 0, "oauth_calls": 0,
        "new_slots": 0, "maximum_model_attempts": 0, "maximum_oauth_attempts": 0, "automatic_retries": 0,
        "fallbacks": 0, "simulated_oauth_boundaries": 1, "captured_native_boundaries": 1,
        "network_denials": policy.denied, "gold_read_denials": guard.denied,
        "max_output_tokens": settings.rag_gigachat_max_tokens, "timeout_seconds": settings.rag_timeout_seconds,
        "model": settings.rag_model, "source_registry_diagnostics": observation.sources["diagnostics"]}
    files.write(output / "contract.json", result)
    files.manifest(output)
    return {key: value for key, value in result.items() if key != "input_bindings"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=("Q01", "Q05"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    policy = files.NetworkPolicy()
    sys.addaudithook(policy)
    print(json.dumps(capture(args.case, args.output, policy), ensure_ascii=True, indent=2), flush=True)


if __name__ == "__main__":
    main()
