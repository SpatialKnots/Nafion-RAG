"""Export explicit claim controls, independently check hashes and build local review."""

from __future__ import annotations

import argparse
import copy
import json
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from html import escape
from pathlib import Path

from app.generation.answer_evidence_packet import build_packet, serialize_packet
from app.generation.answer_requirements import build_requirements
from app.generation.claim_checks import VERSION, build_checks, fact_assertion, load_checks, save_checks
from scripts import gigachat_answer_smoke as files
from scripts.benchmark_retrieval_capture_20261105 import read
from scripts.check_requested_context_runtime_20261105 import render
from scripts.claim_checks_baseline_20261110 import BASE, PROTOCOL
from scripts.review_answer_evidence_packet_20261109 import independent_digest
from scripts.review_benchmark_retrieval_repair_20261105 import check_html, detail


def assertions(packet: dict) -> list[dict]:
    """Declared development comparisons, not answers or independent gold."""
    content = packet["content"]
    claims = [{"id": "bound_fact_" + str(i), "kind": "fact", "fact_ref": row["id"],
               "assertion": fact_assertion(row["fact"])} for i, row in enumerate(content["facts"])]
    if content["anchors"]:
        row = content["anchors"][0]
        quote = {"id": "exact_quote", "kind": "quotation", "anchor_ref": row["id"], "text": row["anchor"]["text"]}
        claims += [quote, {**quote, "id": "changed_quote", "text": quote["text"] + " "}]
    capacity = next((c for c in claims if c["kind"] == "fact" and c["assertion"]["property"] == "capacity_retention"), None)
    if capacity:
        for field in ("sample", "unit", "status", "current"):
            changed = copy.deepcopy(capacity)
            changed["id"] = "constructed_wrong_" + field
            if field in {"sample", "unit"}:
                changed["assertion"][field]["text"] = "OTHER_ASSERTED_VALUE"
            elif field == "status":
                changed["assertion"]["epistemic_status"] = "source_reported"
            else:
                changed["assertion"]["conditions"][field]["text"] = "999"
            claims.append(changed)
    unknown = next((c for c in claims if c["kind"] == "fact" and c["assertion"]["unknown_fields"]), None)
    if unknown:
        changed = copy.deepcopy(unknown)
        changed["id"] = "constructed_dropped_unknowns"
        changed["assertion"]["unknown_fields"] = []
        claims.append(changed)
    for i, row in enumerate(content["transformations"]):
        if row["arithmetic"]["operation"] == "sum":
            claim = {"id": "sum_" + str(i), "kind": "arithmetic", "transformation_ref": row["id"],
                     "assertion": {k: copy.deepcopy(row["arithmetic"][k]) for k in ("operands", "result", "unit")}}
            claims.append(claim)
            changed = copy.deepcopy(claim)
            changed["id"] = "constructed_wrong_sum_" + str(i)
            changed["assertion"]["result"] = "999"
            claims.append(changed)
    return claims


def independent_report_check(report: dict, packet: dict) -> int:
    events = report["journal"]["events"]
    previous = packet["journal"]["root_hash"]
    outputs = [*report["results"], report["stop"]]
    inputs = [*[independent_digest(c) for c in report["claims"]], packet["packet_id"]]
    if len(events) != len(outputs) or len(events) != len(inputs):
        raise ValueError("Claim journal event inventory differs")
    for i, (event, output, input_hash) in enumerate(zip(events, outputs, inputs, strict=True), 1):
        body = {k: v for k, v in event.items() if k != "event_hash"}
        if (event["sequence"] != i or event["previous_hash"] != previous or event["input_hash"] != input_hash
                or event["output_hash"] != independent_digest(output) or independent_digest(body) != event["event_hash"]
                or event["actor_kind"] != "deterministic_system" or event["scientific_validity"] != "not_evaluated"):
            raise ValueError("Independent claim event hash/sequence/binding failed")
        previous = event["event_hash"]
    if (previous != report["journal"]["root_hash"] or report["journal"]["parent_root_hash"] != packet["journal"]["root_hash"]
            or independent_digest({k: v for k, v in report.items() if k != "report_id"}) != report["report_id"]):
        raise ValueError("Independent claim root/report identity failed")
    for result in report["results"]:
        if result["scientific_validity"] != {"status": "not_evaluated"} or result["admission_changed"]:
            raise ValueError("Diagnostic claim comparison changed scientific/admission status")
        sources = {s["id"]: s for s in result["sources"]}
        for anchor in result["anchors"]:
            raw, data = sources[anchor["source_ref"]]["raw_text"], anchor["anchor"]
            if raw[data["start"]:data["end"]] != data["text"] or files.sha(raw.encode()) != data["raw_chunk_sha256"]:
                raise ValueError("Independent raw anchor/hash check failed")
    return len(events)


