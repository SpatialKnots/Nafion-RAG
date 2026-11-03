"""Offline particle-role/direction audit on new windows and328 frozen traces."""

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
from scripts import particle_attachment_audit as v7  # noqa: E402
from scripts import source_reference_chains_v06 as v6  # noqa: E402
from scripts.run_cross_lingual_relation_audit import CAPTURE, load_records, render, replay_service, validate_sources  # noqa: E402
from scripts.verify_particle_attachment_review import base_result  # noqa: E402

PREVIOUS = ROOT / "output/source_reference_chain_20261103/review_v06"
PACKET = ROOT / "docs/records/particle_attachment_cases_v0.7.json"
CONTROLS = ROOT / "docs/records/particle_attachment_controls_v0.7.json"
PROTOCOL = ROOT / "docs/records/particle_attachment_protocol_v0.7.md"
INSPECTION = ROOT / "output/particle_attachment_20261103/source_inspection_v02.json"


def role_summary(result: dict[str, Any]) -> dict[str, Any]:
    units = [u for source in result["atomic_sources"] for u in source["units"]]
    return {"particle_owner": any(u["particle_owners"] for u in units),
            "dispersion": any(m["kind"] == "explicit_dispersion" for u in units for m in u["medium_attachments"]),
            "eligible_relations": len(result["particle_relations"]),
            "complete_role_links": sum(u["role_links_complete"] for u in units),
            "requested_complete": result["particle_requirements_met"]}


def evaluate(question: str, sources: list[dict[str, Any]], baseline: bool) -> dict[str, Any]:
    before = copy.deepcopy(sources)
    values = {"v4": v4.audit(question, sources, baseline_adequate=baseline),
              "v6": v6.audit(question, sources, baseline_adequate=baseline),
              "v7": v7.audit(question, sources, baseline_adequate=baseline)}
    if before != sources or base_result(values["v7"]) != values["v6"]:
        raise ValueError("Immutable source or v0.6 result changed")
    return values


def controls() -> list[dict[str, Any]]:
    data = json.loads(CONTROLS.read_bytes())
    rows = []
    for case in data["controls"]:
        question = case.get("question", data["question"])
        sources = [{"text": t, "title": case.get("title")} for t in case.get("texts", [case.get("text", "")])]
        result = v7.audit(question, sources, baseline_adequate=False)
        if bool(result["particle_relations"]) != case["eligible"] or result["particle_requirements_met"] != case["complete"]:
            raise ValueError("Frozen atomic control differs: " + case["id"])
        rows.append({"id": case["id"], "question": question, "sources": sources, "analysis": result, "control": case})
    return rows


def real_records(packet: dict[str, Any]) -> list[dict[str, Any]]:
    question = json.loads(CONTROLS.read_bytes())["question"]
    rows = []
    for case in packet["cases"]:
        sources = [{"text": case["raw_span"]["text"]}]
        arms = evaluate(question, sources, False)
        summary = role_summary(arms["v7"])
        if any(summary[k] != case["annotation"][k] for k in ("particle_owner", "dispersion")):
            raise ValueError("Frozen real role observation differs: " + case["id"])
        if summary["requested_complete"] != case["requested_complete"]:
            raise ValueError("Frozen real requested scope differs")
        rows.append({"id": case["id"], "question": question, "sources": sources, "analysis": arms["v7"],
                     "arms": arms, "role_summary": summary, "source_case": case})
    return rows


def write_html(report: dict[str, Any], output: Path) -> None:
    detail = output / "detail_view"
    detail.mkdir()
    render(report, detail)
    raw = (detail / "review.html").read_text(encoding="utf-8").replace(v1.VERSION, v7.VERSION)
    raw = raw.replace("<title>ARIADNE: RU/EN relation audit</title>", "<title>ARIADNE: particle attachment v0.7</title>")
    marker = "<h2>Каждый frozen набор evidence</h2>"
    if raw.count(marker) != 1:
        raise ValueError("Frozen renderer marker changed")
    extra = (
        "<h2>Particle attachment и направление v0.7</h2><p>Particle ownership, dispersion, property/direction "
        "проверяются отдельно. Source shape description и concentration dependency не становятся solvent answer. "
        "Старые решения v0.6 неизменны; scientific admission отсутствует.</p>"
        '<table id="partial"><thead><tr><th>Case</th><th>Arm/window</th><th>Owned particle</th>'
        "<th>Attached dispersion</th><th>Eligible records / role-complete links</th><th>Requested requirements</th></tr></thead><tbody>"
    )
    for row in report["records"]:
        r = row["role_summary"]
        values = [row["case_id"], row["arm"] + "/" + row["window_qualifier"], r["particle_owner"], r["dispersion"],
                  str(r["eligible_relations"]) + "/" + str(r["complete_role_links"]), r["requested_complete"]]
        extra += "<tr>" + "".join("<td>" + html.escape(str(v)) + "</td>" for v in values) + "</tr>"
    extra += "</tbody></table><h2>14 frozen real windows / six works: raw source, roles and blocked requests</h2>"
    extra += "<details><summary>Полный real packet и diagnostics</summary><pre>"
    extra += html.escape(json.dumps(report["real_atomic_records"], ensure_ascii=False, indent=2)) + "</pre></details>"
    files.save(output / "review.html", raw.replace(marker, extra + marker).encode())


