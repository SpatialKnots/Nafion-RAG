"""Verify current runtime, preserved historical bindings and fresh read-only traces."""

from __future__ import annotations

import argparse
import ast
from pathlib import Path
from typing import Any

import fitz

from scripts import gigachat_answer_smoke as files
from scripts.benchmark_retrieval_capture_20261105 import read
from scripts.check_requested_context_runtime_20261105 import BASE, INTAKE, ROOT
from scripts.review_benchmark_retrieval_repair_20261105 import presence


def verify(output: Path) -> dict[str, Any]:
    review = BASE / "review_v01"
    files.verify_manifest(review)
    files.verify_manifest(BASE / "freeze_v01")
    report = read(review / "report.json")
    mapped_style = []
    for name, digest in report["bindings"].items():
        if files.sha(Path(name).read_bytes()) == digest:
            continue
        if Path(name).name != "check_requested_context_runtime_20261105.py":
            raise ValueError("Unexpected current binding drift: " + name)
        snapshot = review / "source_snapshot" / Path(name).relative_to(ROOT)
        if (files.sha(snapshot.read_bytes()) != digest or ast.dump(ast.parse(snapshot.read_text(encoding="utf-8")))
                != ast.dump(ast.parse(Path(name).read_text(encoding="utf-8")))):
            raise ValueError("Reviewer change is not a formatting-only AST equivalent")
        mapped_style.append({"path": name, "original_sha256": digest, "current_sha256": files.sha(Path(name).read_bytes()),
                             "snapshot": str(snapshot), "ast_identical": True})
    old = read(BASE / "freeze_v01/runtime.json")["bindings"]
    for name, digest in old.items():
        if name in report["summary"]["old_runtime_drift"]:
            snapshot = BASE / "freeze_v01/source_snapshot" / Path(name).relative_to(ROOT)
            if files.sha(snapshot.read_bytes()) != digest:
                raise ValueError("Historical runtime snapshot changed")
        elif files.sha(Path(name).read_bytes()) != digest:
            raise ValueError("Unmapped runtime drift")
    fresh = []
    for case_id in ("Q03", "Q04"):
        folder = BASE / "fresh_v01" / case_id
        files.verify_manifest(folder)
        capture = read(folder / "capture.json")
        files.verify(capture["bindings"])
        if read(folder / "boundaries.json")["trace"] != read(review / f"{case_id}_repaired.json")["trace"]:
            raise ValueError("Fresh actual search differs from offline repaired trace")
        if (capture["transaction_read_only"], capture["transaction_end"], capture["model_calls"], capture["oauth_calls"],
                capture["slots"], capture["network_denials"], capture["gold_read_denials"]) != ("on", "rollback", 0, 0, 0, [], []):
            raise ValueError("Fresh preparation exceeded read-only question-only scope")
        fresh.append({"case_id": case_id, "complete_trace_identical_to_offline": True, "transaction_read_only": "on",
                      "transaction_end": "rollback"})
    files.verify_manifest(INTAKE)
    gold = read(INTAKE / "report.json")
    pages, spans = 0, 0
    supplementary = []
    for case in gold["cases"]:
        target = next(a for a in report["articles"].values() if Path(a["original_pdf_path"]).resolve()
                      == Path(case["source_pdf_path_verbatim"]).resolve())
        with fitz.open(target["original_pdf_path"]) as document:
            for item in (p for p in gold["source_pages"] if p["case_id"] == case["id"]):
                raw = document[item["pdf_page"] - 1].get_text()
                if files.sha(raw.encode()) != item["sha256"]:
                    raise ValueError("Fresh original page differs")
                pages += 1
                for quote in case["quotes"]:
                    if quote["span"] is not None and quote["pdf_page"] == item["pdf_page"]:
                        span = quote["span"]
                        if raw[span["start"]:span["end"]] != span["text"]:
                            raise ValueError("Mapped source quote offsets differ")
                        spans += 1
                for note in gold["source_notes"]:
                    if note["case_id"] == case["id"] and note["pdf_page"] == item["pdf_page"]:
                        span = note["raw_span"]
                        if raw[span["start"]:span["end"]] != span["text"]:
                            raise ValueError("Supplementary source offsets differ")
                        spans += 1
                        repaired = next(c for c in report["cases"] if c["id"] == case["id"])
                        supplementary.append({"case_id": case["id"], "page": item["pdf_page"], "raw_span": span,
                            "origin": note["origin"], "retained": presence(repaired["repaired"]["evidence"], target["article_id"],
                                [item["pdf_page"]], [{"pdf_page": item["pdf_page"], "span": span}])["mapped_quotes_retained"] == 1})
    result = {"version": "requested_context_runtime_verification_v0.1", "review_bindings": len(report["bindings"]),
              "mapped_reviewer_formatting_change": mapped_style, "fresh_trace_checks": fresh,
              "fresh_original_pages": pages, "fresh_raw_spans": spans, "source_note_retention": supplementary,
              "real_model_calls": 0, "oauth_calls": 0, "slots": 0,
              "static_html_qa": read(review / "qa.json")}
    files.write(output, result)
    return {k: v for k, v in result.items() if k != "source_note_retention"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(files.encode(verify(args.output)).decode(), end="")


if __name__ == "__main__":
    main()
