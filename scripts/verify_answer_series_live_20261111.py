"""Verify closed allowances, immutable native output, source witnesses and review links."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import unquote, urlsplit

from scripts import gigachat_answer_smoke as f
from scripts import run_answer_series_live_20261111 as run
from scripts.verify_answer_series_freeze_20261111 import ReviewParser


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    closed = run.read(run.BASE / "scope_closed_v01.json")
    run.require(closed["remaining_allowance"] == 0 and len(closed["cases"]) == 30
                and closed["model_attempts"] == closed["oauth_attempts"] == 30, "Allowance summary differs")
    for name in ("input_freeze_v01", "review_v01", "review_v02"):
        folder = run.BASE / name
        f.verify_manifest(folder)
        f.verify(run.read(folder / "bindings.json"))
    expected = run.read(run.BASE / "input_freeze_v01/bindings.json")
    app = f.bindings(run.audit.app_paths())
    run.require({k: v for k, v in expected.items() if Path(k).is_relative_to(f.ROOT / "app")} == app,
                "Application differs from tested runtime")
    ledger = run.read(run.BASE / "approval_v01.json")["cases"]
    for case in closed["cases"]:
        cid, path = case["id"], run.BASE / "live" / case["id"]
        prepared = run.BASE / "prepared_v01" / cid
        for folder in (prepared, path):
            f.verify_manifest(folder)
        result = run.read(path / "result.json")
        run.require(result["model_attempts"] == result["oauth_attempts"] == 1 and result["allowance_closed"]
                    and not result["resend_authorized"] and not result["network_denials"]
                    and result["postflight_hashes"] == "verified", "Actual attempt accounting differs")
        digest = next(r["request_sha256"] for r in ledger if r["id"] == cid)
        run.require(f.sha((path / "request.json").read_bytes()) == digest
                    and (path / "request.json").read_bytes() == (prepared / "request.json").read_bytes()
                    and result == run.read(run.LEDGER / digest / "result.json"), "Sent native or ledger differs")
        run.require(f.sha((path / "response.bin").read_bytes()) == result["observed_response_sha256"]
                    == result["stored_response_sha256"] and not result["credential_redaction_applied"],
                    "Original native response was modified")
    witnesses = 0
    notes = run.read(run.BASE / "posthoc_source_review_v01.json")
    for cid, note in notes.items():
        sources = {e["citation_id"]: e for e in run.read(run.BASE / "prepared_v01" / cid / "trace.json")["evidence"]}
        for anchor in note.get("source_witnesses", []):
            source = sources[anchor["citation_id"]]
            run.require(source["text"][anchor["start"]:anchor["end"]] == anchor["text"]
                        and f.sha(source["text"].encode()) == anchor["raw_sha256"]
                        and source["article_id"] == anchor["article_id"] and source["chunk_id"] == anchor["chunk_id"],
                        "Post-hoc raw witness differs")
            witnesses += 1
    run.require(witnesses == 15, "Source witness count changed")
    review = run.BASE / "review_v02"
    report = run.read(review / "report.json")
    summary = report["summary"]
    run.require(summary["counts"]["HTTP:200"] == 23 and summary["counts"]["HTTP:502"] == 7
                and summary["saved_response_API_replays_exact"] == 30, "Observed outcomes differ")
    parsed = ReviewParser()
    parsed.feed((review / "review.html").read_text(encoding="utf-8"))
    run.require(parsed.rows == {1: 31, 2: 4} and parsed.headers == {1: 5, 2: 8} and parsed.search,
                "HTML rows/columns/search differ")
    for href in parsed.links:
        url = urlsplit(href)
        run.require(not url.scheme and not url.netloc and (review / unquote(url.path)).is_file(), "Broken review link")
    value = {"cases": 30, "actual_model_attempts": 30, "actual_oauth_attempts": 30, "remaining_allowance": 0,
        "native_requests_exact": 30, "original_responses_exact": 30, "exclusive_ledger_results_exact": 30,
        "runtime_app_files_exact": len(app), "posthoc_raw_witnesses": witnesses,
        "HTML_case_rows": 30, "HTML_article_rows": 3, "TAC_columns": 8, "HTML_links_existing": len(parsed.links),
        "HTML_details": parsed.details, "new_model_calls_during_verification": 0, "scientific_accuracy": None,
        "plan_percent": 75}
    f.write(out / "result.json", value)
    f.write(out / "bindings.json", f.bindings([Path(__file__), run.SCOPE, run.BASE / "scope_closed_v01.json",
        run.BASE / "duplicate_ID_diagnosis_v01.json", review / "manifest.json", f.ROOT / "AGENTS.md"]))
    f.manifest(out)
    print(json.dumps(value), flush=True)


if __name__ == "__main__":
    main()
