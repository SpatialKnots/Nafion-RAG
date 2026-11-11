"""New scoped five-question required-field experiment; reuse proven one-shot transport."""

from __future__ import annotations

import argparse
import json
import sys
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from app.generation.providers import Evidence, GeneratedClaim
from app.generation.required_answer_fields import RequirementGuidedAnswerProvider, build, check, validate
from scripts import gigachat_answer_smoke as f
from scripts import prepare_answer_instruction_experiment_v02_20261110 as capture_module
from scripts import run_answer_instruction_pilot_20261110 as engine

BASE = f.ROOT / "output/required_answer_fields_20261110"
PARENT = engine.BASE
LEDGER = f.ROOT / "data/experiments/required_answer_fields_20261110"
PROTOCOL = f.ROOT / "docs/records/required_answer_fields_2026-11-10_v0.1.md"
SELECTED = engine.SELECTED


def read(path):
    return json.loads(path.read_bytes())


def capture(provider_type, question, evidence):
    if provider_type is not RequirementGuidedAnswerProvider:
        raise ValueError("Only the declared requirement-guided provider is allowed")
    with patch.object(capture_module, "ExperimentalScientificAnswerProvider", RequirementGuidedAnswerProvider):
        return capture_module.capture_request(provider_type, question, evidence)


@contextmanager
def environment():
    with patch.object(engine, "BASE", BASE), patch.object(engine, "ExperimentalScientificAnswerProvider",
            RequirementGuidedAnswerProvider), patch.object(engine, "capture_request", capture), patch.object(f, "LEDGER", LEDGER):
        yield


def initialize():
    settings = f.configure()
    parent = PARENT / "input_freeze_v01"
    f.verify_manifest(parent)
    f.verify(read(parent / "bindings.json"))
    if read(PARENT / "closed_v01.json")["remaining_allowance"] != 0:
        raise ValueError("Previous scope must stay closed")
    output = BASE / "input_freeze_v01"
    output.mkdir(parents=True, exist_ok=False)
    paths = [*f.ROOT.joinpath("app").rglob("*.py"), *f.ROOT.joinpath("app").rglob("*.yaml"), Path(__file__),
        PROTOCOL, Path(engine.__file__), Path(f.__file__), Path(capture_module.__file__),
        f.ROOT / "scripts/test_answer_support_20261110.py", f.ROOT / "tests/unit/test_required_answer_fields.py",
        f.ROOT / "tests/unit/test_required_answer_fields_runner.py", f.ROOT / "pyproject.toml",
        parent / "manifest.json", PARENT / "closed_v01.json"]
    paths += [Path(p) for p in read(parent / "bindings.json") if Path(p).suffix == ".pdf"]
    rows = []
    for dataset, cid in SELECTED:
        old, live = parent / cid, PARENT / "live" / cid
        f.verify_manifest(live)
        inp = read(old / "input.json")
        evidence = [Evidence(**e) for e in inp["evidence"]]
        plan = build(inp["question"], evidence)
        validate(plan, inp["question"], evidence)
        prepared = capture(RequirementGuidedAnswerProvider, inp["question"], evidence)
        raw = prepared["request"]
        oldraw = (live / "request.json").read_bytes()
        oldprompt = json.loads(oldraw)["messages"][1]["content"]
        native = json.loads(raw)
        if plan["status"] == "mapped":
            if not native["messages"][1]["content"].endswith(oldprompt):
                raise ValueError("Original question/evidence/guidance changed")
        elif raw != oldraw:
            raise ValueError("Unsupported-family positive controls must preserve their exact native")
        native["messages"][1]["content"] = oldprompt
        if native != json.loads(oldraw):
            raise ValueError("Changes beyond the requirement prefix")
        digest = f.sha(raw)
        if (LEDGER / digest).exists():
            raise FileExistsError("Request already attempted within the new scope")
        folder = output / cid
        folder.mkdir()
        f.save(folder / "request.json", raw)
        f.save(folder / "baseline_request.json", oldraw)
        f.write(folder / "input.json", {**inp, "request_sha256": digest})
        f.write(folder / "requirements.json", plan)
        f.save(folder / "historical_baseline.json", (live / "provider_result.json").read_bytes())
        f.write(folder / "offline_baseline_check.json", check(inp["question"], [
            GeneratedClaim(**c) for c in read(live / "provider_result.json")["claims"]], evidence))
        rows.append({"id": cid, "dataset": dataset, "request_sha256": digest,
                     "same_native_as_closed_prior_scope": raw == oldraw, "requirement_family": plan["family"]})
        paths.extend([old / "input.json", live / "manifest.json", live / "request.json", live / "provider_result.json"])
    if sum(r["same_native_as_closed_prior_scope"] for r in rows) != 2:
        raise ValueError("Expected two unchanged positive-control requests and three new requirement cards")
    for path in set(paths):
        if path.suffix == ".pdf":
            continue
        target = output / "source_snapshot" / path.relative_to(f.ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        f.save(target, path.read_bytes())
    f.write(output / "scope.json", {"raw_user_authorization": "Да, давай", "cases": rows,
        "maximum_model_attempts": 5, "maximum_oauth_attempts": 5, "attempts_per_case": 1,
        "retries": 0, "fallbacks": 0, "continuations": 0, "model": settings.rag_model,
        "max_tokens": 1200, "timeout_seconds": 120, "ledger": str(LEDGER),
        "same_body_controls": "new explicitly authorized scope; old slots untouched, not a retry of old scope"})
    f.write(output / "bindings.json", f.bindings(paths))
    f.manifest(output)
    return {"cases": 5, "requirement_cards": 3, "unchanged_positive_controls": 2, "new_model_calls": 0}


def send(cid, policy):
    inp = read(BASE / "input_freeze_v01" / cid / "input.json")
    evidence = [Evidence(**e) for e in inp["evidence"]]
    validate(read(BASE / "input_freeze_v01" / cid / "requirements.json"), inp["question"], evidence)
    with environment():
        result = engine.send(cid, policy)
    path = BASE / "live" / cid / "provider_result.json"
    if path.exists():
        native = read(path)
        folder = BASE / "diagnostics" / cid
        folder.mkdir(parents=True, exist_ok=False)
        f.write(folder / "check.json", check(inp["question"], [GeneratedClaim(**c) for c in native["claims"]], evidence))
        f.manifest(folder)
    return result


def close():
    with environment():
        return engine.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("init", "send", "close"))
    parser.add_argument("--case-id", choices=[cid for _, cid in SELECTED])
    args = parser.parse_args()
    if args.mode == "send" and args.case_id is None:
        parser.error("--case-id is required")
    policy = f.NetworkPolicy()
    sys.dont_write_bytecode = True
    sys.addaudithook(policy)
    value = initialize() if args.mode == "init" else (send(args.case_id, policy) if args.mode == "send" else close())
    print(json.dumps(value), flush=True)
