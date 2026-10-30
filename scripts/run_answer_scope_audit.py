"""Offline audit/replay of saved maximum and operation cases, with exact source verification."""

from __future__ import annotations

import argparse
import html
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import gigachat_answer_smoke as files  # noqa: E402


def no_network(event: str, args: Any) -> None:
    if event in {"socket.connect", "socket.getaddrinfo", "socket.sendto"}:
        raise AssertionError("All network forbidden during offline scope audit")


def run(output: Path) -> dict[str, Any]:
    import fitz
    from sqlalchemy.engine import Engine

    from app.generation.gigachat import GigaChatAnswerProvider
    from scripts.answer_scope_audit import VERSION, PageSource, SuppliedEvidence, audit
    from scripts.event_spans_v02 import parse_proposal, validate_reply
    from scripts.event_value_ownership_audit import audit as operation_audit

    if output.exists():
        raise FileExistsError(output)
    baseline = ROOT / "output/user_swelling_answer_20261029"
    ownership = ROOT / "output/event_value_ownership_20261029/review_v02"
    retrieval = ROOT / "output/swelling_retrieval_audit_20261030/capture_v03"
    registry_path = ROOT / "output/experiment_sentence_links_20261029/review_v02/report.json"
    for folder in (baseline / "review_v02", ownership, retrieval):
        files.verify_manifest(folder)
    saved = json.loads((baseline / "review_v02/report.json").read_bytes())
    events = json.loads((ownership / "report.json").read_bytes())
    capture = json.loads((retrieval / "capture.json").read_bytes())
    for document in (saved, events, capture):
        files.verify(document["bindings"])
    bindings: dict[str, str] = {}
    for document in (saved, events, capture):
        for name, digest in document["bindings"].items():
            if name in bindings and bindings[name] != digest:
                raise ValueError("Frozen input bindings disagree: " + name)
            bindings[name] = digest
    support = ["scripts/answer_scope_audit.py", "scripts/run_answer_scope_audit.py", "tests/unit/test_answer_scope_audit.py",
               "docs/records/answer_scope_audit_protocol_v0.3.md", "output/answer_scope_tests_20261030_v03.xml"]
    bindings.update(files.bindings([ROOT / name for name in support] + [baseline / "review_v02/report.json",
        ownership / "report.json", retrieval / "capture.json", registry_path,
        ROOT / "docs/records/answer_scope_audit_protocol_v0.1.md", ROOT / "docs/records/answer_scope_audit_protocol_v0.2.md"]))
    originals = list(saved["sources"]["pages"].values())
    posthoc = saved["supplemental_pages"]
    pages = [PageSource(p["article_id"], p["page_number"], p["text_layer"], p["original_pdf_path"],
                       p["original_pdf_sha256"], p["page_text"], origin)
             for rows, origin in ((originals, "registered_original_run_page"), (posthoc, "posthoc_original_pdf_page")) for p in rows]
    supplied = [SuppliedEvidence(e["citation_id"], e["article_id"], e["chunk_id"], e["page_start"], e["page_end"],
                                saved["sources"]["chunk_layers"][e["chunk_id"]], e["text"]) for e in saved["trace"]["evidence"]]
    claims = saved["api_result"]["body"]["claims"]
    verified_pages: dict[tuple[str, int], str] = {}
    verified_pdfs: set[str] = set()

    def verify_page(raw: dict[str, Any]) -> None:
        pdf = Path(raw["original_pdf_path"])
        if str(pdf) not in verified_pdfs:
            if files.sha(pdf.read_bytes()) != raw["original_pdf_sha256"]:
                raise ValueError("Original PDF hash changed")
            bindings.update(files.bindings([pdf]))
            verified_pdfs.add(str(pdf))
        if files.sha(raw["page_text"].encode()) != raw["page_text_sha256"]:
            raise ValueError("Archived page text hash changed")
        key = (str(pdf), raw["page_number"])
        if key in verified_pages:
            if verified_pages[key] != raw["page_text"]:
                raise ValueError("Conflicting archived page text")
        else:
            with fitz.open(pdf) as document:
                if document[raw["page_number"] - 1].get_text("text") != raw["page_text"]:
                    raise ValueError("Fresh original PDF extraction differs")
            verified_pages[key] = raw["page_text"]

    operation_replays = []
    with patch.object(Engine, "connect", side_effect=AssertionError("DB forbidden")) as db_guard, patch.object(
            GigaChatAnswerProvider, "_post", side_effect=AssertionError("Provider forbidden")) as provider_guard:
        for p in originals + posthoc:
            verify_page(p)
        before = audit(saved["question"], claims, supplied, pages[:len(originals)])
        broader = audit(saved["question"], claims, supplied, pages)
        if before != audit(saved["question"], claims, supplied, pages[:len(originals)]) or broader != audit(
                saved["question"], claims, supplied, pages):
            raise ValueError("Scope audit replay differs")
        if len(events["cases"]) != 12:
            raise ValueError("Declared operation case inventory differs")
        for row in events["cases"]:
            verify_page(row["full_registered_page"])
            restored_fixture = validate_reply(row["constructed_fixture"]["contract_fixture"], row["source"])
            if operation_audit(row["source"], restored_fixture) != row["constructed_audit"]:
                raise ValueError("Constructed operation replay differs")
            result = {"id": row["case"]["id"], "source": row["source"], "case": row["case"],
                      "constructed_audit_identical": True, "original_constructed_audit": row["constructed_audit"], "live": None}
            live = row["saved_model_proposal"]
            if live is not None:
                path = ROOT / "output/event_span_live_pilot_20261029_v02/cases" / row["case"]["id"] / "live/response.bin"
                raw = path.read_bytes()
                if files.sha(raw) != live["raw_reply_sha256"]:
                    raise ValueError("Saved native response hash differs")
                restored = parse_proposal(raw, row["source"])
                if restored != live["original_restored"] or operation_audit(row["source"], restored) != live["audit"]:
                    raise ValueError("Original native/ownership replay differs")
                result["live"] = {"raw_native_replay_identical": True, "audit_identical": True,
                                  "original_result": live["original_result"], "original_audit": live["audit"],
                                  "formal_verdict_modified": False}
                bindings.update(files.bindings([path]))
            operation_replays.append(result)
        if db_guard.call_count or provider_guard.call_count:
            raise ValueError("Forbidden DB/provider operations attempted")

    # All TAC rows in the declared union, preserving versioned metadata observations.
    registry = json.loads(registry_path.read_bytes())
    observations: dict[str, list[dict[str, Any]]] = {}
    for article in saved["articles"]:
        observations.setdefault(article["article_id"], []).append({"origin": str(baseline / "prepared/articles.json"), "value": article})
    for case in registry["cases"]:
        path = Path(case["prepared_path"]) / "articles.json"
        bindings.update(files.bindings([path]))
        for article in json.loads(path.read_bytes()):
            item = {"origin": str(path), "value": article}
            if item not in observations.setdefault(article["article_id"], []):
                observations[article["article_id"]].append(item)
    scope_ids = {p.article_id for p in pages} | {r["case"]["article_id"] for r in events["cases"]}
    articles = []
    for article_id in sorted(scope_ids):
        values = observations[article_id]
        primary = values[0]["value"]
        fields = ("title", "authors", "journal", "year", "abstract")
        conflicts = [k for k in fields if any(v["value"].get(k) != primary.get(k) for v in values[1:])]
        articles.append({**primary, "metadata_observations": values, "metadata_conflicts": conflicts,
                         "metadata_policy": "first archived observation displayed; other versions retained, no repair"})
    if len(articles) != 6:
        raise ValueError("Declared six-work scope differs")
    for c in broader["source_candidates"]:
        source = next(p for p in pages if p.article_id == c["source"]["article_id"]
                      and p.page_number == c["source"]["page_number"] and p.text_layer == c["source"]["text_layer"])
        for key in ("relation", "number", "form_anchor", "statement"):
            s = c[key]
            if source.page_text[s["start"]:s["end"]] != s["text"]:
                raise ValueError("Detected exact source anchor differs")
    summary = {"maximum_answer_cases": 1, "registered_run_pages": len(originals), "posthoc_pages": len(posthoc),
        "numeric_candidates_original_pages": len(before["source_candidates"]),
        "numeric_candidates_broader_pages": len(broader["source_candidates"]),
        "candidate_states": dict(Counter(c["state"] for c in broader["source_candidates"])),
        "operation_cases_replayed": len(operation_replays),
        "native_operation_replays": sum(r["live"] is not None for r in operation_replays),
        "fresh_pdf_pages_verified": len(verified_pages), "pdfs_verified": len(verified_pdfs), "tac_rows": len(articles),
        "db_connections": 0, "provider_transport_calls": 0, "model_calls": 0, "oauth_calls": 0,
        "scientific_confirmations": 0, "independent_accuracy": None}
    report = {"version": VERSION, "bindings": bindings, "summary": summary, "question": saved["question"],
        "original_system_api_result": saved["api_result"], "original_supplied_evidence": [e.__dict__ for e in supplied],
        "original_page_scope_audit": before, "broader_page_scope_audit": broader,
        "separate_prior_assistant_source_review": saved["assistant_source_review"],
        "prior_assistant_review_is_not_a_new_audit_prediction": True,
        "operation_replays": operation_replays, "articles": articles,
        "production_runtime_changed": False, "original_formal_verdicts_modified": False,
        "scientific_acceptance": "not_established", "exposure": "familiar_source_cases_and_constructed_controls_not_independent_gold"}
    files.verify(bindings)
    output.mkdir(parents=True, exist_ok=False)
    files.write(output / "report.json", report)
    render(report, output, VERSION)
    for name in support[:4]:
        destination = output / "source_snapshot" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        files.save(destination, (ROOT / name).read_bytes())
    files.verify(bindings)
    files.write(output / "manifest.json", {"version": VERSION, "outputs": {
        p.relative_to(output).as_posix(): files.sha(p.read_bytes())
        for p in sorted(output.rglob("*")) if p.is_file() and p.name != "manifest.json"}})
    return summary


