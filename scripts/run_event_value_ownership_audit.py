"""Offline source-region diagnostics for twelve fixtures and three saved replies."""

from __future__ import annotations

import argparse
import html
import json
import sys
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlparse
from urllib.request import url2pathname

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.generation.gigachat import GigaChatAnswerProvider  # noqa: E402
from scripts import gigachat_answer_smoke as files  # noqa: E402
from scripts.event_spans_v02 import parse_proposal  # noqa: E402
from scripts.event_value_ownership_audit import VERSION, audit  # noqa: E402


def no_network(event: str, args: tuple[object, ...]) -> None:
    if event in {"socket.connect", "socket.getaddrinfo", "socket.sendto", "socket.sendmsg"}:
        raise AssertionError("Network forbidden in source-region ownership audit")


def detail(label: str, value: object) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)
    return '<details><summary>' + html.escape(label) + '</summary><pre>' + html.escape(text) + '</pre></details>'


def summarize(audits: list[dict]) -> dict:
    selections = [s for a in audits for s in a["selections"]]
    return {"proposals": len(audits), "selection_states": dict(Counter(s["state"] for s in selections)),
            "duration_relation_states": dict(Counter(s["duration_relation"]["state"] for s in selections if s["duration_relation"])),
            "duration_cue_diagnostics": dict(Counter(d for s in selections if s["duration_relation"]
                                                     for d in s["duration_relation"]["diagnostics"])),
            "scientific_ownership_confirmations": 0}


def page_anchors(case: dict, result: dict) -> list[dict]:
    rows = []
    for selection in result["selections"]:
        row = {"event_id": selection["event_id"], "field": selection["field"], "source": case["source"]}
        for name in ("operation", "value"):
            span = selection[name]
            row[name] = None if span is None else {
                "page_start": case["page_start_offset"] + span["start"],
                "page_end": case["page_start_offset"] + span["end"], "text": span["text"]}
        rows.append(row)
    return rows


