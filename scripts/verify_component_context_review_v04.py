"""Verify all context anchors, exact diagnostic replay and historical sources."""

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
from scripts.verify_cross_lingual_relation_review import check_span  # noqa: E402
from scripts.verify_typed_partial_relation_review import check_graph  # noqa: E402
from scripts.verify_typed_partial_relation_review import verify as verify_previous_structure  # noqa: E402


def check_context_graph(question: str, analysis: dict[str, Any], sources: list[dict[str, Any]]) -> dict[str, int]:
    count = check_graph(analysis, sources)
    contexts = 0
    for source in analysis["typed_sources"]:
        raw = sources[source["evidence_index"]]["text"]
        for unit in source["units"]:
            for node in unit["variables"]:
                context = node["source_context"]
                for binding in [*context["accepted"], *context["rejected"]]:
                    for key in ("span", "pair_span", "sentence_span", "target_dispersion_span"):
                        if binding[key] is not None:
                            check_span(raw, binding[key])
                            contexts += 1
                    if binding["chemical_identity_established"] or binding["value_owner_established"]:
                        raise ValueError("Context invented identity or quantitative owner")
                    if binding in context["accepted"] and binding["diagnostics"]:
                        raise ValueError("Rejected context counted as accepted")
    expected = v4.audit(question, sources, baseline_adequate=analysis["baseline_adequate"])
    if analysis != expected:
        raise ValueError("Context graph differs from exact diagnostic replay")
    return {"graph_spans": count, "context_spans": contexts}


def verify(folder: Path, junit: Path) -> dict[str, Any]:
    # Reuses immutable checks for 328 replays,1968 executions,33 TAC rows/eight
    # columns/41 PDF links, tests, six fresh real windows and partial/full split.
    qa = verify_previous_structure(folder, junit)
    report = json.loads((folder / "report.json").read_bytes())
    counts = {"graph_spans": 0, "context_spans": 0}
    for row in report["records"]:
        checked = check_context_graph(row["question"], row["analysis"], row["full_evidence"] or [])
        for key, value in checked.items():
            counts[key] += value
    controls, parents = report["controls"]["records"], report["controls"]["real_parent_records"]
    for row in [*controls, *parents]:
        checked = check_context_graph(row["question"], row["arms"]["v4"], row["sources"])
        for key, value in checked.items():
            counts[key] += value
    if report["summary"]["old_constructed_complete_losses"]["v4"]:
        raise ValueError("Nominal-null regression remains")
    if report["summary"]["outside_scope_baseline_preserved"] != 292:
        raise ValueError("Outside-scope baseline inventory changed")
    qa.update(
        exact_context_graph_replay="passed", graph_and_control_raw_spans=counts["graph_spans"],
        context_and_rejection_raw_spans=counts["context_spans"],
        constructed_controls=sum(row["kind"] != "real_development" for row in controls),
        real_parent_diagnostics=len(parents),
        bindings={**qa["bindings"], **files.bindings([Path(__file__)])},
    )
    return qa


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
