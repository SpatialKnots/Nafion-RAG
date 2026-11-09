"""Finalize saved context results; no DB, provider or retrieval execution."""

from __future__ import annotations

import argparse
import copy
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import fitz

from scripts import gigachat_answer_smoke as files
from scripts.benchmark_retrieval_capture_20261105 import read
from scripts.check_condition_context_20261106 import BASE, validate_added
from scripts.check_requested_context_runtime_20261105 import render
from scripts.review_benchmark_retrieval_repair_20261105 import check_html


def verify_current(bindings, old_source):
    drift = []
    for name, expected in bindings.items():
        path = Path(name)
        actual = files.sha(path.read_bytes())
        if actual == expected:
            continue
        if path.resolve() != (files.ROOT / "app/generation/context_completion.py").resolve():
            raise ValueError("Unexpected current binding drift: " + name)
        before = old_source.read_bytes()
        if files.sha(before) != expected:
            raise ValueError("Historical code snapshot does not bind changed source")
        text = before.decode().replace("    candidates = []", "    candidates: list[tuple[SearchResult, dict[str, Any]]] = []")
        if text.encode() != path.read_bytes():
            raise ValueError("Context implementation changed beyond the declared type annotation")
        drift.append({"path": name, "historical_sha256": expected, "current_sha256": actual,
                      "snapshot": str(old_source), "reason": "type_annotation_only_no_runtime_change"})
    return drift


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    for folder in ("freeze_v02", "candidate_v01", "candidate_v02", "review_v02", "fresh_v02/Q03", "fresh_v03/Q03"):
        files.verify_manifest(BASE / folder)
    source = BASE / "review_v02"
    old_source = BASE / "candidate_v02/snapshot/app/generation/context_completion.py"
    report = read(source / "report.json")
    drift = verify_current(report["bindings"], old_source)
    fresh = BASE / "fresh_v03/Q03"
    contract, trace = read(fresh / "contract.json"), read(fresh / "trace.json")
    drift += verify_current(contract["input_bindings"], old_source)
    if trace != read(source / "Q03_repaired.json")["trace"]:
        raise ValueError("Fresh full trace differs")
    native = (fresh / "request.json").read_bytes()
    if native != (source / "Q03_native_unsent.json").read_bytes() or files.sha(native) != contract["request_sha256"]:
        raise ValueError("Fresh native body differs")
    if any(contract[k] for k in ("model_calls", "oauth_calls", "new_slots", "network_denials", "gold_read_denials")):
        raise ValueError("Fresh preparation exceeded zero live scope")
    if (contract["transaction_read_only"], contract["transaction_end"]) != ("on", "rollback"):
        raise ValueError("Read-only rollback not recorded")
    registry = read(fresh / "sources.json")
    if registry["diagnostics"]:
        raise ValueError("Source registry diagnostics")
    for region in registry["pages"].values():
        with fitz.open(region["layer_pdf_path"]) as pdf:
            raw = pdf[region["page_number"] - 1].get_text()
        if raw != region["page_text"] or files.sha(raw.encode()) != region["page_text_sha256"]:
            raise ValueError("Fresh selected PDF page changed")
        if raw[region["start"]:region["end"]] != region["quote"]:
            raise ValueError("Selected page raw quote changed")
    corpus = read(files.ROOT / "output/benchmark_retrieval_repair_20261105/capture_v02/Q01/corpus.json")
    for chunk_id, row in registry["chunks"].items():
        if row["text"] != corpus[chunk_id]["full_text"]:
            raise ValueError("Fresh DB raw chunk differs from frozen inventory")
    if validate_added(trace, corpus, fresh / "request.json") != 1:
        raise ValueError("New context not bound in actual native prompt")
    suite = ET.parse(BASE / "tests_affected_v01.xml").getroot()
    tests = sum(int(s.attrib["tests"]) for s in suite.findall("testsuite"))
    failed = sum(int(s.attrib[k]) for s in suite.findall("testsuite") for k in ("failures", "errors", "skipped"))
    scope = read(BASE / "tests_affected_v01.scope.json")
    files.verify(scope["test_bindings"])
    if tests != 581 or failed or scope["exit_code"] or scope["external_network_denials"]:
        raise ValueError("Affected test scope not clean")
    checked = ["app/generation/context_completion.py", "app/generation/fact_types.py", "app/generation/service.py",
        "tests/unit/test_context_completion.py", "tests/unit/test_condition_context_service.py",
        "tests/unit/test_requested_context_service.py", "scripts/check_condition_context_20261106.py",
        "scripts/capture_condition_context_20261106.py", "scripts/test_condition_context_20261106.py",
        "scripts/verify_condition_context_20261106.py"]
    for label, args in (("ruff", ["ruff", "check", *checked]), ("mypy", ["mypy", "app"])):
        result = subprocess.run([sys.executable, "-m", *args], cwd=files.ROOT, capture_output=True, text=True)
        files.save(output / f"{label}.log", (result.stdout + result.stderr).encode())
        if result.returncode:
            raise ValueError(label + " failed; inspect saved log")
    verification = {"affected_tests": tests, "external_network_denials": [], "ruff_files": len(checked),
        "mypy_app_sources": 191, "fresh_selected_pages": len(registry["pages"]),
        "fresh_db_chunks": len(registry["chunks"]), "fresh_trace_native_equal": True,
        "fresh_native_bytes": len(native), "fresh_native_sha256": files.sha(native),
        "historical_bindings_checked": len(report["bindings"]), "historical_drift_map": drift,
        "real_model_calls": 0, "real_oauth_calls": 0, "new_slots": 0,
        "unperformed": ["browser", "PDF visual QA", "full suite", "concurrency", "deployment", "independent scientific evaluation"]}
    report = copy.deepcopy(report)
    report["summary"]["verification"] = verification
    for case in report["cases"]:
        for arm in ("baseline", "repaired"):
            case[arm]["presence_scope"] = "server_raw_parent_inventory_not_scientific_accuracy"
    document = render(report).replace("Сохранение запрошенного контекста в runtime", "Добор контекста условий v0.2")
    qa = check_html(document, article_count=len(report["articles"]), case_count=5)
    docs = ["AGENTS.md", "docs/condition_context_completion_2026-11-06.md", "docs/answer_quality_progress_2026-10-30.md",
            "docs/records/condition_context_completion_protocol_2026-11-06_v0.1.md",
            "docs/records/condition_context_completion_amendment_2026-11-06_v0.2.md"]
    bindings = files.bindings([*map(lambda p: files.ROOT / p, [*checked, *docs]),
        *[BASE / name for name in ("tests_affected_v01.xml", "tests_affected_v01.scope.json", "review_v02/manifest.json",
                                   "fresh_v03/Q03/manifest.json", "candidate_v02/manifest.json")]])
    files.verify(bindings)
    files.write(output / "current_bindings.json", bindings)
    files.write(output / "verification.json", verification)
    files.write(output / "qa.json", qa)
    files.write(output / "report.json", report)
    files.save(output / "review.html", document.encode())
    files.manifest(output)
    return {"verification": verification, "qa": qa}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    policy = files.NetworkPolicy()
    sys.addaudithook(policy)
    result = run(args.output)
    if policy.denied:
        raise ValueError("Unexpected network attempt")
    print(json.dumps(result, ensure_ascii=True, indent=2), flush=True)


if __name__ == "__main__":
    main()
