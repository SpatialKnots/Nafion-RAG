"""Immutable three-arm source-context comparison on328 frozen service inputs."""

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

from scripts import component_context_relations_v04 as v4  # noqa: E402
from scripts import cross_lingual_relation_audit as v1  # noqa: E402
from scripts import gigachat_answer_smoke as files  # noqa: E402
from scripts import typed_partial_relations as v2  # noqa: E402
from scripts.run_cross_lingual_relation_audit import CAPTURE, load_records, render, replay_service, validate_sources  # noqa: E402

PREVIOUS = ROOT / "output/typed_partial_relation_20261102/review_v01"
PROTOCOL = ROOT / "docs/records/component_context_relation_protocol_v0.4.md"
CONTROLS = ROOT / "docs/records/component_context_controls_v0.4.json"
REAL = ROOT / "docs/records/typed_partial_real_cases_v0.2.json"
HISTORICAL = ROOT / "output/component_context_relation_20261103/review_v02"


def evaluate(question: str, sources: list[dict[str, Any]], baseline: bool) -> dict[str, Any]:
    before = copy.deepcopy(sources)
    result = {
        "v1": v1.audit(question, sources, baseline_adequate=baseline),
        "v2": v2.audit(question, sources, baseline_adequate=baseline),
        "v4": v4.audit(question, sources, baseline_adequate=baseline),
    }
    if before != sources:
        raise ValueError("Diagnostic mutated frozen sources")
    return result


def controls() -> dict[str, Any]:
    datasets = [
        ("v1_constructed", ROOT / "docs/records/cross_lingual_relation_controls_v0.1.json"),
        ("v2_constructed", ROOT / "docs/records/typed_partial_controls_v0.2.json"),
        ("v3_constructed", ROOT / "docs/records/component_context_controls_v0.3.json"),
        ("v4_constructed", CONTROLS),
        ("real_development", REAL),
    ]
    question = json.loads(CONTROLS.read_bytes())["question"]
    rows, parents = [], []
    for kind, path in datasets:
        dataset = json.loads(path.read_bytes())
        for control in dataset.get("controls", dataset.get("cases", [])):
            texts = [control["raw_span"]["text"]] if kind == "real_development" else control.get("texts", [control.get("text", "")])
            sources = [{"text": text, "title": control.get("title")} for text in texts]
            query = control.get("question", dataset.get("question", dataset.get("default_question", question)))
            arms = evaluate(query, sources, False)
            if kind == "v1_constructed":
                if bool(arms["v1"].get("proposals")) != control["candidate"]:
                    raise ValueError("Old control changed: " + control["id"])
            else:
                expected = control.get("partial", control.get("annotation", {}).get("partial_relation"))
                if bool(arms["v4"]["partial_relations"]) != expected:
                    raise ValueError("Partial control differs: " + control["id"])
                if arms["v4"]["textual_requirements_met"] != control.get("complete", False):
                    raise ValueError("Complete control differs: " + control["id"])
            rows.append({"id": control["id"], "kind": kind, "source_control": control, "question": query, "sources": sources, "arms": arms})
            if kind == "real_development":
                parent_sources = [{"text": control["parent_text"]}]
                parents.append({
                    "id": control["id"], "question": query, "sources": parent_sources,
                    "provenance": control["provenance"], "addresses": control["addresses"],
                    "parent_sha256": control["parent_sha256"], "arms": evaluate(query, parent_sources, False),
                    "annotation": "whole parent diagnostic; no new completeness labels; exposed source, not independent gold",
                })
    losses = {
        name: [r["id"] for r in rows if r["kind"] == "v1_constructed" and r["arms"]["v1"]["textual_requirements_met"]
               and not r["arms"][name]["textual_requirements_met"]]
        for name in ("v2", "v4")
    }
    return {"records": rows, "real_parent_records": parents, "old_complete_losses": losses, "independent_accuracy": None}


