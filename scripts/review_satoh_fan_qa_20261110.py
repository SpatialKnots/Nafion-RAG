"""Read-only review of the closed twenty-case development check, never inference."""

from __future__ import annotations

import html
import json
import os
from collections import Counter
from pathlib import Path

from scripts import gigachat_answer_smoke as files
from scripts import run_satoh_fan_qa_20261110 as run

INTAKE = run.ROOT / "output/satoh_fan_qa_20261110/intake_v02"
OUT = run.BASE / "review_v01"


def read(path):
    return json.loads(path.read_bytes())


def main():
    closed = read(run.BASE / "scope_closed_v01.json")
    if closed["remaining_allowance"] != 0 or not all(c["allowance_closed"] for c in closed["cases"]):
        raise ValueError("Reference access requires closed dispatch scope")
    contracts = run.preparations()
    run.validate_approval(read(run.BASE / "approval_v01.json"), contracts)
    files.verify_manifest(INTAKE)
    intake = read(INTAKE / "report.json")
    original = (INTAKE / "user_input_original.md").read_bytes().decode("utf-8")
    references = {c["id"]: c for c in intake["parsed"]["cases"]}
    rows, links, snapshots = [], [], []

    def link(path, label, page=None):
        if not path.is_file():
            raise ValueError("Missing report link: " + str(path))
        links.append(str(path))
        url = Path(os.path.relpath(path, OUT)).as_posix() + (f"#page={page}" if page else "")
        return '<a href="' + html.escape(url, quote=True) + '">' + html.escape(label) + '</a>'

    def detail(label, value):
        text = value if isinstance(value, str) else files.encode(value).decode()
        return "<details><summary>" + html.escape(label) + "</summary><pre>" + html.escape(text) + "</pre></details>"

    cards, table = [], []
    for cid, contract in contracts.items():
        prepared, folder = run.BASE / "prepared_v01" / cid, run.BASE / cid
        reference = references[cid]
        for key in ("question_span", "reference_answer_span", "source_pointer_span"):
            span = reference[key]
            if original[span["start"]:span["end"]] != span["text"]:
                raise ValueError("Original question/reference/source span changed")
        case = contract["case"]
        if reference["question_span"]["text"] != case["question_original"]:
            raise ValueError("Question differed from original")
        result = read(folder / "result.json") if (folder / "result.json").exists() else {}
        live = folder / "live"
        if live.exists():
            files.verify_manifest(live)
            files.verify_manifest(folder / "authorized_inputs")
            if result != read(live / "result.json"):
                raise ValueError("Live result differs from case summary")
            for name in ("trace.json", "sources.json", "articles.json", "request.json"):
                if (live / name).exists() and (live / name).read_bytes() != (prepared / name).read_bytes():
                    raise ValueError("Actual production inputs differed from frozen preparation")
            slot = files.LEDGER / contract["request_sha256"]
            if read(slot / "result.json") != result or read(slot / "scope_closed_satoh_fan_20261110_v01.json")["resend_authorized"]:
                raise ValueError("Attempt ledger/closure mismatch")
            snapshots.extend([live / "manifest.json", slot / "result.json", slot / "scope_closed_satoh_fan_20261110_v01.json"])
        trace = read(prepared / "trace.json")
        evidence = trace["evidence"]
        if any(e["article_id"] != case["article_id"] for e in evidence):
            raise ValueError("Evidence article scope mismatch")
        sources = read(prepared / "sources.json")
        for page in sources["pages"].values():
            if files.sha(Path(page["original_pdf_path"]).read_bytes()) != case["original_pdf_sha256"]:
                raise ValueError("Source original PDF changed")
        api = result.get("answer", {})
        if result.get("status") == "gate_rejected":
            if api != read(prepared / "gate_response.json")["body"] or result.get("model_attempts") != 0:
                raise ValueError("Blocked result differs from observed production gate")
        elif result and live.exists() and (live / "api_response.json").exists():
            if read(live / "api_response.json")["body"] != api:
                raise ValueError("Actual API body changed")
        adequacy = trace["metadata"].get("evidence_adequacy", {})
        declared_pages = sorted(set(reference["source_locations"]["pdf_pages"]
                                    + reference["source_locations"]["named_methods_pdf_pages"]))
        selected_pages = {p for e in evidence for p in range(e["page_start"], e["page_end"] + 1)}
        location_overlap = {"declared_reference_PDF_pages": declared_pages,
                            "selected_chunk_page_ranges": [[e["page_start"], e["page_end"]] for e in evidence],
                            "declared_pages_outside_selected_ranges": sorted(set(declared_pages) - selected_pages),
                            "meaning": "range_overlap_only_not_complete_page_or_claim_support"}
        row = {"id": cid, "question": case["question_original"], "scoped_question": case["question"],
               "status": result.get("status", "not_dispatched"), "api_status": api.get("status"),
               "actual_asgi_http_status": result.get("http_status") if live.exists() else None,
               "preparation_service_status": read(prepared / "gate_response.json")["body"]["status"]
                   if not contract["generation_reached"] else "provider_boundary_reached_unsent",
               "model_attempts": result.get("model_attempts", 0), "oauth_attempts": result.get("oauth_attempts", 0),
               "usage": result.get("usage"), "returned_model": result.get("returned_model"),
               "elapsed_seconds": result.get("elapsed_seconds"), "actual_cost": None,
               "adequacy": adequacy, "answer": api, "reference_original": reference["reference_answer_span"],
               "reference_location_overlap": location_overlap,
               "source_pointer_original": reference["source_pointer_span"], "source_locations": reference["source_locations"],
               "evidence": evidence, "source_registry": sources, "request_sha256": contract["request_sha256"],
               "request_bytes": contract["request_bytes"], "reference_agreement_score": None,
               "scientific_validity": "not_evaluated", "independent_accuracy": None,
               "network_denials": result.get("network_denials", []), "gold_read_denials": contract["gold_read_denials"]}
        rows.append(row)
        snapshots.extend([prepared / "manifest.json", prepared / "contract.json"])
        if (folder / "result.json").exists():
            snapshots.append(folder / "result.json")
        answer_text = api.get("answer") or api.get("detail") or "Ответ не выдан"
        table.append("<tr><td><a href='#" + cid + "'>" + cid + "</a></td><td>" + html.escape(row["status"])
                     + "</td><td>" + str(row["model_attempts"]) + "</td><td>"
                     + html.escape(str(adequacy.get("reason"))) + "</td></tr>")
        source_links = []
        for e in evidence:
            source_links.append(link(Path(case["original_pdf_path"]),
                                     f'{e["citation_id"]}: PDF {e["page_start"]}–{e["page_end"]}', e["page_start"]))
        artifacts = [link(prepared / "trace.json", "Точный trace"), link(prepared / "sources.json", "Реестр источников")]
        if live.exists():
            artifacts.append(link(live / "api_response.json", "Исходный API-ответ") if (live / "api_response.json").exists()
                             else link(live / "result.json", "Ошибка запуска"))
            for name in ("request.json", "response.bin"):
                if (live / name).exists():
                    artifacts.append(link(live / name, name))
        else:
            artifacts.append(link(prepared / "gate_response.json", "Исходный ответ service, без ASGI/модели"))
        cards.append(f'<section id="{cid}"><h2>{cid}</h2><p>' + html.escape(case["question_original"])
                     + "</p><p><b>Результат:</b> " + html.escape(row["status"]) + "</p><pre>" + html.escape(answer_text)
                     + "</pre>" + detail("Эталон пользователя — научная проверка отдельно", reference["reference_answer_span"]["text"])
                     + detail("Исходный указатель источника и PDF mapping", {"original": reference["source_pointer_span"]["text"],
                                                                            "mapped": reference["source_locations"],
                                                                            "selected_ranges": location_overlap})
                     + detail("Достаточность evidence и параметры вопроса", {"question": case["question"], "adequacy": adequacy})
                     + "<p>" + " | ".join(source_links) + "</p>" + detail("Отобранные raw chunks", evidence)
                     + detail("Полный результат", result) + "<p>" + " | ".join(artifacts) + "</p></section>")
    counts = dict(Counter(r["status"] for r in rows))
    summary = {"version": run.VERSION, "cases": len(rows), "status_counts": counts,
               "model_attempts": sum(r["model_attempts"] for r in rows), "oauth_attempts": sum(r["oauth_attempts"] for r in rows),
               "actual_asgi_requests": sum(r["actual_asgi_http_status"] is not None for r in rows),
               "answered": sum(r["api_status"] == "answered" for r in rows), "actual_cost": None,
               "cases_with_some_declared_reference_pages_outside_selected_ranges": sum(
                   bool(r["reference_location_overlap"]["declared_pages_outside_selected_ranges"]) for r in rows),
               "usage": {key: sum((r["usage"] or {}).get(key, 0) for r in rows)
                         for key in ("prompt_tokens", "completion_tokens", "total_tokens")},
               "references_used_for_inference": False, "agent_reference_exposure": True,
               "independent_evaluation": False, "score": None, "scientific_validity": "not_evaluated",
               "all_allowances_closed": True, "automatic_retries": 0, "fallbacks": 0,
               "app_runtime_changes": 0, "fresh_PDF_extraction_or_visual_review": False,
               "prior_supplement_caveats": ["Fan_02", "Fan_07", "Fan_08"],
               "panel_pointer_caveat": "Fan_07 caption d, body/visual recovery e; original preserved",
               "network_denials": sum(len(r["network_denials"]) for r in rows),
               "gold_read_denials": sum(len(r["gold_read_denials"]) for r in rows)}
    if summary["model_attempts"] != closed["model_attempts"] or summary["oauth_attempts"] != closed["oauth_attempts"]:
        raise ValueError("Closed scope counter mismatch")
    report = {"summary": summary, "cases": rows, "provenance": intake["provenance"],
              "original_rubric": intake["parsed"]["rubric_span"], "rubric_applied": False,
              "original_source_observations": intake["source_observations"]}
    snapshots += [Path(__file__), INTAKE / "manifest.json", run.BASE / "approval_v01.json", run.BASE / "scope_closed_v01.json"]
    report["bindings"] = files.bindings(snapshots)
    files.verify(report["bindings"])
    OUT.mkdir(exist_ok=False)
    files.write(OUT / "report.json", report)
    heading = ("<h1>ARIADNE:20 вопросов Satoh/Fan</h1><p>Development-проверка. "
               "Эталоны уже видны агенту; независимая точность не измерена.</p>")
    note = ("<p>Отказы на подготовке — реальные результаты production service в read-only БД; ASGI и модель для них не запускались. "
            "HTTP200 сам по себе не означает ответ или научную корректность. Шкала0/1/2 пока не применена.</p>"
            "<p>Fan02/07/08: supplementary не предоставлены. Fan07:caption указывает d, основной текст и визуальный recovery panel e. "
            "Исходный эталон сохранён. Свежий визуальный просмотр PDF в этом запуске не выполнялся.</p>")
    document = ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>Satoh/Fan production check</title>'
                '<style>body{font:16px system-ui;max-width:1200px;margin:auto;padding:24px;background:#fafafa;color:#18252c}'
                'table{border-collapse:collapse;width:100%}td,th{padding:10px;border:1px solid #aaa;text-align:left}'
                'pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#eef2f4;padding:12px}section{margin:32px 0;'
                'border-top:2px solid #597888}details{padding:8px}a{color:#16579a}</style>' + heading + note
                + detail("Итоги и ограничения", summary) + "<table><thead><tr><th>Вопрос</th><th>Статус</th><th>Model POST</th>"
                "<th>Причина adequacy</th></tr></thead><tbody>" + "".join(table) + "</tbody></table>" + "".join(cards) + "</html>")
    files.save(OUT / "review.html", document.encode())
    files.write(OUT / "verification.json", {"cases": len(rows), "original_spans_verified": 60,
                "existing_local_links": len(links), "bindings_verified": len(report["bindings"]),
                "exact_input_and_ledger_checks": True, "browser_layout_verified": False})
    files.manifest(OUT)
    print(json.dumps(summary, ensure_ascii=True))


if __name__ == "__main__":
    main()
