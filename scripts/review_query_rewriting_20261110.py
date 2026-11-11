"""Closed-scope paired development comparison and offline gate ablations."""

from __future__ import annotations

import html
import json
import os
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from app.generation.evidence_adequacy import assess_evidence_adequacy
from app.generation.providers import Evidence
from app.retrieval.cross_lingual import glossary_terms_for_concepts
from scripts import gigachat_answer_smoke as f
from scripts import query_rewriting_experiment as qr
from scripts import run_query_rewriting_20261110 as run


def read(path):
    return json.loads(path.read_bytes())


def main():
    base = run.BASE
    closed = read(base / "answers_closed_v01.json")
    if closed["remaining_allowance"] or read(base / "rewrite_closed_v01.json")["remaining_allowance"]:
        raise ValueError("All scopes must close before references/old outputs are read")
    f.verify_manifest(base / "input_freeze_v01")
    f.verify(read(base / "input_freeze_v01/runtime.json")["input_bindings"])
    f.verify_manifest(base / "plans_freeze_v01")
    f.verify(read(base / "plans_freeze_v01/bindings.json"))
    old = f.ROOT / "output/satoh_fan_qa_run_20261110"
    f.verify_manifest(old / "input_freeze_v01")
    f.verify(read(old / "input_freeze_v01/runtime.json")["input_bindings"])
    f.verify_manifest(old / "review_v01")
    old_report = read(old / "review_v01/report.json")
    old_cases = {c["id"]: c for c in old_report["cases"]}
    intake_path = f.ROOT / "output/satoh_fan_qa_20261110/intake_v02/report.json"
    intake = read(intake_path)
    references = {c["id"]: c for c in intake["parsed"]["cases"]}
    plans = {c["id"]: c for c in read(base / "plans_freeze_v01/plans.json")["cases"]}
    cases = read(base / "input_freeze_v01/questions.json")["cases"]
    out = base / "review_v01"
    links = []

    def link(path, title, page=None):
        if not path.is_file():
            raise ValueError("Missing report artifact: " + str(path))
        links.append(str(path))
        url = Path(os.path.relpath(path, out)).as_posix() + (f"#page={page}" if page else "")
        return '<a href="' + html.escape(url, quote=True) + '">' + html.escape(title) + '</a>'

    def detail(title, value):
        return '<details><summary>' + html.escape(title) + '</summary><pre>' + html.escape(
            value if isinstance(value, str) else f.encode(value).decode()) + '</pre></details>'

    def assessment(question, evidence, trace):
        concepts = trace.get("metadata", {}).get("retrieval", {}).get("cross_lingual", {}).get("matched_concepts", [])
        return assess_evidence_adequacy(question, evidence, concept_terms=glossary_terms_for_concepts(concepts))

    rows, cards, table, ablations = [], [], [], []
    bindings = f.bindings([Path(__file__), base / "answers_closed_v01.json", base / "rewrite_closed_v01.json",
                           base / "answer_approval_v01.json", base / "plans_freeze_v01/manifest.json",
                           old / "review_v01/manifest.json", intake_path])
    for case in cases:
        cid = case["id"]
        previous, ref, plan = old_cases[cid], references[cid], plans[cid]
        prepared = base / "prepared_v01" / cid
        f.verify_manifest(prepared)
        folder = base / "answers" / cid
        result = read(folder / "result.json") if (folder / "result.json").exists() else {
            "status": "not_dispatched", "model_attempts": 0, "oauth_attempts": 0}
        answer = result.get("answer", {})
        if result["status"] == "identical_native_reuse":
            if (prepared / "request.json").read_bytes() != (old / "prepared_v01" / cid / "request.json").read_bytes():
                raise ValueError("Reused response requires exact original native body")
            answer = previous["answer"]
        live = folder / "live"
        if live.exists():
            f.verify_manifest(live)
            f.verify_manifest(folder / "authorized_inputs")
            for name in ("trace.json", "sources.json", "articles.json", "request.json"):
                if (live / name).exists() and (live / name).read_bytes() != (prepared / name).read_bytes():
                    raise ValueError("Live and prepared inputs differ")
            if read(live / "result.json") != result:
                raise ValueError("Live result differs")
            response_path = live / "response.bin"
            if response_path.exists():
                if f.sha(response_path.read_bytes()) != result["observed_response_sha256"]:
                    raise ValueError("Native response SHA mismatch")
            slot = f.LEDGER / read(prepared / "contract.json")["request_sha256"]
            if read(slot / "result.json") != result or read(slot / "query_rewriting_answer_closed_v01.json")["resend_authorized"]:
                raise ValueError("Ledger result/closure mismatch")
            bindings.update(f.bindings([live / "manifest.json", slot / "result.json"]))
        trace = read(prepared / "trace.json") if (prepared / "trace.json").exists() else None
        evidence = trace["evidence"] if trace else []
        if any(e["article_id"] != case["article_id"] for e in evidence):
            raise ValueError("Wrong article evidence")
        declared = set(ref["source_locations"]["pdf_pages"] + ref["source_locations"]["named_methods_pdf_pages"])
        selected_pages = {p for e in evidence for p in range(e["page_start"], e["page_end"] + 1)}
        missing = sorted(declared - selected_pages)
        if plan["accepted"]:
            old_trace = read(old / "prepared_v01" / cid / "trace.json")
            old_ev, new_ev = [Evidence(**e) for e in previous["evidence"]], [Evidence(**e) for e in evidence]
            original_old = assessment(case["question"], old_ev, old_trace)
            original_new = assessment(case["question"], new_ev, trace)
            from app.generation import service
            with qr.activate(case["question"], plan["plan"]):
                english_old = service.assess_evidence_adequacy(case["question"], old_ev)
                english_new = service.assess_evidence_adequacy(case["question"], new_ev)
            ablation = {"id": cid, "diagnostic_only_not_full_service_or_scientific_acceptance": True,
                        "baseline": asdict(original_old), "ranking_only": asdict(original_new),
                        "english_gate_only": asdict(english_old), "ranking_and_english_gate": asdict(english_new)}
            ablations.append(ablation)
        else:
            ablation = {"id": cid, "excluded_reason": "rewrite_rejected", "denominator_retained": True}
        row = {"id": cid, "question": case["question_original"], "baseline_status": previous["status"],
               "baseline_answer": previous["answer"], "rewrite": plan, "result": result, "answer": answer,
               "baseline_declared_pages_outside_ranges": previous["reference_location_overlap"]["declared_pages_outside_selected_ranges"],
               "declared_reference_pages": sorted(declared), "new_declared_pages_outside_ranges": missing,
               "selected_raw_evidence": evidence, "ablations": ablation,
               "reference": ref["reference_answer_span"], "source_pointer": ref["source_pointer_span"],
               "independent_accuracy": None, "scientific_validity": "not_evaluated", "score": None}
        rows.append(row)
        page_links = [link(Path(case["original_pdf_path"]), f'{e["citation_id"]}:PDF{e["page_start"]}–{e["page_end"]}',
                           e["page_start"]) for e in evidence]
        artifact_links = [link(base / "rewrites" / cid / "result.json", "Результат переписывания")]
        if trace:
            artifact_links.append(link(prepared / "trace.json", "Новый trace"))
        if (live / "api_response.json").exists():
            artifact_links.append(link(live / "api_response.json", "Исходный API-ответ"))
        table.append(f'<tr><td><a href="#{cid}">{cid}</a></td><td>' + html.escape(previous["status"])
                     + '</td><td>' + html.escape(result["status"]) + '</td><td>' + str(plan["accepted"])
                     + '</td><td>' + html.escape(str(previous["reference_location_overlap"]["declared_pages_outside_selected_ranges"]))
                     + ' → ' + html.escape(str(missing)) + '</td></tr>')
        cards.append(f'<section id="{cid}"><h2>{cid}</h2><p>' + html.escape(case["question_original"])
                     + '</p>' + detail("Переписывание и смысловая проверка", plan)
                     + '<h3>Новый ответ</h3><pre>' + html.escape(answer.get("answer") or answer.get("detail") or result["status"])
                     + '</pre>' + detail("Прежний ответ", previous["answer"])
                     + detail("Эталон пользователя — exposed development", ref["reference_answer_span"]["text"])
                     + detail("Диагностические ablations — не дополнительные ответы", ablation)
                     + '<p>' + ' | '.join(page_links) + '</p>' + detail("Новые raw chunks", evidence)
                     + detail("Полный новый результат", result) + '<p>' + ' | '.join(artifact_links) + '</p></section>')
        bindings.update(f.bindings([prepared / "manifest.json", base / "rewrites" / cid / "manifest.json"]))
    rewrite_results = [read(base / "rewrites" / c["id"] / "result.json") for c in cases]
    summary = {"version": qr.VERSION, "cases": 20, "meaning_accepted": sum(c["rewrite"]["accepted"] for c in rows),
        "baseline_answered": old_report["summary"]["answered"],
        "new_answered": sum(c["answer"].get("status") == "answered" for c in rows),
        "status_counts": dict(Counter(c["result"]["status"] for c in rows)),
        "baseline_cases_with_reference_pages_outside_ranges": sum(bool(c["baseline_declared_pages_outside_ranges"]) for c in rows),
        "new_cases_with_reference_pages_outside_ranges_including_rejected_as_no_context": sum(
            bool(c["new_declared_pages_outside_ranges"]) for c in rows),
        "gate_ablation_eligible_counts_on_accepted_cases": {
            name: sum(a[name]["adequate"] for a in ablations)
            for name in ("baseline", "ranking_only", "english_gate_only", "ranking_and_english_gate")},
        "rewrite_model_attempts": sum(r["model_attempts"] for r in rewrite_results),
        "rewrite_oauth_attempts": sum(r["oauth_attempts"] for r in rewrite_results),
        "answer_model_attempts": sum(c["result"]["model_attempts"] for c in rows),
        "answer_oauth_attempts": sum(c["result"]["oauth_attempts"] for c in rows),
        "usage": {stage: {k: sum((r.get("usage") or {}).get(k, 0) for r in rs)
                          for k in ("prompt_tokens", "completion_tokens", "total_tokens", "precached_prompt_tokens")}
                  for stage, rs in (("rewrite", rewrite_results), ("answer", [c["result"] for c in rows]))},
        "latency_seconds": {"rewrite_total": sum(r.get("elapsed_seconds", 0) for r in rewrite_results),
                            "answer_total": sum(c["result"].get("elapsed_seconds", 0) for c in rows)},
        "latency_measurement_scope": "sum of recorded rewrite transport/parse and answer ASGI execution timers; "
                                     "excludes worker startup and preflight hashing; not production user latency",
        "cost": None, "all_allowances_closed": True, "independent_evaluation": False, "score": None,
        "scientific_validity": "not_evaluated", "default_product_changes": 0,
        "network_denials": sum(len(r.get("network_denials", [])) for r in [*rewrite_results, *[c["result"] for c in rows]])}
    report = {"summary": summary, "cases": rows, "bindings": bindings,
              "limitations": ["Unblinded development with per-plan agent meaning review, no independent accuracy",
                  "Frozen old model samples; no new model sample when native bytes match baseline",
                  "Literal page-range overlap is not semantic support or full page inclusion",
                  "Finite existing lexical thresholds applied to translated questions; not general entailment",
                  "Requirements diagnostic only; no automatic claim completeness enforcement",
                  "Fan02/07/08 supplements unavailable; Fan07 original panel discrepancy preserved"]}
    f.verify(bindings)
    out.mkdir(exist_ok=False)
    f.write(out / "report.json", report)
    page = ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>Query rewriting experiment</title>'
            '<style>body{font:16px system-ui;max-width:1200px;margin:auto;padding:24px}pre{white-space:pre-wrap;'
            'overflow-wrap:anywhere;background:#eef2f4;padding:12px}td,th{padding:8px;border:1px solid #999}'
            'table{border-collapse:collapse;width:100%}section{margin-top:32px;border-top:2px solid #456}</style>'
            '<h1>ARIADNE:query rewriting на20 вопросах</h1><p>Development, не независимая научная оценка. '
            'Исходный вопрос/эталон сохранены; смысловые отказы не исключены из знаменателя.</p>'
            + detail("Итоги", summary) + detail("Ограничения", report["limitations"])
            + '<table><tr><th>Вопрос</th><th>До</th><th>После</th><th>Перевод принят</th><th>Пропущенные PDF страницы</th></tr>'
            + ''.join(table) + '</table>' + ''.join(cards) + '</html>')
    f.save(out / "review.html", page.encode())
    f.write(out / "verification.json", {"cases": 20, "existing_file_links": len(links), "bindings_verified": len(bindings),
                                        "baseline_manifests_unchanged": True, "browser_layout_verified": False})
    f.manifest(out)
    print(json.dumps(summary, ensure_ascii=True))


if __name__ == "__main__":
    main()
