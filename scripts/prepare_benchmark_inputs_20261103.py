"""Five question-only actual /answer preparations; this module has no send mode."""

from __future__ import annotations

import argparse
import json
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import patch

from scripts import gigachat_answer_smoke as smoke

ROOT = Path(__file__).resolve().parents[1]
VERSION = "user_benchmark_inputs_v0.1"
CASES = ROOT / "docs/records/user_benchmark_questions_2026-11-03_v0.1.json"
PACKET_HASH = "d0d3ed5983b9e8b2a2bca6f26f1853232a6e7fa76035ae8e5c87fc8ab6c0609a"
PROTOCOL = ROOT / "docs/records/user_benchmark_inputs_protocol_v0.1.md"
BASE = ROOT / "output/user_benchmark_inputs_20261103"
FREEZE = BASE / "input_freeze_v01"


def load_cases(path: Path = CASES, expected_sha256: str = PACKET_HASH) -> list[dict[str, str]]:
    raw = path.read_bytes()
    if smoke.sha(raw) != expected_sha256:
        raise ValueError("Question-only packet hash differs")
    value = json.loads(raw)
    if set(value) != {"version", "cases", "reference_document_sha256", "live_authorization"}:
        raise ValueError("Question-only packet has unexpected fields")
    if value["live_authorization"] is not False or value["version"] != "external_user_benchmark_intake_v0.1":
        raise ValueError("Question-only packet version/authorization differs")
    cases = value["cases"]
    if (not isinstance(cases, list) or any(not isinstance(c, dict) for c in cases)
            or [c.get("id") for c in cases] != [f"Q{i:02d}" for i in range(1, 6)]):
        raise ValueError("Expected exactly ordered Q01–Q05")
    if any(set(c) != {"id", "question"} or not isinstance(c["question"], str) or not c["question"].strip() for c in cases):
        raise ValueError("Only nonempty ID/question pairs are allowed")
    return cases


class GoldReadGuard:
    """Deny benchmark reference/annotation files in the preparation process."""

    def __init__(self) -> None:
        self.allowed = {CASES.resolve(), PROTOCOL.resolve()}
        self.blocked_roots = (ROOT / "docs/records", ROOT / "output/user_benchmark_20261103")
        self.denied: list[str] = []

    def __call__(self, event: str, args: tuple[Any, ...]) -> None:
        if event != "open" or isinstance(args[0], int):
            return
        path = Path(os.fsdecode(args[0])).resolve()
        if path in self.allowed:
            return
        forbidden = (path.name.casefold() == "nafion_rag_benchmark_v1.0.md"
                     or any(path.is_relative_to(parent.resolve()) for parent in self.blocked_roots))
        if forbidden:
            self.denied.append(str(path))
            raise PermissionError("Benchmark reference reads are forbidden during question-only preparation")


class BoundaryObservation(smoke.Observation):
    def __init__(self, *args: Any) -> None:
        super().__init__(*args)
        self.fake_oauth_calls = 0
        self.native_boundary_calls = 0

    def instrument(self, provider: Any) -> Any:
        from app.generation.gigachat import AUTH_URL, CHAT_URL

        def post(url: str, body: bytes, authorization: str, *, oauth: bool = False) -> bytes:
            if oauth:
                if url != AUTH_URL or self.fake_oauth_calls:
                    raise ValueError("Unexpected/repeated offline OAuth boundary")
                self.fake_oauth_calls += 1
                return b'{"access_token":"offline-preparation-placeholder"}'
            if url != CHAT_URL or self.native_boundary_calls:
                raise ValueError("Unexpected/repeated native boundary")
            self.native_boundary_calls += 1
            self.body = body
            smoke.save(self.folder / "request.json", body)
            raise smoke.PreparedBoundary()

        provider._post = post
        return provider


@contextmanager
def case_scope(case: dict[str, str]):
    with patch.object(smoke, "QUESTION", case["question"]), patch.object(smoke, "VERSION", VERSION), \
            patch.object(smoke, "PROTOCOL", PROTOCOL):
        yield


def freeze_runtime() -> dict[str, Any]:
    load_cases()
    files = list((ROOT / "app").rglob("*.py")) + list((ROOT / "app").rglob("*.yaml"))
    files += [Path(__file__), CASES, PROTOCOL, ROOT / "scripts/gigachat_answer_smoke.py",
              ROOT / "tests/unit/test_benchmark_inputs_20261103.py", ROOT / "pyproject.toml"]
    bindings = smoke.bindings(files)
    FREEZE.mkdir(parents=True, exist_ok=False)
    for source in files:
        target = FREEZE / "source_snapshot" / source.resolve().relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        smoke.save(target, source.read_bytes())
    smoke.write(FREEZE / "runtime.json", {"version": VERSION, "input_bindings": bindings,
                "question_packet_sha256": PACKET_HASH, "new_live_authorization": False})
    smoke.write(FREEZE / "manifest.json", {"version": VERSION, "outputs": {
        p.relative_to(FREEZE).as_posix(): smoke.sha(p.read_bytes()) for p in sorted(FREEZE.rglob("*")) if p.is_file()}})
    return {"freeze": str(FREEZE), "bindings": len(bindings)}


