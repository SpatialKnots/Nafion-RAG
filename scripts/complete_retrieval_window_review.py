"""Add before/after raw evidence and explicit displaced-source accounting.

Presentation/accounting only: do not rerun or change the frozen experiment.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import gigachat_answer_smoke as files  # noqa: E402
from scripts.run_retrieval_window_selection import CAPTURE, QUALIFIERS, render  # noqa: E402


def source_delta(before: list[dict[str, Any]], after: list[dict[str, Any]]) -> dict[str, Any]:
    def identity(row: dict[str, Any]) -> tuple[str, str, str]:
        return row["article_id"], row["chunk_id"], files.sha(row["text"].encode("utf-8"))

    old = {identity(row): row for row in before}
    new = {identity(row): row for row in after}
    return {
        "removed_raw_evidence": [row for key, row in old.items() if key not in new],
        "added_raw_evidence": [row for key, row in new.items() if key not in old],
        "removed_article_ids": sorted({row["article_id"] for row in before} - {row["article_id"] for row in after}),
        "added_article_ids": sorted({row["article_id"] for row in after} - {row["article_id"] for row in before}),
        "scope": "Source displacement, not scientific harm/benefit; unknown relevance is not a negative label",
    }


def complete(source: Path, output: Path) -> dict[str, Any]:
    files.verify_manifest(source)
    report = json.loads((source / "report.json").read_bytes())
    files.verify(report["bindings"])
    report = copy.deepcopy(report)
    recipe = json.loads((CAPTURE / "cases.json").read_bytes())
    indices = {case["id"]: index for index, case in enumerate(recipe["cases"])}
    comparisons = {(row["case_id"], row["arm"], row["qualifier"]): row for row in report["comparisons"]}
    for record in report["scoped_records"]:
        filename = CAPTURE / f"cases/{indices[record['case_id']]:03d}_{record['arm']}.json"
        baseline = json.loads(filename.read_bytes())
        record["baseline_trace"] = baseline["trace"]
        record["baseline_capture_path"] = str(filename.resolve())
        delta = source_delta(baseline["trace"]["evidence"], record["trace"]["evidence"])
        record["source_displacement"] = delta
        comparisons[record["case_id"], record["arm"], record["qualifier"]]["source_displacement"] = delta
    report["summary"]["source_displacement"] = {
        qualifier: [
            {
                "case_id": row["case_id"],
                "arm": row["arm"],
                "removed_raw_evidence_count": len(row["source_displacement"]["removed_raw_evidence"]),
                "added_raw_evidence_count": len(row["source_displacement"]["added_raw_evidence"]),
                "removed_article_ids": row["source_displacement"]["removed_article_ids"],
                "added_article_ids": row["source_displacement"]["added_article_ids"],
            }
            for row in report["comparisons"]
            if row["qualifier"] == qualifier
            and row.get("source_displacement")
            and (row["source_displacement"]["removed_raw_evidence"] or row["source_displacement"]["added_raw_evidence"])
        ]
        for qualifier in QUALIFIERS
    }
    report["presentation_amendment"] = "v0.1: before/after full traces and all displaced source fragments added; no rerun or metric change"
    report["bindings"].update(files.bindings([Path(__file__), source / "report.json", source / "manifest.json"]))
    files.verify(report["bindings"])
    output.mkdir(parents=True, exist_ok=False)
    destination = output / "source_snapshot"
    destination.mkdir()
    files.save(destination / Path(__file__).name, Path(__file__).read_bytes())
    files.write(output / "report.json", report)
    render(report, output)
    files.manifest(output)
    return report["summary"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(complete(args.source, args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
