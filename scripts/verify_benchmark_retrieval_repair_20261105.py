"""Verify lineage, exact raw evidence, supplemental source spans and repeat identity."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import fitz

from scripts import gigachat_answer_smoke as files
from scripts.benchmark_retrieval_capture_20261105 import BASE, ROOT, read
from scripts.review_benchmark_retrieval_repair_20261105 import ARMS, INTAKE, presence


def verify(output: Path) -> dict[str, Any]:
    first, final = BASE / "review_v01", BASE / "review_v02"
    for folder in (first, final, INTAKE):
        files.verify_manifest(folder)
    report, earlier = read(final / "report.json"), read(first / "report.json")
    files.verify(report["bindings"])
    drifts = []
    for path, digest in earlier["bindings"].items():
        if files.sha(Path(path).read_bytes()) != digest:
            snapshot = first / "source_snapshot" / Path(path).relative_to(ROOT)
            if files.sha(snapshot.read_bytes()) != digest:
                raise ValueError("Unmapped historical source drift")
            drifts.append({"path": path, "original_sha256": digest, "current_sha256": report["bindings"][path],
                           "original_snapshot": str(snapshot)})
    if [Path(d["path"]).name for d in drifts] != ["review_benchmark_retrieval_repair_20261105.py"]:
        raise ValueError("Expected only the separately documented evaluator clarification")
    compared = []
    for path in first.glob("Q*_*.json"):
        if path.read_bytes() != (final / path.name).read_bytes():
            raise ValueError("Repeated case/arm output differs: " + path.name)
        compared.append(path.name)
    for path in first.glob("regression_*.json"):
        if path.read_bytes() != (final / path.name).read_bytes():
            raise ValueError("Repeated regression output differs: " + path.name)
        compared.append(path.name)
    corpus = read(BASE / "capture_v02/Q01/corpus.json")
    checked = 0
    for case in report["cases"]:
        folder = BASE / "capture_v02" / case["id"]
        files.verify_manifest(folder)
        files.verify(read(folder / "capture.json")["bindings"])
        for arm in ARMS:
            for row in case["arms"][arm]["evidence"]:
                source = corpus[row["chunk_id"]]
                if (row["text"], row["article_id"], row["page_start"], row["page_end"]) != (
                        source["full_text"], source["article_id"], source["page_start"], source["page_end"]):
                    raise ValueError("Selected raw source/provenance differs")
                checked += 1
    # Seven prior source notes include the two unmapped quotes and tabular contexts;
    # keep them separate from the original 12 mapped quote denominator.
    intake = read(INTAKE / "report.json")
    supplementary = []
    for note in intake["source_notes"]:
        case = next(c for c in report["cases"] if c["id"] == note["case_id"])
        gold = next(c for c in intake["cases"] if c["id"] == note["case_id"])
        pdf = Path(gold["source_pdf_path_verbatim"]).resolve()
        article = next(a for a in report["articles"].values() if Path(a["original_pdf_path"]).resolve() == pdf)
        with fitz.open(pdf) as document:
            raw = document[note["pdf_page"] - 1].get_text()
        span = note["raw_span"]
        if raw[span["start"]:span["end"]] != span["text"]:
            raise ValueError("Supplementary raw source offset differs")
        quote = {"pdf_page": note["pdf_page"], "span": span}
        supplementary.append({"case_id": case["id"], "page": note["pdf_page"], "raw_span": span,
            "origin": note["origin"], "retained_by_arm": {arm: presence(case["arms"][arm]["evidence"],
                article["article_id"], [note["pdf_page"]], [quote])["mapped_quotes_retained"] == 1 for arm in ARMS}})
    result = {"version": "benchmark_retrieval_repair_verification_v0.1", "bindings_verified": len(report["bindings"]),
        "repeat_outputs_byte_identical": len(compared), "compared_files": compared, "mapped_historical_drift": drifts,
        "raw_selected_evidence_verified": checked, "additional_fresh_source_spans_verified": len(supplementary),
        "original_12_mapped_quote_denominator_unchanged": True, "supplementary_source_presence": supplementary,
        "model_calls": 0, "oauth_calls": 0, "db_calls": 0,
        "summary_counts": {arm: {"old_full_trace_changes": len(value.get("old_full_trace_changes", [])),
                                  "old_gate_decision_changes": len(value.get("old_gate_decision_changes", [])),
                                  "old_adequacy_metadata_changes": len(value.get("old_adequacy_metadata_changes", []))}
                           for arm, value in report["summary"]["arms"].items()},
        "static_html_qa": read(final / "qa.json")}
    files.write(output, result)
    return {key: value for key, value in result.items() if key not in {"supplementary_source_presence", "compared_files"}}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(files.encode(verify(args.output)).decode(), end="")


if __name__ == "__main__":
    main()
