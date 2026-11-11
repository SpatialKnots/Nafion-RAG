"""Offline paired native requests, with an explicitly replaced non-network transport."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

from app.generation.answer_instruction_experiment import INSTRUCTION, VERSION, ExperimentalScientificAnswerProvider
from app.generation.gigachat import AUTH_URL, CHAT_URL, GigaChatAnswerProvider
from app.generation.providers import Evidence, GenerationOutputError
from scripts import gigachat_answer_smoke as f

BASE = f.ROOT / "output/answer_instruction_experiment_20261110"
PARENT = f.ROOT / "output/answer_support_v02_20261110/freeze_v01"
PROTOCOL = f.ROOT / "docs/records/answer_instruction_experiment_2026-11-10_v0.1.md"
MODULE = f.ROOT / "app/generation/answer_instruction_experiment.py"


class _RequestCaptured(Exception):
    pass


def capture_request(provider_type, question, evidence, *, model="GigaChat-2-Max", max_tokens=1200,
                    timeout_seconds=120, answer_style="claims", answer_language="ru"):
    """Exercise actual generate until its model request; never dispatch any request."""
    if provider_type not in (GigaChatAnswerProvider, ExperimentalScientificAnswerProvider):
        raise ValueError("Only the paired registered provider classes are supported")
    provider = provider_type(credentials="offline-placeholder", scope="GIGACHAT_API_PERS", model=model,
                             max_tokens=max_tokens, timeout_seconds=timeout_seconds)
    events, captured = [], []

    def transport(url, body, authorization, *, oauth=False):
        if oauth and url == AUTH_URL and not events:
            events.append("synthetic_oauth_response")
            return b'{"access_token":"offline-placeholder-token"}'
        if not oauth and url == CHAT_URL and events == ["synthetic_oauth_response"]:
            events.append("unsent_model_request_captured")
            captured.append(body)
            raise _RequestCaptured
        raise AssertionError("Unexpected transport invocation or retry")

    with patch.object(provider, "_post", side_effect=transport):
        try:
            result = provider.generate(question, evidence, answer_style=answer_style, answer_language=answer_language)
        except _RequestCaptured:
            return {"status": "unsent_request_prepared", "request": captured[0], "transport_events": events}
        except GenerationOutputError as exc:
            if events:
                raise AssertionError("Unexpected output failure after transport") from exc
            return {"status": "inherited_preflight_refusal", "reason": str(exc), "transport_events": events}
    if evidence or result.answerable or result.claims or events:
        raise AssertionError("Expected unchanged empty-evidence abstention only")
    return {"status": "empty_evidence_no_request", "transport_events": events}


def read(path):
    return json.loads(path.read_bytes())


def freeze():
    f.verify_manifest(PARENT)
    parent_bindings = read(PARENT / "bindings.json")
    f.verify(parent_bindings)
    old_assets = [Path(p) for p in parent_bindings if Path(p).is_relative_to(f.ROOT / "app")]
    current_assets = [*f.ROOT.joinpath("app").rglob("*.py"), *f.ROOT.joinpath("app").rglob("*.yaml")]
    if set(current_assets) - set(old_assets) != {MODULE} or set(old_assets) - set(current_assets):
        raise ValueError("Expected one new app module and all prior app assets unchanged")
    folder = BASE / "freeze_v01"
    folder.mkdir(parents=True, exist_ok=False)
    source = [*current_assets, Path(__file__), PROTOCOL,
              f.ROOT / "tests/unit/test_answer_instruction_experiment.py", f.ROOT / "pyproject.toml"]
    for path in source:
        target = folder / "source_snapshot" / path.relative_to(f.ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        f.save(target, path.read_bytes())
    f.save(folder / "records.json", (PARENT / "records.json").read_bytes())
    f.write(folder / "bindings.json", f.bindings([*source, PARENT / "manifest.json", PARENT / "bindings.json",
                                                PARENT / "records.json"]))
    f.write(folder / "scope.json", {"version": VERSION, "prior_assets_unchanged": len(old_assets),
                                   "new_app_modules": [str(MODULE)], "new_model_calls": 0,
                                   "instruction_sha256": f.sha(INSTRUCTION.encode())})
    f.manifest(folder)
    return read(folder / "scope.json")


def prepare():
    folder = BASE / "freeze_v01"
    f.verify_manifest(folder)
    f.verify(read(folder / "bindings.json"))
    output = BASE / "preparation_v01"
    output.mkdir(exist_ok=False)
    rows, previous_exact = [], 0
    for record in read(folder / "records.json")["records"]:
        evidence = [Evidence(**item) for item in record["evidence"]]
        original_input = f.encode({"question": record["question"], "evidence": [asdict(e) for e in evidence]})
        baseline = capture_request(GigaChatAnswerProvider, record["question"], evidence)
        candidate = capture_request(ExperimentalScientificAnswerProvider, record["question"], evidence)
        if baseline["status"] != candidate["status"]:
            raise ValueError("Candidate changed inherited preflight behavior")
        row = {"dataset": record["dataset"], "id": record["id"], "status": baseline["status"],
               "prior_answer_status": record["original_status"], "previous_native_exact": None,
               "input_sha256": f.sha(original_input), "new_model_calls": 0}
        if baseline["status"] == "unsent_request_prepared":
            old, new = json.loads(baseline["request"]), json.loads(candidate["request"])
            old_prompt = old["messages"][1]["content"]
            if new["messages"][1]["content"] != INSTRUCTION + "\n" + old_prompt:
                raise ValueError("Expected exactly the general instruction prefix for these raw sources")
            comparable = json.loads(candidate["request"])
            comparable["messages"][1]["content"] = old_prompt
            if comparable != old:
                raise ValueError("Native request changed beyond the instruction prefix")
            if record["actual_native_folder"]:
                native = Path(record["actual_native_folder"])
                f.verify_manifest(native)
                if (native / "request.json").read_bytes() != baseline["request"]:
                    raise ValueError("Regenerated baseline differs from saved actual native")
                previous_exact += 1
                row["previous_native_exact"] = True
            case_folder = output / record["dataset"] / record["id"]
            case_folder.mkdir(parents=True)
            for key, prepared in (("baseline", baseline), ("candidate", candidate)):
                f.save(case_folder / (key + "_request.json"), prepared["request"])
                row[key + "_sha256"] = f.sha(prepared["request"])
            row["instruction_only_change"] = True
            row["added_user_prompt_characters"] = len(INSTRUCTION) + 1
        elif baseline != candidate:
            raise ValueError("Nonrequest outcomes differ")
        if f.encode({"question": record["question"], "evidence": [asdict(e) for e in evidence]}) != original_input:
            raise ValueError("Original question or evidence mutated")
        rows.append(row)
    f.verify(read(folder / "bindings.json"))
    if len(rows) != 60 or previous_exact != 30:
        raise ValueError("Expected all sixty records and thirty prior answered-native matches")
    report = {"version": VERSION, "cases": rows, "prior_native_byte_matches": previous_exact,
              "prepared_pairs": sum(r["status"] == "unsent_request_prepared" for r in rows),
              "new_model_calls": 0, "new_oauth_calls": 0, "new_DB_calls": 0,
              "quality_measurement": "not_evaluated; unsent prompts only; exposed development data",
              "bindings": f.bindings([folder / "manifest.json", folder / "bindings.json", folder / "records.json"])}
    f.write(output / "report.json", report)
    f.manifest(output)
    return {k: v for k, v in report.items() if k not in {"cases", "bindings"}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("freeze", "prepare"))
    args = parser.parse_args()
    policy = f.NetworkPolicy()
    sys.dont_write_bytecode = True
    sys.addaudithook(policy)
    value = freeze() if args.mode == "freeze" else prepare()
    if policy.denied:
        raise RuntimeError("Unexpected external-network attempt")
    print(json.dumps({**value, "external_network_denials": policy.denied}))
