"""Check anchored chains, immutable v0.4 base and separate completeness flags."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import component_context_relations_v04 as v4  # noqa: E402
from scripts import gigachat_answer_smoke as files  # noqa: E402
from scripts import source_reference_chains_v06 as v5  # noqa: E402
from scripts.verify_component_context_review_v04 import check_context_graph  # noqa: E402
from scripts.verify_cross_lingual_relation_review import check_span  # noqa: E402
from scripts.verify_typed_partial_relation_review import verify as verify_structure  # noqa: E402

CHAIN_FIELDS = {"chain_sources", "source_chains", "chain_textual_requirements_met", "exact_chain_groups"}


def base_result(analysis: dict[str, Any]) -> dict[str, Any]:
    return {**{k: v for k, v in analysis.items() if k not in CHAIN_FIELDS}, "version": v4.VERSION}


def check_chains(question: str, analysis: dict[str, Any], sources: list[dict[str, Any]]) -> dict[str, int]:
    base = check_context_graph(question, base_result(analysis), sources)
    count = 0

    def anchors(value: Any, raw: str) -> None:
        nonlocal count
        if isinstance(value, dict):
            if {"start", "end", "text"} <= value.keys():
                check_span(raw, value)
                count += 1
            for key, item in value.items():
                if key in {"scientific_admission", "chemical_identity_established", "performed_established",
                           "material_owner_established", "value_owner_established"} and item:
                    raise ValueError("Chain invented scientific owner or admission")
                anchors(item, raw)
        elif isinstance(value, list):
            for item in value:
                anchors(item, raw)

    for graph in analysis["chain_sources"]:
        anchors(graph, sources[graph["evidence_index"]]["text"])
    if analysis != v5.audit(question, sources, baseline_adequate=analysis["baseline_adequate"]):
        raise ValueError("Exact reference-chain replay differs")
    return {**base, "chain_spans": count}


def verify(folder: Path, junit: Path) -> dict[str, Any]:
    qa = verify_structure(folder, junit)
    report = json.loads((folder / "report.json").read_bytes())
    count = 0
    for row in report["records"]:
        count += check_chains(row["question"], row["analysis"], row["full_evidence"] or [])["chain_spans"]
    for row in report["chain_controls"]["records"]:
        count += check_chains(row["question"], row["analysis"], row["sources"])["chain_spans"]
    for row in report["real_chain_records"]:
        count += check_chains(row["question"], row["analysis"], row["sources"])["chain_spans"]
    for row in report["older_control_replays"]:
        count += check_chains(row["question"], row["analysis"], row["sources"])["chain_spans"]
    packet = json.loads((ROOT / "docs/records/source_reference_cases_v0.5.json").read_bytes())
    files.verify(packet["bindings"])
    parents = {p["parent_sha256"]: p for p in packet["parents"]}
    for digest, parent in parents.items():
        if files.sha(parent["text"].encode()) != digest:
            raise ValueError("Frozen chain parent differs")
    import fitz

    articles = {a["article_id"]: a for a in report["articles"]}
    for case in packet["context_cases"]:
        check_span(parents[case["parent_sha256"]]["text"], case["raw_span"])
        source = case["provenance"]
        with fitz.open(articles[source["article_id"]]["original_pdf_path"]) as pdf:
            pages = [pdf[i - 1].get_text() for i in range(source["page_start"], source["page_end"] + 1)]
        if not any(case["raw_span"]["text"] in raw for raw in [*pages, "\n".join(pages), "\n\n".join(pages)]):
            raise ValueError("Fresh chain context differs")
    qa.update(chain_raw_spans_verified=count, exact_chain_and_base_replay="passed",
              fresh_chain_context_windows=len(packet["context_cases"]),
              bindings={**qa["bindings"], **files.bindings([Path(__file__)])})
    return qa


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--junit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.review, args.junit)
    files.write(args.output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
