"""Bounded four-question wrapper around the unchanged production smoke path."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import gigachat_answer_smoke as smoke  # noqa: E402

VERSION = "gigachat_answer_batch_v0.2"
PROTOCOL = ROOT / "docs/records/gigachat_answer_batch_protocol_v0.2.md"
CASES = ROOT / "docs/records/gigachat_answer_batch_cases_v0.1.json"


def load_cases() -> list[dict[str, Any]]:
    value = json.loads(CASES.read_bytes())
    cases = value["cases"]
    if (value["version"] != "gigachat_answer_batch_v0.1" or len(cases) != 4 or len({c["id"] for c in cases}) != 4
            or any(not c["question"].strip() or c["id"] != Path(c["id"]).name for c in cases)):
        raise ValueError("Expected exactly four distinct prospectively declared question cases")
    return cases


@contextmanager
def case_scope(case: dict[str, Any]):
    # Only the development runner's process-local question/provenance change.
    with patch.object(smoke, "QUESTION", case["question"]), patch.object(smoke, "PROTOCOL", PROTOCOL):
        yield


def worker(mode: str, root: Path, case: dict[str, Any], policy: smoke.NetworkPolicy, *, authorized: bool) -> dict[str, Any]:
    from sqlalchemy.exc import SQLAlchemyError
    from sqlalchemy.orm.exc import DetachedInstanceError

    folder = root / "cases" / case["id"] / "prepared"
    row = dict(case)
    try:
        with case_scope(case):
            if mode == "prepare":
                value = smoke.prepare(folder, policy)
                row.update(preparation_status="ready" if value["generation_reached"] else "gate_rejected",
                           request_sha256=value["request_sha256"], request_bytes=value["request_bytes"],
                           prepared=str(folder.resolve()))
            else:
                if not authorized or not (root / "dispatch_started.json").is_file():
                    raise ValueError("Send worker requires the parent's authorized frozen dispatch")
                frozen = read_batch(root)
                declared = next(c for c in frozen["cases"] if c["id"] == case["id"])
                if declared["preparation_status"] != "ready":
                    raise ValueError("Only a frozen ready case may be dispatched")
                result = smoke.send(Path(declared["prepared"]), folder.parent / "live", policy)
                row = {"id": case["id"], **{k: result.get(k) for k in (
                    "status", "http_status", "model_attempts", "oauth_attempts", "usage", "error_type", "error")}}
    except (OSError, ValueError, RuntimeError, SQLAlchemyError) as exc:
        message = str(exc) if not isinstance(exc, SQLAlchemyError) or isinstance(exc, DetachedInstanceError) else (
            "Database preparation failed; see exception type")
        row.update(preparation_status="preparation_failed", status="worker_failed", error_type=type(exc).__name__,
                   error=message, prepared=str(folder.resolve()), model_attempts=None, oauth_attempts=None)
    folder.parent.mkdir(parents=True, exist_ok=True)
    smoke.write(folder.parent / (mode + "_worker_result.json"), row)
    return row


def run_worker(mode: str, root: Path, case: dict[str, Any]) -> dict[str, Any]:
    from app.core.config import Settings

    command = [sys.executable, "-B", "-X", "utf8", str(Path(__file__).resolve()), mode,
               "--root", str(root.resolve()), "--worker", "--case-id", case["id"]]
    if mode == "send":
        command.append("--authorize-four-case-gigachat-batch")
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, encoding="utf-8", check=False)
    settings = Settings()
    logs = {"stdout": completed.stdout, "stderr": completed.stderr}
    folder = root / "cases" / case["id"]
    folder.mkdir(parents=True, exist_ok=True)
    for label, content in logs.items():
        for secret in (settings.gigachat_credentials, settings.database_url):
            if secret:
                content = content.replace(secret, "[REDACTED]")
        smoke.save(folder / (mode + "_worker_" + label + ".txt"), content.encode("utf-8"))
    if completed.returncode:
        return {**case, "preparation_status": "preparation_failed", "status": "worker_failed",
                "error_type": "WorkerProcessError", "returncode": completed.returncode,
                "model_attempts": None, "oauth_attempts": None, "prepared": str((folder / "prepared").resolve())}
    value = json.loads((folder / (mode + "_worker_result.json")).read_bytes())
    if value["id"] != case["id"]:
        raise ValueError("Worker returned a different case identity")
    return value


def prepare(root: Path, policy: smoke.NetworkPolicy) -> dict[str, Any]:

    cases = load_cases()
    root.mkdir(parents=True, exist_ok=False)
    smoke.save(root / "questions.json", CASES.read_bytes())
    inputs = smoke.bindings([PROTOCOL, ROOT / "docs/records/gigachat_answer_batch_protocol_v0.1.md",
                             CASES, Path(__file__), ROOT / "tests/unit/test_gigachat_answer_batch.py"])
    rows = []
    for case in cases:
        folder = root / "cases" / case["id"] / "prepared"
        row = run_worker("prepare", root, case)
        if row["preparation_status"] in {"ready", "gate_rejected"}:
            contract = json.loads((folder / "contract.json").read_bytes())
            for path, digest in contract["input_bindings"].items():
                if path in inputs and inputs[path] != digest:
                    raise ValueError("Conflicting current source/code bindings: " + path)
                inputs[path] = digest
            inputs.update(smoke.bindings([folder / "manifest.json", folder / "contract.json"]))
        else:
            smoke.write(folder.parent / "preparation_error.json", row)
        rows.append(row)
        print(json.dumps({k: row.get(k) for k in ("id", "preparation_status", "request_bytes", "error_type")}), flush=True)
    smoke.verify(inputs)
    snapshot = root / "source_snapshot"
    snapshot.mkdir(exist_ok=False)
    archived = 0
    for name, digest in inputs.items():
        path = Path(name)
        if not path.is_relative_to(ROOT):
            continue
        relative = path.relative_to(ROOT)
        if (relative.parts[0] not in {"app", "scripts", "tests", "docs", "pyproject.toml"}
                or path.suffix not in {".py", ".yaml", ".toml", ".md", ".json"}):
            continue
        target = snapshot / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        raw = path.read_bytes()
        if smoke.sha(raw) != digest:
            raise ValueError("Source changed during snapshot: " + name)
        smoke.save(target, raw)
        archived += 1
    smoke.manifest(snapshot)
    inputs.update(smoke.bindings([snapshot / "manifest.json", root / "questions.json"]))
    smoke.write(root / "batch_contract.json", {"version": VERSION, "frozen_at_utc": datetime.now(UTC).isoformat(),
        "authorization": "user_continue_testing_2026-10-29", "cases": rows, "bindings": inputs,
        "maximum_model_attempts": 4, "maximum_oauth_attempts": 4, "max_output_tokens_per_request": 1200,
        "automatic_retries": 0, "fallbacks": 0, "archived_source_files": archived,
        "new_model_calls": 0, "scientific_acceptance": "not_evaluated", "independent_accuracy": None})
    return {"cases": len(rows), "preparation_statuses": dict(Counter(r["preparation_status"] for r in rows)),
            "archived_source_files": archived, "new_model_calls": 0}


def read_batch(root: Path) -> dict[str, Any]:
    value = json.loads((root / "batch_contract.json").read_bytes())
    if value["version"] != VERSION or len(value["cases"]) != 4 or value["maximum_model_attempts"] != 4:
        raise ValueError("Frozen batch scope/budget differs")
    smoke.verify(value["bindings"])
    smoke.verify_manifest(root / "source_snapshot")
    frozen_cases = json.loads((root / "questions.json").read_bytes())["cases"]
    if [{k: c[k] for k in original} for c, original in zip(value["cases"], frozen_cases, strict=True)] != frozen_cases:
        raise ValueError("Frozen case questions/rules differ")
    for case in value["cases"]:
        if case["preparation_status"] in {"ready", "gate_rejected"}:
            smoke.verify_manifest(Path(case["prepared"]))
    return value


def send(root: Path, policy: smoke.NetworkPolicy, *, authorized: bool = False) -> dict[str, Any]:
    if not authorized:
        raise ValueError("Explicit authorization for the bounded four-case batch is required")
    frozen = read_batch(root)
    smoke.write(root / "dispatch_started.json", {"version": VERSION, "started_at_utc": datetime.now(UTC).isoformat(),
        "batch_contract_sha256": smoke.sha((root / "batch_contract.json").read_bytes()),
        "maximum_model_attempts": 4, "maximum_oauth_attempts": 4})
    rows = []
    for case in frozen["cases"]:
        if case["preparation_status"] != "ready":
            row = {"id": case["id"], "status": case["preparation_status"], "model_attempts": 0, "oauth_attempts": 0}
        else:
            row = run_worker("send", root, case)
        rows.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
    model_calls = sum(r.get("model_attempts") or 0 for r in rows)
    oauth_calls = sum(r.get("oauth_attempts") or 0 for r in rows)
    if model_calls > 4 or oauth_calls > 4:
        raise ValueError("Declared batch budget exceeded")
    summary = {"version": VERSION, "total_cases": 4, "cases": rows, "actual_model_attempts": model_calls,
               "actual_oauth_attempts": oauth_calls, "automatic_retries": 0, "fallbacks": 0,
               "unresolved_worker_outcomes": [r["id"] for r in rows if r.get("model_attempts") is None],
               "completed_at_utc": datetime.now(UTC).isoformat(), "scientific_acceptance": "not_evaluated"}
    smoke.write(root / "dispatch_summary.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "send"))
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--authorize-four-case-gigachat-batch", action="store_true")
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--case-id")
    args = parser.parse_args()
    policy = smoke.NetworkPolicy()
    sys.addaudithook(policy)
    if args.worker:
        cases = [c for c in load_cases() if c["id"] == args.case_id]
        if len(cases) != 1:
            parser.error("Worker requires one declared --case-id")
        result = worker(args.mode, args.root, cases[0], policy, authorized=args.authorize_four_case_gigachat_batch)
    else:
        result = prepare(args.root, policy) if args.mode == "prepare" else send(
            args.root, policy, authorized=args.authorize_four_case_gigachat_batch)
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