def render_audit(result: dict) -> str:
    body = '<table><thead><tr><th>Event / field</th><th>Operation</th><th>Selected source</th><th>Diagnostic</th></tr></thead><tbody>'
    for s in result["selections"]:
        duration = s["duration_relation"]
        state = s["state"] + ("; " + duration["state"] if duration else "")
        values = (s["event_id"] + " / " + s["field"], s["operation"]["text"],
                  s["value"]["text"] if s["value"] else "Нет выбранного значения; отсутствие не проверено", state)
        body += '<tr>' + ''.join('<td>' + html.escape(v) + '</td>' for v in values) + '</tr>'
    return body + '</tbody></table>' + detail("Полные области, точные anchors и ограничения", result)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sys.addaudithook(no_network)
    import fitz

    parent = ROOT / "output/event_spans_v02_20261029/review_v02"
    live_parent = ROOT / "output/event_span_live_pilot_20261029_v02/review_v02"
    for folder in (parent, live_parent):
        files.verify_manifest(folder)
    previous = json.loads((parent / "report.json").read_bytes())
    live = json.loads((live_parent / "report.json").read_bytes())
    files.verify(previous["bindings"])
    files.verify(live["bindings"])
    bindings = {**previous["bindings"], **live["bindings"], **files.bindings([
        Path(__file__), ROOT / "scripts/event_value_ownership_audit.py", ROOT / "tests/unit/test_event_value_ownership_audit.py",
        ROOT / "docs/records/event_value_ownership_audit_protocol_v0.1.md",
        ROOT / "output/event_value_ownership_regression_20261029_v04.xml",
        parent / "report.json", parent / "manifest.json", live_parent / "report.json", live_parent / "manifest.json"])}
    if len(previous["cases"]) != 12 or len(live["cases"]) != 3:
        raise ValueError("Expected the declared twelve-fixture / three-reply scope")
    live_cases = {r["id"]: r for r in live["cases"]}
    if len(live_cases) != 3 or not set(live_cases).issubset({r["case"]["id"] for r in previous["cases"]}):
        raise ValueError("Live case identities differ")
    registry_path = ROOT / "output/experiment_sentence_links_20261029/review_v02/report.json"
    registry = json.loads(registry_path.read_bytes())
    articles = {}
    for r in registry["cases"]:
        for a in json.loads((Path(r["prepared_path"]) / "articles.json").read_bytes()):
            articles[a["article_id"]] = a
    rows, fixture_audits, live_audits, pages, selected_articles = [], [], [], set(), {}
    with patch.object(GigaChatAnswerProvider, "_post", side_effect=AssertionError("Transport forbidden")) as transport:
        for previous_row in previous["cases"]:
            case = previous_row["case"]
            page = previous_row["full_registered_page"]
            source = previous_row["source"]
            pdf = Path(case["source"]["original_pdf_path"])
            if files.sha(pdf.read_bytes()) != case["source"]["original_pdf_sha256"]:
                raise ValueError("Original PDF changed")
            if files.sha(page["page_text"].encode()) != case["source"]["page_text_sha256"] or (
                    page["page_text"][case["page_start_offset"]:case["page_end_offset"]] != case["exact_text"]):
                raise ValueError("Raw page or excerpt changed")
            key = (str(pdf), case["page"])
            if key not in pages:
                with fitz.open(pdf) as document:
                    if document[case["page"] - 1].get_text("text") != page["page_text"]:
                        raise ValueError("Fresh PDF extraction differs")
                pages.add(key)
            result = audit(source, previous_row["restored_constructed_fixture"])
            fixture_audits.append(result)
            anchors = page_anchors(case, result)
            row = {"case": case, "source": source, "full_registered_page": page,
                   "constructed_fixture": previous_row["constructed_fixture"], "constructed_audit": result,
                   "constructed_page_anchors": anchors, "saved_model_proposal": None}
            if case["id"] in live_cases:
                saved = live_cases[case["id"]]
                folder = ROOT / "output/event_span_live_pilot_20261029_v02/cases" / case["id"] / "live"
                files.verify_manifest(folder)
                raw = (folder / "response.bin").read_bytes()
                restored = parse_proposal(raw, source)
                if restored != saved["restored"]:
                    raise ValueError("Original native replay differs")
                model_audit = audit(source, restored)
                live_audits.append(model_audit)
                row["saved_model_proposal"] = {"original_result": saved["result"], "original_restored": restored,
                                               "raw_native_reply": saved["raw_native_reply_text"], "raw_reply_sha256": files.sha(raw),
                                               "audit": model_audit, "page_anchors": page_anchors(case, model_audit),
                                               "original_formal_verdict_modified": False}
                anchors = [*anchors, *row["saved_model_proposal"]["page_anchors"]]
            for anchor_row in anchors:
                for name in ("operation", "value"):
                    a = anchor_row[name]
                    if a and page["page_text"][a["page_start"]:a["page_end"]] != a["text"]:
                        raise ValueError("Computed full-page source anchor differs")
            selected_articles[case["article_id"]] = articles[case["article_id"]]
            rows.append(row)
        if transport.call_count:
            raise ValueError("Offline audit attempted transport")
    summary = {"cases": len(rows), "source_documents": len(selected_articles), "fresh_pdf_pages_verified": len(pages),
               "constructed_fixtures": summarize(fixture_audits), "saved_live_proposals": summarize(live_audits),
               "native_replays_identical": len(live_audits), "new_api_oauth_calls": 0, "database_operations": 0,
               "postflight_transport_calls": 0, "scientific_acceptance": "not_evaluated", "independent_accuracy": None}
    report = {"version": VERSION, "bindings": bindings, "summary": summary,
              "runtime_versions": {"python": sys.version, "pymupdf": fitz.VersionBind}, "cases": rows,
              "algorithm_uses_reference_annotations": False, "runtime_installed": False}
    body = ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>ARIADNE — source-region ownership audit</title>'
            '<style>body{font:16px system-ui;margin:24px}table{border-collapse:collapse;width:100%}td,th{border:1px solid #abc;'
            'padding:8px;vertical-align:top}pre,blockquote{white-space:pre-wrap;overflow-wrap:anywhere}'
            '[hidden]{display:none!important}</style><h1>Величина и операция: локальные области источника</h1>'
            '<p>Ограниченная диагностика RU/EN по тексту и точным ссылкам, без чтения разметки и kind модели. '
            'Область рядом с операцией не подтверждает научного владельца. Shared/reference/unknown scope остаётся unresolved. '
            'Конфликт областей — диагностический сигнал, не автоматический отказ или scientific acceptance. '
            'Все исходные output, schema, разметка, отказы и закрытые бюджеты сохранены; новых вызовов нет.</p>'
            '<p>12 примеров ассистента и 3 сохранённых ответа GigaChat считаются раздельно. '
            'Источники уже известны разработчику; независимой оценки нет.</p><p>Algorithm: ' + VERSION
            + '; snapshot: ' + files.sha(files.encode(bindings)) + '</p><label>Поиск <input id="q" type="search"></label>'
            + detail("Сводка раздельных групп", summary))
    for row in rows:
        case = row["case"]
        body += '<article data-case data-search><h2>' + html.escape(case["id"]) + '</h2><p>' + html.escape(case["question"]) + '</p>'
        body += '<blockquote>' + html.escape(case["exact_text"]) + '</blockquote><a href="' + html.escape(
            Path(case["source"]["original_pdf_path"]).as_uri() + '#page=' + str(case["page"]), quote=True) + '">Original PDF</a>'
        model = row["saved_model_proposal"]
        if model:
            body += '<section data-model><h3>Сохранённый ответ GigaChat; исходный формальный допуск не изменён</h3>'
            body += render_audit(model["audit"]) + detail("Неизменённый raw reply и формальный результат", model) + '</section>'
        else:
            body += '<p>Ответ модели на этом этапе отсутствует; новых запросов нет.</p>'
        body += '<h3>Пример ассистента для разработки; не ответ модели</h3>' + render_audit(row["constructed_audit"])
        for label, field in (("Исходный constructed fixture и прежние open notes", "constructed_fixture"),
                             ("Точные anchors полной страницы", "constructed_page_anchors"),
                             ("Полная зарегистрированная страница", "full_registered_page"),
                             ("Каталог без изменений", "source"), ("Исходный случай и трассировка", "case")):
            body += detail(label, row[field])
        body += '</article>'
    body += '<h2>TAC: все пять работ</h2><table><thead><tr>' + ''.join('<th>' + x + '</th>' for x in (
        "Title", "Authors", "Journal", "Year", "Abstract", "Conclusions", "Terms", "Original file")) + '</tr></thead><tbody>'
    for article in selected_articles.values():
        body += '<tr data-tac data-search>'
        for field in ("title", "authors", "journal", "year", "abstract", "conclusions", "terms"):
            body += '<td>' + ("Отсутствует / не собрано на этой стадии" if article[field] is None else detail(
                "Развернуть", article[field])) + '</td>'
        body += '<td><a href="' + html.escape(Path(article["original_pdf_path"]).as_uri(), quote=True) + '">Original PDF</a></td></tr>'
    body += ('</tbody></table><script>document.getElementById("q").addEventListener("input",e=>{for(const r of '
             'document.querySelectorAll("[data-search]"))r.hidden=!r.textContent.toLocaleLowerCase().includes('
             'e.target.value.toLocaleLowerCase())})</script></html>\n')

    class CheckHTML(HTMLParser):
        def __init__(self) -> None:
            super().__init__()
            self.cases = self.tac = self.models = 0
            self.links: list[str] = []

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            values = dict(attrs)
            self.cases += tag == "article" and "data-case" in values
            self.tac += tag == "tr" and "data-tac" in values
            self.models += tag == "section" and "data-model" in values
            if tag == "a" and values.get("href"):
                self.links.append(str(values["href"]))

    check = CheckHTML()
    check.feed(body)
    if (check.cases, check.tac, check.models) != (12, 5, 3):
        raise ValueError("HTML scope differs")
    for href in check.links:
        url = urlparse(href)
        if url.scheme != "file" or not Path(url2pathname(url.path)).is_file():
            raise ValueError("Missing source PDF link")
    report["html_qa"] = {"method": "static_not_browser", "case_cards": check.cases, "tac_rows": check.tac,
                         "actual_model_sections": check.models, "existing_original_pdf_links": len(check.links)}
    files.verify(bindings)
    args.output.mkdir(parents=True, exist_ok=False)
    for name, digest in bindings.items():
        path = Path(name)
        if path.is_relative_to(ROOT) and path.suffix in {".py", ".md", ".json"} and path.relative_to(ROOT).parts[0] in {
                "scripts", "app", "docs", "tests"}:
            target = args.output / "source_snapshot" / path.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            raw = path.read_bytes()
            if files.sha(raw) != digest:
                raise ValueError("Source changed during snapshot")
            files.save(target, raw)
    files.write(args.output / "report.json", report)
    files.save(args.output / "review.html", body.encode())
    files.manifest(args.output)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
