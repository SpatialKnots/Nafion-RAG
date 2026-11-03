"""Compare immutable v0.2/v0.4 and explicit chains on328 frozen preparations."""

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
from scripts import source_reference_chains as v5  # noqa: E402
from scripts import typed_partial_relations as v2  # noqa: E402
from scripts.run_cross_lingual_relation_audit import CAPTURE, load_records, render, replay_service, validate_sources  # noqa: E402
from scripts.verify_source_reference_review import base_result  # noqa: E402

PREVIOUS = ROOT / "output/component_context_relation_20261103/review_v04"
PACKET = ROOT / "docs/records/source_reference_cases_v0.5.json"
CONTROLS = ROOT / "docs/records/source_reference_controls_v0.5.json"
PROTOCOL = ROOT / "docs/records/source_reference_chain_protocol_v0.5.md"


def evaluate(question: str, sources: list[dict[str, Any]], baseline: bool) -> dict[str, Any]:
    before = copy.deepcopy(sources)
    result = {"v2": v2.audit(question, sources, baseline_adequate=baseline),
              "v4": v4.audit(question, sources, baseline_adequate=baseline),
              "v5": v5.audit(question, sources, baseline_adequate=baseline)}
    if before != sources or base_result(result["v5"]) != result["v4"]:
        raise ValueError("Source or immutable v0.4 decision changed")
    return result


def controls() -> dict[str, Any]:
    data = json.loads(CONTROLS.read_bytes())
    rows = []
    for case in data["controls"]:
        question = case.get("question", data["question"])
        sources = [{"text": t, "title": case.get("title")} for t in case.get("texts", [case.get("text", "")])]
        analysis = v5.audit(question, sources, baseline_adequate=False)
        if bool(analysis["source_chains"]) != case["binding"] or analysis["chain_textual_requirements_met"] != case["complete"]:
            raise ValueError("Declared chain control differs: " + case["id"])
        rows.append({"id": case["id"], "question": question, "sources": sources, "control": case, "analysis": analysis})
    return {"origin": data["origin"], "records": rows, "scientific_accuracy": None}


def real_records(packet: dict[str, Any], question: str) -> list[dict[str, Any]]:
    rows = []
    parents = {p["parent_sha256"]: p for p in packet["parents"]}
    for kind, cases in (("old_window", packet["old_cases"]), ("context_window", packet["context_cases"]),
                        ("full_parent", packet["old_cases"])):
        for case in cases:
            text = parents[case["parent_sha256"]]["text"] if kind == "full_parent" else case["raw_span"]["text"]
            sources = [{"text": text}]
            arms = evaluate(question, sources, False)
            if kind == "context_window" and (bool(arms["v5"]["source_chains"]) != case["annotation"]["binding"]
                                              or arms["v5"]["chain_textual_requirements_met"] != case["annotation"]["complete"]):
                raise ValueError("Frozen real context label differs")
            rows.append({"id": case["id"], "kind": kind, "question": question, "sources": sources,
                         "provenance": case["provenance"], "addresses": case["addresses"],
                         "parent_sha256": case["parent_sha256"], "analysis": arms["v5"], "arms": arms})
    return rows


def write_html(report: dict[str, Any], output: Path) -> None:
    detail = output / "detail_view"
    detail.mkdir()
    render(report, detail)
    raw = (detail / "review.html").read_text(encoding="utf-8").replace(v1.VERSION, v5.VERSION)
    raw = raw.replace("<title>ARIADNE: RU/EN relation audit</title>", "<title>ARIADNE: explicit reference chains v0.5</title>")
    marker = "<h2>Каждый frozen набор evidence</h2>"
    if raw.count(marker) != 1:
        raise ValueError("Frozen HTML renderer marker changed")
    extra = (
        "<h2>Явные source-reference chains v0.5</h2><p>Каждый переход имеет raw anchor. "
        "Context association не является dependency; missing particles/owners остаются unresolved. "
        "Решения v0.4 сохранены, новые chain requirements показаны отдельно.</p>"
        '<table id="partial"><thead><tr><th>Case</th><th>Arm/window</th><th>v2 full</th><th>v4 full</th>'
        "<th>Chain bindings</th><th>Chain textual requirements</th></tr></thead><tbody>"
    )
    for row in report["records"]:
        c = row["arm_comparison"]
        values = [row["case_id"], row["arm"] + "/" + row["window_qualifier"], c["v2_full"], c["v4_full"],
                  c["chain_bindings"], c["chain_requirements"]]
        extra += "<tr>" + "".join("<td>" + html.escape(str(v)) + "</td>" for v in values) + "</tr>"
    extra += "</tbody></table><h2>Frozen real contexts: отдельные paths и source addresses</h2>"
    extra += "<details><summary>Полные14 real diagnostics; повторы не независимы</summary><pre>"
    extra += html.escape(json.dumps(report["real_chain_records"], ensure_ascii=False, indent=2)) + "</pre></details>"
    files.save(output / "review.html", raw.replace(marker, extra + marker).encode())