def edge_rows(analysis: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for source in analysis["typed_sources"]:
        for unit in source["units"]:
            for index, edge in enumerate(unit["edges"]):
                if edge["partial_relation"]:
                    rows.append({
                        "evidence_index": source["evidence_index"], "region_index": unit["region_index"], "edge_index": index,
                        "span": edge["span"], "variable_span": edge["variable"]["span"], "status": edge["status"],
                        "query_variable_scope": edge["query_variable_scope"], "context_bindings": edge.get("context_bindings", []),
                    })
    return rows


def write_html(report: dict[str, Any], output: Path) -> None:
    detail = output / "detail_view"
    detail.mkdir()
    render(report, detail)
    raw = (detail / "review.html").read_text(encoding="utf-8")
    raw = raw.replace("<title>ARIADNE: RU/EN relation audit</title>", "<title>ARIADNE: component context v0.4</title>")
    raw = raw.replace(v1.VERSION, v4.VERSION)
    marker = "<h2>Каждый frozen набор evidence</h2>"
    if raw.count(marker) != 1:
        raise ValueError("Frozen renderer marker differs")
    extra = (
        "<h2>v0.4: source-context binding и observed nominal null</h2>"
        "<p>Точная пара компонентов, то же/предыдущее предложение. Dispersion context не доказывает solvent identity. "
        "Partial/full отдельно; quantitative owners не подтверждены. Это offline diagnostic, не рабочий gate.</p>"
        '<table id="partial"><thead><tr><th>Case</th><th>Arm/window</th><th>v1 full</th><th>v2 partial/full</th>'
        "<th>v4 partial/full</th><th>Source-context changes</th></tr></thead><tbody>"
    )
    for row in report["records"]:
        c = row["arm_comparison"]
        values = [row["case_id"], row["arm"] + "/" + row["window_qualifier"], c["v1_complete"],
                  f'{c["v2_partial_edges"]}/{c["v2_complete"]}', f'{c["v4_partial_edges"]}/{c["v4_complete"]}',
                  json.dumps(row["edge_changes"], ensure_ascii=False)]
        extra += "<tr>" + "".join("<td>" + html.escape(str(value)) + "</td>" for value in values) + "</tr>"
    extra += "</tbody></table>"
    files.save(output / "review.html", raw.replace(marker, extra + marker).encode())


def run(output: Path, policy: files.NetworkPolicy) -> dict[str, Any]:
    settings = files.configure()
    files.verify_manifest(PREVIOUS)
    previous = json.loads((PREVIOUS / "report.json").read_bytes())
    files.verify(previous["bindings"])
    files.verify_manifest(HISTORICAL)
    historical = json.loads((HISTORICAL / "report.json").read_bytes())
    files.verify(historical["bindings"])
    real = json.loads(REAL.read_bytes())
    files.verify(real["bindings"])
    paths = [Path(__file__), PROTOCOL, CONTROLS, REAL, PREVIOUS / "manifest.json", PREVIOUS / "report.json",
             ROOT / "scripts/component_context_relations_v04.py", ROOT / "scripts/verify_component_context_review_v04.py",
             ROOT / "tests/unit/test_component_context_v04.py", HISTORICAL / "report.json", HISTORICAL / "manifest.json",
             ROOT / "docs/records/component_context_controls_v0.3.json",
             ROOT / "output/component_context_relation_20261103/posthoc_adverse_probes_v01.json"]
    bindings = {**historical["bindings"], **files.bindings(paths)}
    control_results = controls()
    if control_results["old_complete_losses"]["v4"]:
        raise ValueError("Original complete controls regressed")
    records = load_records()
    corpus = json.loads((CAPTURE / "corpus.json").read_bytes())
    if len(records) != len(previous["records"]) or len(records) != 328:
        raise ValueError("Frozen inventory changed")
    output.mkdir(parents=True, exist_ok=False)
    (output / "records").mkdir()
    for path in paths:
        if any(path.is_relative_to(ROOT / name) for name in ("scripts", "tests", "docs")):
            target = output / "source_snapshot" / path.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            files.save(target, path.read_bytes())
    files.write(output / "frozen_inputs.json", {"version": v4.VERSION, "bindings": bindings})
    reports = []
    for index, record in enumerate(records):
        validate_sources(record["trace"], corpus)
        proof = replay_service(record, settings)
        evidence = record["trace"]["evidence"]
        baseline = record["trace"]["metadata"]["evidence_adequacy"]
        arms = evaluate(record["request"]["question"], evidence, baseline["adequate"])
        if arms["v2"] != previous["records"][index]["analysis"]:
            raise ValueError("Frozen typed v0.2 replay differs")
        if arms != evaluate(record["request"]["question"], evidence, baseline["adequate"]):
            raise ValueError("Repeated diagnostics differ")
        analysis = arms["v4"]
        before, after = edge_rows(arms["v2"]), edge_rows(analysis)
        changes = {"before": before, "after": after} if before != after else None
        item = {key: value for key, value in record.items() if key not in {"trace", "request"}}
        item.update(
            question=record["request"]["question"], baseline_adequacy=baseline, analysis=analysis,
            arms=arms if analysis["requirements"]["in_scope"] else None,
            arm_comparison={
                "v1_complete": arms["v1"]["textual_requirements_met"],
                "v2_partial_edges": len(arms["v2"]["partial_relations"]), "v2_complete": arms["v2"]["textual_requirements_met"],
                "v4_partial_edges": len(analysis["partial_relations"]), "v4_complete": analysis["textual_requirements_met"],
            },
            edge_changes=changes, replay=proof, repeated_execution_identical=True,
            full_evidence=evidence if analysis["requirements"]["in_scope"] else None,
            frozen_full_trace_sha256=files.sha(files.encode(record["trace"])),
        )
        reports.append(item)
        files.write(output / f"records/{index:03d}.json", item)
        if (index + 1) % 40 == 0 or index + 1 == len(records):
            print(json.dumps({"completed_records": index + 1, "total_records": len(records)}), flush=True)
    corrupt = copy.deepcopy(records[0])
    corrupt["trace"]["retrieval"]["results"][0]["full_text"] += " corrupt"
    try:
        validate_sources(corrupt["trace"], corpus)
    except ValueError as exc:
        if str(exc) != "Frozen raw retrieval source differs: full_text":
            raise
    else:
        raise ValueError("Corrupt source accepted")
    corrupt = copy.deepcopy(records[0])
    corrupt["trace"]["metadata"]["evidence_adequacy"]["reason"] = "corrupt"
    try:
        replay_service(corrupt, settings)
    except ValueError as exc:
        if str(exc) != "Frozen full service trace or status differs":
            raise
    else:
        raise ValueError("Corrupt baseline accepted")
    import fitz

    for article in previous["articles"]:
        if files.sha(Path(article["original_pdf_path"]).read_bytes()) != article["original_pdf_sha256"]:
            raise ValueError("Original PDF changed")
    for window in previous["reference_windows"]:
        with fitz.open(window["original_pdf_path"]) as pdf:
            if window["exact_text"] not in pdf[window["pdf_page"] - 1].get_text():
                raise ValueError("Fresh reference window differs")
    files.verify(bindings)
    if policy.denied:
        raise ValueError("Unexpected network attempt")
    scoped = [r for r in reports if r["analysis"]["requirements"]["in_scope"]]
    edges = [e for r in scoped for e in edge_rows(r["analysis"])]
    unique = {g["raw_relation_sha256"] for r in scoped for g in r["analysis"]["exact_relation_groups"]}
    summary = {
        "version": v4.VERSION, "evidence_sets": len(records), "service_full_trace_replays": len(records),
        "arm_diagnostic_executions": 6 * len(records), "diagnostic_arm_count": 3,
        "scoped_sets": len(scoped), "outside_scope_baseline_preserved": len(reports) - len(scoped),
        "partial_relation_sets": sum(bool(r["analysis"]["partial_relations"]) for r in scoped),
        "partial_edge_observations": len(edges), "unique_raw_relation_types": len(unique),
        "complete_sets_by_arm": {name: sum(bool(r["arms"][name]["textual_requirements_met"]) for r in scoped)
                                 for name in ("v1", "v2", "v4")},
        "context_bound_edge_observations": sum(bool(e["context_bindings"]) for e in edges),
        "solvent_context_bound_edges": sum(any(b["kind"] == "explicit_solvent_components" for b in e["context_bindings"])
                                          for e in edges),
        "dispersion_context_bound_edges": sum(any(b["kind"] == "explicit_dispersion_components" for b in e["context_bindings"])
                                             for e in edges),
        "changed_scoped_records": sum(r["edge_changes"] is not None for r in scoped),
        "old_constructed_complete_losses": control_results["old_complete_losses"],
        "constructed_controls": sum(r["kind"] != "real_development" for r in control_results["records"]),
        "real_development_windows": len(real["cases"]), "real_parent_diagnostics": len(control_results["real_parent_records"]),
        "corrupted_source_rejected": True, "corrupted_baseline_rejected": True,
        "verified_bindings": len(bindings), "pdf_hashes_checked": len(previous["articles"]),
        "fresh_reference_windows": len(previous["reference_windows"]), "runtime_changed": False,
        "db_calls": 0, "search_calls": 0, "embedding_calls": 0, "model_calls": 0, "oauth_calls": 0,
        "slot_reservations": 0, "network_denials": policy.denied, "scientific_acceptance": "not_established",
        "independent_accuracy": None, "answer_quality_plan_completion_percent": 75,
        "limits": ["finite explicit ordered pairs; same/previous sentence only; no unrestricted anaphora",
                   "dispersion components do not establish solvent identity; no quantitative owner propagation",
                   "exposed development inputs, not independent scientific evaluation",
                   "serial offline adapter; no production integration", "browser/PDF visual/full suite/mypy not run"],
    }
    summary["historical_v3_summary"] = historical["summary"]
    report = {"summary": summary, "bindings": bindings, "records": reports, "controls": control_results,
              "articles": previous["articles"], "reference_windows": previous["reference_windows"]}
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
