"""Verify exact graph anchors and separate partial/full accounting."""

from __future__ import annotations

import argparse
import hashlib
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
from scripts.verify_cross_lingual_relation_review import check_span  # noqa: E402
from scripts.verify_retrieval_window_review import TableAudit  # noqa: E402


def check_graph(analysis: dict[str, Any], sources: list[dict[str, Any]]) -> int:
    if analysis["scientific_admission"] or not analysis["baseline_preserved"]:
        raise ValueError("Unsupported admission or changed baseline")
    if not analysis["requirements"]["in_scope"]:
        if analysis["textual_requirements_met"] is not None or analysis["partial_relations"]:
            raise ValueError("Outside scope assessment changed")
        return 0
    complete = any(edge["complete_requirements"] for edge in analysis["partial_relations"])
    if complete != analysis["textual_requirements_met"]:
        raise ValueError("Partial and full requirements conflated")
    count = 0
    for source in analysis["typed_sources"]:
        raw = sources[source["evidence_index"]]["text"]
        for unit in source["units"]:
            spans = [unit["span"]]
            for node in unit["variables"]:
                spans.append(node["span"])
                spans.extend(component["span"] for component in node["components"])
                if node["value_owner_established"] or node["chemical_identity_established"]:
                    raise ValueError("Variable owner/identity was invented")
            for edge in unit["edges"]:
                spans.extend([edge["span"], edge["property_span"], edge["predicate_span"], *edge["target_attachment"]])
                if edge["antecedent"] is not None:
                    spans.append(edge["antecedent"])
                if any(
                    edge[name]
                    for name in ("scientific_admission", "performed_established", "material_owner_established", "value_owner_established")
                ):
                    raise ValueError("Scientific owner/admission was invented")
            for span in spans:
                check_span(raw, span)
                count += 1
    for group in analysis["exact_relation_groups"]:
        digests = set()
        for address in group["addresses"]:
            source = next(source for source in analysis["typed_sources"] if source["evidence_index"] == address["evidence_index"])
            unit = next(unit for unit in source["units"] if unit["region_index"] == address["region_index"])
            edge = unit["edges"][address["edge_index"]]
            if not edge["partial_relation"]:
                raise ValueError("Blocked edge counted as partial")
            digests.add(
                hashlib.sha256((edge["span"]["text"] + "\0" + edge["variable"]["kind"] + "\0" + edge["direction"]).encode()).hexdigest()
            )
        if digests != {group["raw_relation_sha256"]}:
            raise ValueError("Exact relation duplicate group differs")
    return count


def verify(folder: Path, junit: Path) -> dict[str, Any]:
    import fitz

    files.verify_manifest(folder)
    report = json.loads((folder / "report.json").read_bytes())
    files.verify(report["bindings"])
    summary = report["summary"]
    if summary["service_full_trace_replays"] != 328 or summary["arm_diagnostic_executions"] != 1968:
        raise ValueError("Incomplete declared comparison")
    if not summary["corrupted_source_rejected"] or not summary["corrupted_baseline_rejected"]:
        raise ValueError("Missing negative integrity controls")
    if any(summary[key] for key in ("db_calls", "search_calls", "embedding_calls", "model_calls", "oauth_calls", "slot_reservations")):
        raise ValueError("Unexpected operation")
    anchored = 0
    for row in report["records"]:
        if not row["replay"]["full_trace_identical"] or not row["repeated_execution_identical"]:
            raise ValueError("Missing real replay/repeat")
        anchored += check_graph(row["analysis"], row["full_evidence"] or [])
    dataset = json.loads((ROOT / "docs/records/typed_partial_real_cases_v0.2.json").read_bytes())
    files.verify(dataset["bindings"])
    articles = {article["article_id"]: article for article in report["articles"]}
    for case in dataset["cases"]:
        check_span(case["parent_text"], case["raw_span"])
        if files.sha(case["parent_text"].encode()) != case["parent_sha256"]:
            raise ValueError("Real parent text changed")
        source = case["provenance"]
        article = articles[source["article_id"]]
        with fitz.open(article["original_pdf_path"]) as pdf:
            pages = [pdf[index - 1].get_text() for index in range(source["page_start"], source["page_end"] + 1)]
        # Exact containment only; do not normalize source to force a match.
        if not any(case["raw_span"]["text"] in page for page in [*pages, "\n".join(pages), "\n\n".join(pages)]):
            raise ValueError("Fresh real development window differs: " + case["id"])
    raw = (folder / "review.html").read_text(encoding="utf-8")
    table = TableAudit()
    table.feed(raw)
    if table.rows != [8] * 34 or not table.search_input or "r.hidden=" not in raw or '<table id="partial">' not in raw:
        raise ValueError("Incomplete TAC/partial/search HTML")
    paths = []
    for href in table.links:
        url = urlsplit(href)
        path = Path(url2pathname(url.path))
        if url.scheme != "file" or path.suffix.lower() != ".pdf" or not path.is_file():
            raise ValueError("Broken original source link")
        paths.append(str(path.resolve()))
    if len(paths) != 41 or set(paths) != {str(Path(article["original_pdf_path"]).resolve()) for article in report["articles"]}:
        raise ValueError("Source link coverage differs")
    xml = ET.parse(junit).getroot()
    suites = [xml] if xml.tag == "testsuite" else list(xml)
    if any(int(suite.get(key, "0")) for suite in suites for key in ("errors", "failures", "skipped")):
        raise ValueError("Failing/incomplete tests")
    return {
        "static_html_qa": "passed",
        "tac_rows": 33,
        "tac_columns": 8,
        "existing_pdf_links": len(paths),
        "graph_raw_spans_verified": anchored,
        "fresh_real_development_windows": len(dataset["cases"]),
        "bindings_verified": len(report["bindings"]),
        "tests_passed": sum(int(suite.get("tests", "0")) for suite in suites),
        "browser_execution": "not_run",
        "pdf_visual_qa": "not_run",
        "bindings": files.bindings([Path(__file__), folder / "report.json", folder / "manifest.json", junit]),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", required=True, type=Path)
    parser.add_argument("--junit", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = verify(args.review, args.junit)
    files.write(args.output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