def run(output: Path, policy: files.NetworkPolicy) -> dict[str, Any]:
    settings = files.configure()
    files.verify_manifest(PREVIOUS)
    previous = json.loads((PREVIOUS / "report.json").read_bytes())
    files.verify(previous["bindings"])
    packet = json.loads(PACKET.read_bytes())
    files.verify(packet["bindings"])
    scan = json.loads(INSPECTION.read_bytes())
    files.verify(scan["bindings"])
    paths = [Path(__file__), ROOT / "scripts/particle_attachment_audit.py", ROOT / "scripts/inspect_particle_sources.py",
             ROOT / "scripts/prepare_particle_attachment_cases.py", ROOT / "scripts/verify_particle_attachment_review.py",
             ROOT / "tests/unit/test_particle_attachment_audit.py", ROOT / "tests/unit/test_particle_attachment_review.py",
             PROTOCOL, PACKET, CONTROLS, INSPECTION, ROOT / "docs/records/particle_attachment_recipe_v0.7.json",
             PREVIOUS / "report.json", PREVIOUS / "manifest.json"]
    bindings = {**previous["bindings"], **files.bindings(paths)}
    new_controls, real = controls(), real_records(packet)
    old_rows = [*previous["older_control_replays"], *previous["chain_controls"]["records"]]
    older = []
    for row in old_rows:
        result = v7.audit(row["question"], row["sources"], baseline_adequate=False)
        if base_result(result) != row["analysis"]:
            raise ValueError("Older control result changed")
        older.append({"id": row["id"], "question": row["question"], "sources": row["sources"], "analysis": result})
    records, corpus = load_records(), json.loads((CAPTURE / "corpus.json").read_bytes())
    if len(records) != 328 or len(older) != 193 or len(real) != 14:
        raise ValueError("Frozen input inventory changed")
    output.mkdir(parents=True, exist_ok=False)
    (output / "records").mkdir()
    for path in paths:
        if any(path.is_relative_to(ROOT / name) for name in ("scripts", "tests", "docs")):
            target = output / "source_snapshot" / path.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            files.save(target, path.read_bytes())
    files.write(output / "frozen_inputs.json", {"version": v7.VERSION, "bindings": bindings})
    reports = []
    for index, record in enumerate(records):
        validate_sources(record["trace"], corpus)
        proof = replay_service(record, settings)
        evidence, baseline = record["trace"]["evidence"], record["trace"]["metadata"]["evidence_adequacy"]
        arms = evaluate(record["request"]["question"], evidence, baseline["adequate"])
        if arms["v6"] != previous["records"][index]["analysis"]:
            raise ValueError("Frozen v0.6 diagnostic differs")
        if arms != evaluate(record["request"]["question"], evidence, baseline["adequate"]):
            raise ValueError("Repeated atomic diagnostics differ")
        analysis = arms["v7"]
        item = {k: v for k, v in record.items() if k not in {"trace", "request"}}
        item.update(question=record["request"]["question"], baseline_adequacy=baseline, analysis=analysis,
                    arms=arms if analysis["requirements"]["in_scope"] else None, role_summary=role_summary(analysis),
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
        "version": v7.VERSION, "evidence_sets": 328, "service_full_trace_replays": 328,
        "arm_diagnostic_executions": 1968, "diagnostic_arm_count": 3, "scoped_sets": len(scoped),
        "outside_scope_baseline_preserved": 328 - len(scoped), "v6_exact_replays": 328,
        "owned_particle_sets": sum(r["role_summary"]["particle_owner"] for r in scoped),
        "attached_dispersion_sets": sum(r["role_summary"]["dispersion"] for r in scoped),
        "eligible_particle_sets": sum(bool(r["analysis"]["particle_relations"]) for r in scoped),
        "eligible_particle_observations": sum(len(r["analysis"]["particle_relations"]) for r in scoped),
        "unique_raw_particle_units": len({g["raw_unit_sha256"] for r in scoped for g in r["analysis"]["exact_particle_groups"]}),
        "role_complete_link_observations": sum(r["role_summary"]["complete_role_links"] for r in scoped),
        "requested_complete_sets": sum(r["analysis"]["particle_requirements_met"] for r in scoped),
        "constructed_controls": len(new_controls), "older_control_replays": len(older), "real_windows": len(real),
        "real_pdf_works": packet["pdfs"], "real_requested_complete": sum(r["analysis"]["particle_requirements_met"] for r in real),
        "local_source_pdf_pages_scanned": scan["pages_scanned"], "source_pages_with_diagnostics": len(scan["extraction_diagnostics"]),
        "corrupted_source_rejected": True, "corrupted_baseline_rejected": True, "verified_bindings": len(bindings),
        "pdf_hashes_checked": len(previous["articles"]), "fresh_reference_windows": len(previous["reference_windows"]),
        "runtime_changed": False, "db_calls": 0, "search_calls": 0, "embedding_calls": 0, "model_calls": 0,
        "oauth_calls": 0, "slot_reservations": 0, "network_denials": policy.denied,
        "scientific_acceptance": "not_established", "independent_accuracy": None, "answer_quality_plan_completion_percent": 75,
        "limits": ["finite local particle syntax; descriptions and concentration are not solvent dependencies",
                   "no scientific/value owner or experiment established; no condition propagation",
                   "new real windows exposed and assistant-labelled, not independent scientific accuracy",
                   "old v0.6 decisions unchanged; no runtime integration",
                   "native MuPDF warnings preserved; browser/PDF visual/full suite/mypy not run"],
    }
    report = {"summary": summary, "bindings": bindings, "records": reports, "atomic_controls": new_controls,
              "real_atomic_records": real, "older_control_replays": older,
              "controls": {"new": new_controls, "older": older}, "extraction_diagnostics": scan["extraction_diagnostics"],
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