def render(report: dict[str, Any], output: Path, version: str) -> None:
    def esc(value: Any) -> str:
        return html.escape(str(value), quote=True)

    def detail(label: str, value: Any) -> str:
        raw = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)
        return "<details><summary>" + esc(label) + "</summary><pre>" + esc(raw) + "</pre></details>"

    def cell(value: Any) -> str:
        return "Неизвестно / не собрано на этапе" if value is None else detail("Полный текст / значение", value)

    def candidate_table(audit: dict[str, Any]) -> str:
        body = '<table><thead><tr><th>Форма / число</th><th>Источник</th><th>Точный фрагмент</th><th>Диагностика</th></tr></thead><tbody>'
        for c in audit["source_candidates"]:
            s = c["source"]
            url = Path(s["original_pdf_path"]).as_uri() + "#page=" + str(s["page_number"])
            body += ('<tr><td>' + esc(c["form"] + " / " + c["value"]) + '<br>' + esc(c["unit"]) + '</td><td><a href="'
                + esc(url) + '">PDF, с.' + str(s["page_number"]) + '</a><br>' + esc(s["origin"]) + '</td><td>'
                + detail("Точная relation", c["relation"]) + detail("Полный исходный statement", c["statement"]) + '</td><td>'
                + esc(c["state"]) + detail("Все anchors / diagnostics / принадлежность evidence", c) + '</td></tr>')
        return body + '</tbody></table>'

    body = ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>ARIADNE — область научного ответа</title>'
        '<style>body{font:16px system-ui;margin:24px;color:#18333f}table{border-collapse:collapse;width:100%}'
        'td,th{border:1px solid #abc;padding:8px;vertical-align:top}pre{white-space:pre-wrap;overflow-wrap:anywhere}'
        '[hidden]{display:none!important}</style><h1>Offline-проверка области научного ответа</h1><p>' + esc(report["question"])
        + '</p><p>Algorithm: ' + esc(version) + '; input bindings SHA256: ' + files.sha(files.encode(report["bindings"]))
        + '.</p><p><strong>Научных подтверждений: 0. Runtime не изменён.</strong> '
        'Совпадение числа и формы — диагностический синтаксический признак. '
        'Температура, среда, роль значения и общий максимум требуют проверки связи с величиной.</p>'
        '<h2>Исходный ответ системы, без исправлений</h2>' + detail("Полные API status/body", report["original_system_api_result"])
        + '<h2>Только страницы исходного контекста</h2>'
        + detail("Требования и проверки claims", report["original_page_scope_audit"]["claims"])
        + candidate_table(report["original_page_scope_audit"])
        + '<h2>Дополнительные страницы, найденные после ответа</h2><p>Не были evidence исходного ответа. '
        'Более крупные числа ниже — кандидаты для проверки; это не автоматически подтверждённый новый максимум.</p>'
        + detail("Расширенная проверка claims", report["broader_page_scope_audit"]["claims"])
        + candidate_table(report["broader_page_scope_audit"])
        + detail("Температура и среда на странице не переносятся к числу", report["broader_page_scope_audit"]["source_context_inventory"])
        + detail("Прежняя отдельная проверка источника ассистентом; не предсказание нового алгоритма",
                 report["separate_prior_assistant_source_review"])
        + '<h2>Принадлежность величины операции: отдельный replay прежних событий</h2>')
    for row in report["operation_replays"]:
        body += '<article><h3>' + esc(row["id"]) + '</h3>' + detail("Исходный source / сохранённые результаты replay", row) + '</article>'
    body += ('<h2>TAC: все шесть работ этапа</h2><p>Архивные метаданные; независимая проверка не заявляется. '
        'Conclusions/Terms не собирались; варианты метаданных и расхождения сохранены.</p>'
        '<label>Поиск по таблице <input type="search" id="q"></label><table id="tac"><thead><tr>'
        + ''.join('<th>' + s + '</th>' for s in ('Title', 'Authors', 'Journal', 'Year', 'Abstract', 'Conclusions', 'Terms',
                                               'hyperlink to original file')) + '</tr></thead><tbody>')
    for a in report["articles"]:
        body += ('<tr>' + ''.join('<td>' + cell(a.get(k)) + '</td>' for k in
            ('title', 'authors', 'journal', 'year', 'abstract', 'conclusions', 'terms')) + '<td><a href="'
            + esc(Path(a["original_pdf_path"]).as_uri()) + '">Оригинальный PDF</a>'
            + detail("Происхождение и все варианты метаданных", a) + '</td></tr>')
    body += ('</tbody></table>' + detail("Итоги и ограничения", report["summary"])
        + '<script>document.getElementById("q").addEventListener("input",e=>{const s=e.target.value.toLowerCase();'
        'document.querySelectorAll("#tac tbody tr").forEach(r=>{r.hidden=!r.textContent.toLowerCase().includes(s)})});</script></html>')
    files.save(output / "review.html", body.encode())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sys.addaudithook(no_network)
    print(json.dumps(run(args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