def prepare(folder: Path, case: dict[str, str], policy: smoke.NetworkPolicy, guard: GoldReadGuard) -> dict[str, Any]:
    if case not in load_cases():
        raise ValueError("Case differs from the frozen question-only packet")
    smoke.verify_manifest(FREEZE)
    frozen = json.loads((FREEZE / "runtime.json").read_bytes())
    smoke.verify(frozen["input_bindings"])
    settings = smoke.configure()
    request = {"question": case["question"], "collection": settings.default_collection,
               "method": settings.rag_retrieval_method, "top_k": settings.rag_top_k,
               "answer_style": "claims", "answer_language": "auto"}
    folder.mkdir(parents=True, exist_ok=False)
    smoke.write(folder / "api_request.json", request)
    stopped = False
    with case_scope(case):
        observation = BoundaryObservation(folder, settings, policy)
        try:
            response = smoke.run_route(observation, request)
            smoke.write(folder / "gate_response.json", {"http_status": response.status_code, "body": response.json()})
        except smoke.PreparedBoundary:
            stopped = True
        if observation.trace is None or observation.sources is None:
            raise ValueError("Actual /answer trace/source registry missing")
        bindings = smoke.source_inputs(settings, observation)
    bindings.update(frozen["input_bindings"])
    bindings.update(smoke.bindings([FREEZE / "manifest.json", FREEZE / "runtime.json"]))
    if policy.denied or guard.denied:
        raise ValueError("Forbidden network/reference access attempted")
    size = len(observation.body) if observation.body else 0
    blockers = []
    if not stopped:
        blockers.append("production_gate_or_route_did_not_reach_generation")
    if size > 100000:
        blockers.append("native_request_over_100000_byte_review_cap_no_clipping")
    if observation.sources["diagnostics"]:
        blockers.append("source_registry_diagnostics_present")
    smoke.verify(bindings)
    contract = {"version": VERSION, "id": case["id"], "question": case["question"], "input_bindings": bindings,
                "generation_reached": stopped, "blocking_reasons": blockers,
                "preparation_status": "prepared_unsent" if not blockers else "blocked_for_future_dispatch",
                "request_sha256": smoke.sha(observation.body) if observation.body else None, "request_bytes": size,
                "model": settings.rag_model, "max_output_tokens": settings.rag_gigachat_max_tokens,
                "per_http_timeout_seconds": settings.rag_timeout_seconds,
                "authorization": "question_only_preparation_no_live_authorization",
                "maximum_model_attempts": 0, "maximum_oauth_attempts": 0, "new_model_calls": 0, "new_oauth_calls": 0,
                "new_slot_reservations": 0, "automatic_retries": 0, "fallbacks": 0,
                "simulated_oauth_boundaries": observation.fake_oauth_calls,
                "captured_native_boundaries": observation.native_boundary_calls,
                "network_denials": policy.denied, "gold_read_denials": guard.denied,
                "reference_answers_or_expected_articles_passed_to_inference": False,
                "qualifier_check": observation.result.get("qualifier_check"),
                "metadata_diagnostics": observation.result.get("metadata_diagnostics"),
                "scientific_scores": None, "model_answer": None,
                "process_scope": "fresh_process_read_only_DB_not_cache_ORM_validation"}
    smoke.write(folder / "contract.json", contract)
    smoke.write(folder / "manifest.json", {"version": VERSION, "outputs": {
        p.relative_to(folder).as_posix(): smoke.sha(p.read_bytes()) for p in sorted(folder.rglob("*")) if p.is_file()}})
    return {key: contract[key] for key in ("id", "preparation_status", "request_bytes", "request_sha256", "blocking_reasons")}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("freeze", "prepare"))
    parser.add_argument("--case-id", choices=[f"Q{i:02d}" for i in range(1, 6)])
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    policy, guard = smoke.NetworkPolicy(), GoldReadGuard()
    sys.addaudithook(policy)
    sys.addaudithook(guard)
    if arguments.mode == "freeze":
        result = freeze_runtime()
    else:
        if not arguments.case_id or arguments.output is None:
            parser.error("prepare requires --case-id and --output")
        case = next(c for c in load_cases() if c["id"] == arguments.case_id)
        result = prepare(arguments.output, case, policy, guard)
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