def run(output: Path, policy: files.NetworkPolicy) -> dict[str, Any]:
    settings = files.configure()
    files.verify_manifest(PREVIOUS)
    previous = json.loads((PREVIOUS / "report.json").read_bytes())
    files.verify(previous["bindings"])
    packet = json.loads(PACKET.read_bytes())
    files.verify(packet["bindings"])
    paths = [Path(__file__), ROOT / "scripts/source_reference_chains.py", ROOT / "scripts/prepare_source_reference_cases.py",
             ROOT / "scripts/verify_source_reference_review.py", ROOT / "tests/unit/test_source_reference_chains.py",
             ROOT / "tests/unit/test_source_reference_review.py", PROTOCOL, PACKET, CONTROLS,
             PREVIOUS / "report.json", PREVIOUS / "manifest.json"]
    bindings = {**previous["bindings"], **files.bindings(paths)}
    new_controls = controls()
    old_controls = []
    for row in previous["controls"]["records"]:
        if row["kind"] == "real_development":
            continue
        analysis = v5.audit(row["question"], row["sources"], baseline_adequate=False)
        if base_result(analysis) != row["arms"]["v4"]:
            raise ValueError("Saved older control decision changed")
        old_controls.append({"id": row["id"], "kind": row["kind"], "question": row["question"],
                             "sources": row["sources"], "analysis": analysis})
    real = real_records(packet, json.loads(CONTROLS.read_bytes())["question"])
    records, corpus = load_records(), json.loads((CAPTURE / "corpus.json").read_bytes())
    if len(records) != 328 or len(previous["records"]) != 328 or len(old_controls) != 139:
        raise ValueError("Frozen input inventory changed")
    output.mkdir(parents=True, exist_ok=False)
    (output / "records").mkdir()
    for path in paths:
        if any(path.is_relative_to(ROOT / name) for name in ("scripts", "tests", "docs")):
            target = output / "source_snapshot" / path.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            files.save(target, path.read_bytes())
    files.write(output / "frozen_inputs.json", {"version": v5.VERSION, "bindings": bindings})
    reports = []
    for index, record in enumerate(records):
        validate_sources(record["trace"], corpus)
        proof = replay_service(record, settings)
        evidence, baseline = record["trace"]["evidence"], record["trace"]["metadata"]["evidence_adequacy"]
        arms = evaluate(record["request"]["question"], evidence, baseline["adequate"])
        if arms["v4"] != previous["records"][index]["analysis"]:
            raise ValueError("Frozen v0.4 replay differs")
        if arms != evaluate(record["request"]["question"], evidence, baseline["adequate"]):
            raise ValueError("Repeated arm executions differ")
        analysis = arms["v5"]
        item = {k: v for k, v in record.items() if k not in {"trace", "request"}}
        item.update(question=record["request"]["question"], baseline_adequacy=baseline, analysis=analysis,
                    arms=arms if analysis["requirements"]["in_scope"] else None,
                    arm_comparison={"v2_full": arms["v2"]["textual_requirements_met"],
                                    "v4_full": arms["v4"]["textual_requirements_met"],
                                    "chain_bindings": len(analysis["source_chains"]),
                                    "chain_requirements": analysis["chain_textual_requirements_met"]},
                    replay=proof, repeated_execution_identical=True,
                    full_evidence=evidence if analysis["requirements"]["in_scope"] else None,
                    frozen_full_trace_sha256=files.sha(files.encode(record["trace"])))
        reports.append(item)
        files.write(output / f"records/{index:03d}.json", item)
        if (index + 1) % 40 == 0 or index + 1 == len(records):
            print(json.dumps({"completed_records": index + 1, "total_records": len(records)}), flush=True)
    for kind in ("source", "baseline"):
        corrupt = copy.deepcopy(records[0])
        if kind == "source":
            corrupt["trace"]["retrieval"]["results"][0]["full_text"] += " corrupt"
        else:
            corrupt["trace"]["metadata"]["evidence_adequacy"]["reason"] = "corrupt"
        try:
            validate_sources(corrupt["trace"], corpus) if kind == "source" else replay_service(corrupt, settings)
        except ValueError as exc:
            expected = ("Frozen raw retrieval source differs: full_text" if kind == "source"
                        else "Frozen full service trace or status differs")
            if str(exc) != expected:
                raise
        else:
            raise ValueError("Corrupted input accepted")
    import fitz

    for article in previous["articles"]:
        if files.sha(Path(article["original_pdf_path"]).read_bytes()) != article["original_pdf_sha256"]:
            raise ValueError("Original PDF changed")
    for window in previous["reference_windows"]:
        with fitz.open(window["original_pdf_path"]) as pdf:
            if window["exact_text"] not in pdf[window["pdf_page"] - 1].get_text():
                raise ValueError("Fresh reference anchor differs")
    files.verify(bindings)
    if policy.denied:
        raise ValueError("Unexpected network attempt")
    scoped = [r for r in reports if r["analysis"]["requirements"]["in_scope"]]
    summary = {
        "version": v5.VERSION, "evidence_sets": 328, "service_full_trace_replays": 328,
        "arm_diagnostic_executions": 1968, "diagnostic_arm_count": 3, "scoped_sets": len(scoped),
        "outside_scope_baseline_preserved": 328 - len(scoped), "v4_exact_replays": 328,
        "base_partial_sets": sum(bool(r["analysis"]["partial_relations"]) for r in scoped),
        "base_full_sets": sum(r["analysis"]["textual_requirements_met"] for r in scoped),
        "chain_binding_sets": sum(bool(r["analysis"]["source_chains"]) for r in scoped),
        "chain_path_observations": sum(len(r["analysis"]["source_chains"]) for r in scoped),
        "unique_raw_chain_types": len({g["raw_chain_sha256"] for r in scoped for g in r["analysis"]["exact_chain_groups"]}),
        "chain_full_requirement_sets": sum(r["analysis"]["chain_textual_requirements_met"] for r in scoped),
        "constructed_controls": len(new_controls["records"]), "older_control_replays": len(old_controls),
        "real_diagnostic_records": len(real), "real_distinct_parents": len(packet["parents"]),
        "real_context_windows": len(packet["context_cases"]),
        "corrupted_source_rejected": True, "corrupted_baseline_rejected": True, "verified_bindings": len(bindings),
        "pdf_hashes_checked": len(previous["articles"]), "fresh_reference_windows": len(previous["reference_windows"]),
        "runtime_changed": False, "db_calls": 0, "search_calls": 0, "embedding_calls": 0, "model_calls": 0,
        "oauth_calls": 0, "slot_reservations": 0, "network_denials": policy.denied,
        "scientific_acceptance": "not_established", "independent_accuracy": None, "answer_quality_plan_completion_percent": 75,
        "limits": ["finite explicit references; consecutive anchored hops; no distant identity inference",
                   "context association does not supply particle attachment or directed dependency",
                   "old v0.4 decisions unchanged; new chain flags are not runtime permissions",
                   "exposed development inputs, no independent scientific metrics; no value propagation",
                   "browser/PDF visual/full suite/mypy not run"],
    }
    report = {"summary": summary, "bindings": bindings, "records": reports, "chain_controls": new_controls,
              "older_control_replays": old_controls, "real_chain_records": real,
              "controls": {"new": new_controls, "older": old_controls},
              "articles": previous["articles"], "reference_windows": previous["reference_windows"]}
    files.write(output / "report.json", report)
    write_html(report, output)
    files.manifest(output)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    policy = files.NetworkPolicy()
    sys.addaudithook(policy)
    print(json.dumps(run(args.output, policy), ensure_ascii=False, indent=2))