def run(output: Path, comparison: Path, junit: Path) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    (output / "checks").mkdir()
    files.verify_manifest(BASE / "freeze_v01")
    files.verify_manifest(comparison)
    scope = read(junit.with_suffix(".scope.json"))
    files.verify(scope["test_bindings"])
    files.verify(scope["app_bindings"])
    counts = {k: sum(int(s.get(k, 0)) for s in ET.parse(junit).getroot().iter("testsuite"))
              for k in ("tests", "failures", "errors", "skipped")}
    if scope["exit_code"] or scope["external_network_denials"] or counts["failures"] or counts["errors"]:
        raise ValueError("Claim check affected tests failed")
    frozen = read(BASE / "freeze_v01/bindings.json")
    files.verify({name: digest for name, digest in frozen.items() if Path(name).is_relative_to(files.ROOT / "app")})
    new = {str(p.resolve()) for p in files.ROOT.joinpath("app").rglob("*.py")} - set(frozen)
    if new != {str((files.ROOT / "app/generation/claim_checks.py").resolve())}:
        raise ValueError("Unexpected app additions outside offline checker")
    cases = read(files.ROOT / "output/answer_requirements_20261109/controls_v01.json")
    outcomes, fragments, events = [], [], 0
    statuses: Counter = Counter()
    for i, case in enumerate(cases):
        p = copy.deepcopy(case["parent"])
        parent = {"version": "answer_requirements_preparation_v0.1", "preparation": p, "requirements": build_requirements(p),
                  "generation_performed": False, "external_request_constructed": False, "network_ready": False}
        packet = build_packet(parent)
        original = serialize_packet(packet)
        claims = assertions(packet)
        report = build_checks(packet, parent, claims, expected_packet_id=packet["packet_id"])
        target = output / "checks" / f"report_{i:03}.json"
        kwargs = {"expected_packet_id": packet["packet_id"], "expected_report_id": report["report_id"]}
        save_checks(target, report, packet, parent, claims, **kwargs)
        restored = load_checks(target, packet, parent, claims, **kwargs)
        if serialize_packet(restored) != serialize_packet(report) or serialize_packet(packet) != original:
            raise ValueError("Report roundtrip or unchanged input packet check failed")
        for label, value in (("parent", parent), ("packet", packet), ("claims", claims)):
            files.save(output / "checks" / f"{label}_{i:03}.json", serialize_packet(value))
        events += independent_report_check(report, packet)
        if report["stop"]["baseline"] != packet["content"]["stop"]:
            raise ValueError("Original admission/blockers were altered")
        for result in report["results"]:
            statuses.update([result["semantic_support"]["status"]])
        outcomes.append({"id": case["id"], "origin": case["origin"], "claims": len(claims), "report_id": report["report_id"],
                         "stop": report["stop"]["reason"], "journal_events": len(report["journal"]["events"])})
        rows = []
        for claim, result in zip(claims, report["results"], strict=True):
            rows.append('<tr data-claim-row><td>' + escape(claim["id"]) + detail("Явное утверждение", claim)
                + "</td><td>" + escape(result["literal_presence"]["status"]) + "</td><td>"
                + escape(result["semantic_support"]["status"]) + "</td><td>" + escape(result["arithmetic"]["status"])
                + "</td><td>not_evaluated</td><td>" + detail("Точные цитаты, source/page/layer и основания", result) + "</td></tr>")
        fragments.append('<div data-claim-case><h3>' + escape(case["id"]) + " · " + escape(case["origin"]) + "</h3>"
            + "<p>Утверждения constructed из известных tuples; это не ответы модели. Реальные raw только в первом случае. "
              "Статус допуска и blockers сохранены. PDF page mapping не дополнялась.</p>"
            + detail("Итог и прежние blockers", report["stop"])
            + "<table><thead><tr><th>Утверждение</th><th>Наличие в raw</th><th>Конечный смысловой контракт</th>"
              "<th>Арифметика</th><th>Научная достоверность</th><th>Evidence</th></tr></thead><tbody>"
            + "".join(rows) + "</tbody></table></div>")
        print(json.dumps({"control": i + 1, "claims": len(claims)}), flush=True)
    previous = files.ROOT / "output/bounded_context_action_20261110/review_v01"
    files.verify_manifest(previous)
    prior = read(previous / "report.json")
    pdfs = [Path(a["original_pdf_path"]) for a in prior["articles"].values()]
    for article, path in zip(prior["articles"].values(), pdfs, strict=True):
        if files.sha(path.read_bytes()) != article["original_pdf_sha256"]:
            raise ValueError("Original corpus PDF changed")
    # No new PDF/page extraction: bind the unchanged prior source audit explicitly.
    sources = read(previous / "report.json")["source_matches"]
    for match in sources:
        anchor = match["anchor"]
        source = next(s for s in read(output / "checks/packet_000.json")["content"]["sources"]
                      if s["chunk_id"] == anchor["chunk_id"])
        if (source["raw_text"][anchor["start"]:anchor["end"]] != anchor["text"]
                or files.sha(source["raw_text"].encode()) != anchor["raw_chunk_sha256"]):
            raise ValueError("Prior real raw/PDF audit no longer matches the current packet")
    summary = {"version": VERSION, "tests": counts, "external_network_denials": scope["external_network_denials"],
        "controls": len(outcomes), "claims": sum(c["claims"] for c in outcomes), "independently_checked_events": events,
        "semantic_contract_statuses": dict(statuses), "old_app_files_changed": 0, "new_app_modules": sorted(new),
        "final_service_comparison": read(comparison / "summary.json"), "PDF_hashes_rechecked": len(pdfs),
        "prior_raw_PDF_anchor_bindings_rechecked": len(sources), "fresh_PDF_extraction": False,
        "real_model_calls": 0, "real_oauth_exchanges": 0, "new_slots": 0, "fresh_DB_preparation": False,
        "independent_scientific_accuracy": None, "browser_layout": "not_verified_prior_file_URL_policy_block",
        "limitations": ["Explicit diagnostic assertions, not free prose or generated answer extraction",
            "Finite tuple comparison, not general semantic entailment or scientific acceptance",
            "Real raw source is exposed and preparation synthetic; all adverse assertions constructed",
            "Current trusted parent/code required; internal integrity does not establish authenticity",
            "Offline CLI only; product API/UI integration and pilot remain separate work"]}
    report = {"summary": summary, "cases": copy.deepcopy(prior["cases"]), "articles": prior["articles"],
        "regressions": read(comparison / "summary.json")["regressions"], "controls": outcomes}
    document = render(report).replace("Сохранение запрошенного контекста в runtime", "Отдельные offline-проверки утверждений")
    document = document.replace("<p>Офлайн-сравнение реального service на замороженных", "<p>Ниже архивное сравнение контекста. "
                                "Новые проверки утверждений размещены перед TAC. Офлайн-сравнение service на замороженных")
    extra = ("<h2>Проверки утверждений: " + VERSION + "</h2><p>Наличие текста, конечный смысловой контракт, арифметика "
        "и научная достоверность разделены. Научная достоверность во всех случаях не оценена. "
        "Полное совпадение полей не подтверждает научное владение или связь отдельных результатов. "
        "Diff не объявляется научным противоречием. Прежние пять секций и TAC сохранены как архивный контекст, "
        "а не новые gains этого этапа.</p>" + "".join(fragments))
    document = document.replace("<h2>TAC:", extra + "<h2>TAC:")
    qa = check_html(document, article_count=len(prior["articles"]), case_count=5)
    if document.count("data-claim-case") != len(outcomes) or document.count("data-claim-row") != summary["claims"]:
        raise ValueError("HTML claim inventory differs")
    qa.update(claim_cases=len(outcomes), claim_rows=summary["claims"], browser_layout_verified=False)
    paths = [*files.ROOT.joinpath("app").rglob("*.py"), Path(__file__), PROTOCOL, junit, junit.with_suffix(".scope.json"),
        previous / "manifest.json", files.ROOT / "output/answer_requirements_20261109/controls_v01.json", *pdfs,
        *[files.ROOT / p for p in ("scripts/check_answer_claims.py", "scripts/test_claim_checks_20261110.py",
                                  "scripts/claim_checks_baseline_20261110.py", "tests/unit/test_claim_checks.py")]]
    report["bindings"] = files.bindings(paths)
    files.verify(report["bindings"])
    files.write(output / "report.json", report)
    files.write(output / "qa.json", qa)
    files.save(output / "review.html", document.encode())
    return {k: v for k, v in summary.items() if k != "final_service_comparison"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--comparison", type=Path, required=True)
    parser.add_argument("--junit", type=Path, required=True)
    args = parser.parse_args()
    policy = files.NetworkPolicy()
    sys.addaudithook(policy)
    summary = run(args.output, args.comparison, args.junit)
    files.write(args.output / "network.json", {"external_denials": policy.denied})
    if policy.denied:
        raise ValueError("External network attempted")
    files.manifest(args.output)
    print(json.dumps(summary, ensure_ascii=True), flush=True)


if __name__ == "__main__":
    main()
