"""Compare immutable v0.1, segmentation-only and typed partial v0.2 offline."""

from __future__ import annotations

import argparse
import copy
import html
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import cross_lingual_relation_audit as v1  # noqa: E402
from scripts import gigachat_answer_smoke as files  # noqa: E402
from scripts import typed_partial_relations as v2  # noqa: E402
from scripts.run_cross_lingual_relation_audit import CAPTURE, load_records, render, replay_service, validate_sources  # noqa: E402

PREVIOUS = ROOT / "output/cross_lingual_relation_20261102/review_v03"
PROTOCOL = ROOT / "docs/records/typed_partial_relation_protocol_v0.2.md"
CONTROLS = ROOT / "docs/records/typed_partial_controls_v0.2.json"
REAL = ROOT / "docs/records/typed_partial_real_cases_v0.2.json"


def evaluate(question: str, sources: list[dict[str, Any]], baseline: bool) -> dict[str, Any]:
    before = copy.deepcopy(sources)
    values = {
        "v1": v1.audit(question, sources, baseline_adequate=baseline),
        "segmentation_only": v2.segmentation_only(question, sources, baseline_adequate=baseline),
        "typed_partial": v2.audit(question, sources, baseline_adequate=baseline),
    }
    if sources != before:
        raise ValueError("Diagnostic mutated source inputs")
    return values


def controls() -> dict[str, Any]:
    old = json.loads((ROOT / "docs/records/cross_lingual_relation_controls_v0.1.json").read_bytes())
    new = json.loads(CONTROLS.read_bytes())
    real = json.loads(REAL.read_bytes())
    records = []
    for dataset, kind in ((old, "v1_constructed"), (new, "v2_constructed"), (real, "real_development")):
        for control in dataset.get("controls", dataset.get("cases", [])):
            if kind == "real_development":
                question, sources = new["question"], [{"text": control["raw_span"]["text"]}]
            else:
                question = control.get("question", dataset.get("question", dataset.get("default_question")))
                sources = [{"text": text} for text in control.get("texts", [control.get("text", "")])]
            result = evaluate(question, sources, False)
            if kind == "v1_constructed":
                if bool(result["v1"].get("proposals")) != control["candidate"]:
                    raise ValueError("Original v1 control changed")
            else:
                expected = control.get("partial", control.get("annotation", {}).get("partial_relation"))
                if bool(result["typed_partial"]["partial_relations"]) != expected:
                    raise ValueError("New partial-relation control differs: " + control["id"])
                if result["typed_partial"]["textual_requirements_met"] != control.get("complete", False):
                    raise ValueError("New complete-requirements control differs: " + control["id"])
            records.append(
                {"kind": kind, "id": control["id"], "source_control": control, "question": question, "sources": sources, "arms": result}
            )
    return {
        "records": records,
        "origin": "assistant development controls; exposed real packet; not independent gold",
        "old_complete_losses": [
            row["id"]
            for row in records
            if row["kind"] == "v1_constructed"
            and row["arms"]["v1"]["textual_requirements_met"]
            and not row["arms"]["typed_partial"]["textual_requirements_met"]
        ],
        "real_partial_hits": sum(
            bool(row["arms"]["typed_partial"]["partial_relations"]) for row in records if row["kind"] == "real_development"
        ),
    }


def write_html(report: dict[str, Any], output: Path) -> None:
    # Reuse the already versioned full raw/TAC renderer; add an explicit partial
    # graph comparison above its unchanged strict-requirements detail table.
    detail_dir = output / "detail_view"
    detail_dir.mkdir()
    render(report, detail_dir)
    raw = (detail_dir / "review.html").read_text(encoding="utf-8")
    marker = "<h2>Каждый frozen набор evidence</h2>"
    if raw.count(marker) != 1:
        raise ValueError("Bound renderer marker differs")
    extra = (
        "<h2>Typed partial v0.2: частичная связь отдельно от достаточности</h2>"
        "<p>Named-component ratio не объявляется solvent composition. Все связи и владельцы "
        "остаются научно непроверенными; baseline gate не меняется.</p>"
        '<table id="partial"><thead><tr><th>Case</th><th>Arm / window</th><th>v1 full</th>'
        "<th>Segmentation full</th><th>Typed partial edges</th><th>Typed full</th></tr></thead><tbody>"
    )
    for row in report["records"]:
        arms = row["arm_comparison"]
        extra += (
            "<tr><td>"
            + html.escape(row["case_id"])
            + "</td><td>"
            + html.escape(row["arm"] + "/" + row["window_qualifier"])
            + "</td><td>"
            + str(arms["v1_complete"])
            + "</td><td>"
            + str(arms["segmentation_complete"])
            + "</td><td>"
            + str(arms["typed_partial_edges"])
            + "</td><td>"
            + str(arms["typed_complete"])
            + "</td></tr>"
        )
    extra += "</tbody></table>"
    files.save(output / "review.html", raw.replace(marker, extra + marker).encode("utf-8"))


