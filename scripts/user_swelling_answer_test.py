"""One verbatim user question through the unchanged current /answer route."""

from __future__ import annotations

import argparse
import json
import sys
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import gigachat_answer_smoke as smoke  # noqa: E402

VERSION = "user_swelling_answer_test_v0.1"
QUESTION = "Какая максимальная степень набухания Li-Nafion при комнатной температуре задокументирована?"
BASE = ROOT / "output/user_swelling_answer_20261029"
PROTOCOL = ROOT / "docs/records/user_swelling_answer_test_v0.1.md"


@contextmanager
def scope():
    with patch.object(smoke, "QUESTION", QUESTION), patch.object(smoke, "VERSION", VERSION), patch.object(smoke, "PROTOCOL", PROTOCOL):
        yield


def prepare(policy: smoke.NetworkPolicy) -> dict:
    BASE.mkdir(parents=True, exist_ok=False)
    with scope():
        result = smoke.prepare(BASE / "prepared", policy)
    contract = json.loads((BASE / "prepared/contract.json").read_bytes())
    bindings = {**contract["input_bindings"], **smoke.bindings([
        Path(__file__), PROTOCOL, ROOT / "tests/unit/test_user_swelling_answer_test.py",
        BASE / "prepared/manifest.json", BASE / "prepared/contract.json",
        ROOT / "output/user_swelling_preflight_20261029_v01.xml"])}
    snapshot = BASE / "source_snapshot"
    for name, digest in bindings.items():
        source = Path(name)
        if source.is_relative_to(ROOT) and source.suffix in {".py", ".md", ".json", ".yaml"} and source.relative_to(ROOT).parts[0] in {
                "app", "scripts", "tests", "docs"}:
            target = snapshot / source.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            raw = source.read_bytes()
            if smoke.sha(raw) != digest:
                raise ValueError("Source changed during snapshot")
            smoke.save(target, raw)
    smoke.manifest(snapshot)
    bindings.update(smoke.bindings([snapshot / "manifest.json"]))
    smoke.verify(bindings)
    smoke.write(BASE / "study_contract.json", {"version": VERSION, "question": QUESTION, "bindings": bindings,
        "authorization": "user_requested_current_system_end_to_end_test_and_supplied_this_question",
        "maximum_model_attempts": 1, "maximum_oauth_attempts": 1, "automatic_retries": 0, "fallbacks": 0,
        "generation_reached": result["generation_reached"], "request_sha256": result["request_sha256"],
        "scientific_acceptance": "not_evaluated"})
    return result


def read_study() -> dict:
    study = json.loads((BASE / "study_contract.json").read_bytes())
    if (study["version"], study["question"], study["maximum_model_attempts"], study["maximum_oauth_attempts"],
            study["automatic_retries"], study["fallbacks"]) != (VERSION, QUESTION, 1, 1, 0, 0):
        raise ValueError("Frozen user question or budget differs")
    smoke.verify(study["bindings"])
    smoke.verify_manifest(BASE / "prepared")
    smoke.verify_manifest(BASE / "source_snapshot")
    return study


def send(policy: smoke.NetworkPolicy, *, authorized: bool) -> dict:
    if not authorized:
        raise ValueError("Explicit authorization for one live user-question request required")
    study = read_study()
    if not study["generation_reached"]:
        raise ValueError("Production gate ended this test; generation forbidden")
    smoke.write(BASE / "dispatch_started.json", {"version": VERSION,
        "study_sha256": smoke.sha((BASE / "study_contract.json").read_bytes()), "maximum_model_attempts": 1,
        "maximum_oauth_attempts": 1, "automatic_retries": 0})
    with scope():
        result = smoke.send(BASE / "prepared", BASE / "live", policy)
    smoke.verify(study["bindings"])
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "send", "review"))
    parser.add_argument("--authorize-one-live-call", action="store_true")
    args = parser.parse_args()
    policy = smoke.NetworkPolicy()
    sys.addaudithook(policy)
    if args.mode == "prepare":
        result = prepare(policy)
    elif args.mode == "send":
        raw = send(policy, authorized=args.authorize_one_live_call)
        result = {k: raw.get(k) for k in ("status", "http_status", "model_attempts", "oauth_attempts", "usage", "error_type", "error")}
    else:
        read_study()
        with scope():
            result = smoke.review(BASE / "prepared", BASE / "live", BASE / "review_v01")
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
