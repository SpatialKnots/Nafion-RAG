"""Verify static review, raw anchors, source redundancy and replay accounting."""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from urllib.request import url2pathname

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import gigachat_answer_smoke as files  # noqa: E402
from scripts.verify_retrieval_window_review import TableAudit  # noqa: E402


def check_span(raw: str, span: dict[str, Any]) -> None:
    if not 0 <= span["start"] < span["end"] <= len(raw) or raw[span["start"] : span["end"]] != span["text"]:
        raise ValueError("Raw span differs")


def verify(folder: Path, junit: Path) -> dict[str, Any]:
    files.verify_manifest(folder)
    report = json.loads((folder / "report.json").read_bytes())
    files.verify(report["bindings"])
    summary = report["summary"]
    if len(report["records"]) != 328 or summary["service_full_trace_replays"] != 328 or summary["diagnostic_executions"] != 656:
        raise ValueError("Incomplete experiment")
    if not summary["corrupted_source_rejected"] or not summary["corrupted_baseline_rejected"]:
        raise ValueError("Missing negative integrity controls")
    if any(summary[key] for key in ("db_calls", "search_calls", "embedding_calls", "model_calls", "oauth_calls", "slot_reservations")):
        raise ValueError("Unexpected operations")
    anchored = 0
    for row in report["records"]:
        if not row["replay"]["full_trace_identical"] or not row["repeated_execution_identical"]:
            raise ValueError("Unverified record")
        analysis = row["analysis"]
        if analysis["scientific_admission"] or not analysis["baseline_preserved"]:
            raise ValueError("Unsupported admission or changed baseline")
        if not analysis["requirements"]["in_scope"]:
            if analysis["textual_requirements_met"] is not None:
                raise ValueError("Outside-scope policy changed")
            continue
        for field in analysis["requirements"]["constraints"]:
            check_span(row["question"], field)
        for source in analysis["sources"]:
            raw = row["full_evidence"][source["evidence_index"]]["text"]
            for region in source["regions"]:
                spans = [region["span"], *region["owner_links"], *region["relation_links"], *region["fields"]]
                spans.extend(span for values in region["role_spans"].values() for span in values)
                if region["antecedent"] is not None:
                    spans.append(region["antecedent"])
                for span in spans:
                    check_span(raw, span)
                    anchored += 1
                if any(region[key] for key in ("performed_established", "material_owner_established", "value_owner_established")):
                    raise ValueError("Unsupported scientific owner assertion")
            for field in source["unassigned_fields"]:
                check_span(raw, field)
                if field["owner_established"]:
                    raise ValueError("Unassigned field has an owner")
        for group in analysis["duplicates"]:
            raw_texts = [row["full_evidence"][index]["text"] for index in group["evidence_indices"]]
            if len(set(raw_texts)) != 1 or files.sha(raw_texts[0].encode()) != group["raw_text_sha256"]:
                raise ValueError("Incorrect raw source duplicate group")
    document = (folder / "review.html").read_text(encoding="utf-8")
    audit = TableAudit()
    audit.feed(document)
    if audit.rows != [8] * 34 or not audit.search_input or 'addEventListener("input"' not in document or "r.hidden=" not in document:
        raise ValueError("Incomplete TAC/search HTML")
    linked = []
    for href in audit.links:
        target = urlsplit(href)
        path = Path(url2pathname(target.path))
        if target.scheme != "file" or path.suffix.lower() != ".pdf" or not path.is_file():
            raise ValueError("Broken original PDF link")
        linked.append(str(path.resolve()))
    expected = {str(Path(article["original_pdf_path"]).resolve()) for article in report["articles"]}
    if len(linked) != 41 or set(linked) != expected:
        raise ValueError("Incomplete original PDF coverage")
    xml = ET.parse(junit).getroot()
    suites = [xml] if xml.tag == "testsuite" else list(xml)
    if any(int(suite.get(key, "0")) for suite in suites for key in ("errors", "failures", "skipped")):
        raise ValueError("Tests failing or incomplete")
    return {
        "static_html_qa": "passed",
        "tac_rows": 33,
        "tac_columns": 8,
        "existing_pdf_links": len(linked),
        "current_bindings_verified": len(report["bindings"]),
        "source_spans_verified": anchored,
        "tests_passed": sum(int(suite.get("tests", "0")) for suite in suites),
        "browser_execution": "not_run",
        "pdf_visual_qa": "not_run",
        "bindings": files.bindings(
            [Path(__file__), ROOT / "scripts/verify_retrieval_window_review.py", folder / "report.json", folder / "manifest.json", junit]
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--junit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.review, args.junit)
    files.write(args.output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