def run(output: Path, policy: files.NetworkPolicy) -> dict[str, Any]:
    settings = files.configure()
    files.verify_manifest(PREVIOUS)
    previous = json.loads((PREVIOUS / "report.json").read_bytes())
    files.verify(previous["bindings"])
    real = json.loads(REAL.read_bytes())
    files.verify(real["bindings"])
    paths = [
        Path(__file__),
        ROOT / "scripts/typed_partial_relations.py",
        ROOT / "scripts/prepare_typed_partial_real_cases.py",
        ROOT / "scripts/run_cross_lingual_relation_audit.py",
        ROOT / "tests/unit/test_typed_partial_relations.py",
        PROTOCOL,
        CONTROLS,
        REAL,
        ROOT / "docs/records/typed_partial_real_recipe_v0.2.json",
        PREVIOUS / "manifest.json",
        PREVIOUS / "report.json",
    ]
    bindings = {**previous["bindings"], **files.bindings(paths)}
    control_results = controls()
    records = load_records()
    corpus = json.loads((CAPTURE / "corpus.json").read_bytes())
    if len(records) != len(previous["records"]) or len(records) != 328:
        raise ValueError("Frozen record inventory changed")
    output.mkdir(parents=True, exist_ok=False)
    (output / "records").mkdir()
    for path in paths:
        if path.is_relative_to(ROOT / "scripts") or path.is_relative_to(ROOT / "docs") or path.is_relative_to(ROOT / "tests"):
            destination = output / "source_snapshot" / path.relative_to(ROOT)
            destination.parent.mkdir(parents=True, exist_ok=True)
            files.save(destination, path.read_bytes())
    files.write(output / "frozen_inputs.json", {"version": v2.VERSION, "bindings": bindings})
    reports, unique_relation_texts = [], set()
    for index, record in enumerate(records):
        validate_sources(record["trace"], corpus)
        proof = replay_service(record, settings)
        evidence = record["trace"]["evidence"]
        baseline = record["trace"]["metadata"]["evidence_adequacy"]
        arms = evaluate(record["request"]["question"], evidence, baseline["adequate"])
        if arms["v1"] != previous["records"][index]["analysis"]:
            raise ValueError("Frozen v1 diagnostic replay differs")
        if arms != evaluate(record["request"]["question"], evidence, baseline["adequate"]):
            raise ValueError("Repeated arm executions differ")
        typed = arms["typed_partial"]
        for group in typed["exact_relation_groups"]:
            unique_relation_texts.add(group["raw_relation_sha256"])
        item = {key: value for key, value in record.items() if key not in {"trace", "request"}}
        item.update(
            question=record["request"]["question"],
            baseline_adequacy=baseline,
            analysis=typed,
            arm_comparison={
                "v1_complete": arms["v1"]["textual_requirements_met"],
                "segmentation_complete": arms["segmentation_only"]["textual_requirements_met"],
                "typed_complete": typed["textual_requirements_met"],
                "typed_partial_edges": len(typed["partial_relations"]),
            },
            arms=arms if typed["requirements"]["in_scope"] else None,
            replay=proof,
            repeated_execution_identical=True,
            full_evidence=evidence if typed["requirements"]["in_scope"] else None,
            frozen_full_trace_sha256=files.sha(files.encode(record["trace"])),
        )
        reports.append(item)
        files.write(output / f"records/{index:03d}.json", item)
        if (index + 1) % 40 == 0 or index + 1 == len(records):
            print(json.dumps({"completed_records": index + 1, "total_records": len(records)}), flush=True)
    corrupted = copy.deepcopy(records[0])
    corrupted["trace"]["retrieval"]["results"][0]["full_text"] += " corrupt"
    try:
        validate_sources(corrupted["trace"], corpus)
    except ValueError as exc:
        if str(exc) != "Frozen raw retrieval source differs: full_text":
            raise
    else:
        raise ValueError("Corrupt source accepted")
    corrupted = copy.deepcopy(records[0])
    corrupted["trace"]["metadata"]["evidence_adequacy"]["reason"] = "corrupt"
    try:
        replay_service(corrupted, settings)
    except ValueError as exc:
        if str(exc) != "Frozen full service trace or status differs":
            raise
    else:
        raise ValueError("Corrupt baseline accepted")
    import fitz

    for article in previous["articles"]:
        if files.sha(Path(article["original_pdf_path"]).read_bytes()) != article["original_pdf_sha256"]:
            raise ValueError("PDF changed")
    for window in previous["reference_windows"]:
        with fitz.open(window["original_pdf_path"]) as pdf:
            page = pdf[window["pdf_page"] - 1].get_text()
        if window["exact_text"] not in page:
            raise ValueError("Fresh reference window differs")
    files.verify(bindings)
    if policy.denied:
        raise ValueError("Unexpected network attempt")
    scoped = [row for row in reports if row["analysis"]["requirements"]["in_scope"]]
    summary = {
        "version": v2.VERSION,
        "evidence_sets": len(records),
        "service_full_trace_replays": len(records),
        "arm_diagnostic_executions": 6 * len(records),
        "diagnostic_arm_count": 3,
        "scoped_sets": len(scoped),
        "outside_scope_baseline_preserved": len(reports) - len(scoped),
        "partial_relation_sets": sum(bool(row["analysis"]["partial_relations"]) for row in scoped),
        "partial_edge_observations": sum(len(row["analysis"]["partial_relations"]) for row in scoped),
        "unique_raw_relation_types": len(unique_relation_texts),
        "v1_complete_sets": sum(bool(row["arm_comparison"]["v1_complete"]) for row in scoped),
        "segmentation_complete_sets": sum(bool(row["arm_comparison"]["segmentation_complete"]) for row in scoped),
        "typed_complete_sets": sum(bool(row["arm_comparison"]["typed_complete"]) for row in scoped),
        "old_constructed_complete_losses": control_results["old_complete_losses"],
        "real_development_windows": len(real["cases"]),
        "real_partial_hits": control_results["real_partial_hits"],
        "constructed_controls": sum(row["kind"] != "real_development" for row in control_results["records"]),
        "corrupted_source_rejected": True,
        "corrupted_baseline_rejected": True,
        "verified_bindings": len(bindings),
        "pdf_hashes_checked": len(previous["articles"]),
        "fresh_reference_windows": len(previous["reference_windows"]),
        "runtime_changed": False,
        "db_calls": 0,
        "search_calls": 0,
        "embedding_calls": 0,
        "model_calls": 0,
        "oauth_calls": 0,
        "slot_reservations": 0,
        "network_denials": policy.denied,
        "scientific_acceptance": "not_established",
        "independent_accuracy": None,
        "answer_quality_plan_completion_percent": 75,
        "limits": [
            "partial source edge is not query completeness or scientific entailment",
            "generic component names do not establish solvent/chemical identity",
            "the real positive was previously exposed and assistant labelled; not independent evaluation",
            "serialized offline segmentation adapter only; no production mounting",
            "browser/PDF visual QA/full suite/mypy not run",
        ],
    }
    report = {
        "summary": summary,
        "bindings": bindings,
        "records": reports,
        "controls": control_results,
        "articles": previous["articles"],
        "reference_windows": previous["reference_windows"],
    }
    files.write(output / "report.json", report)
    write_html(report, output)
    files.manifest(output)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    policy = files.NetworkPolicy()
    sys.addaudithook(policy)
    print(json.dumps(run(args.output, policy), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
