"""Replay frozen event-pilot replies against post-hoc duration references offline."""

from __future__ import annotations

import argparse
import html
import json
import sys
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import url2pathname

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import gigachat_answer_smoke as files  # noqa: E402
from scripts.event_duration_evaluation import VERSION, evaluate  # noqa: E402


def no_network(event: str, args: tuple[object, ...]) -> None:
    if event in {"socket.connect", "socket.getaddrinfo", "socket.sendto", "socket.sendmsg"}:
        raise AssertionError("Network forbidden in offline event-duration evaluation")


def detail(label: str, value: object) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)
    return '<details><summary>' + html.escape(label) + '</summary><pre>' + html.escape(text) + '</pre></details>'


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sys.addaudithook(no_network)
    import fitz

    base = ROOT / "output/gigachat_event_pilot_20261029"
    parent = base / "review_v02"
    dataset_path = ROOT / "docs/records/event_duration_reference_v0.1.json"
    build_path = ROOT / "output/event_duration_evaluation_20261029/build_manifest_v01.json"
    files.verify_manifest(parent)
    previous = json.loads((parent / "report.json").read_bytes())
    files.verify(previous["postflight_bindings"])
    study = json.loads((base / "study_contract_v01.json").read_bytes())
    files.verify(study["bindings"])
    files.verify_manifest(base / "source_snapshot_v01")
    build = json.loads(build_path.read_bytes())
    files.verify(build["bindings"])
    if files.sha(dataset_path.read_bytes()) != build["reference_sha256"]:
        raise ValueError("Reference annotation changed since recording")
    dataset = json.loads(dataset_path.read_bytes())
    if dataset["version"] != "event_duration_reference_v0.1":
        raise ValueError("Unexpected reference version")
    refs = {r["case_id"]: r for r in dataset["cases"]}
    if len(refs) != len(dataset["cases"]) or set(refs) != {c["id"] for c in study["cases"]}:
        raise ValueError("Reference scope differs from the complete frozen pilot")
    bindings = {**study["bindings"], **previous["postflight_bindings"], **build["bindings"], **files.bindings([
        Path(__file__), ROOT / "scripts/event_duration_evaluation.py", ROOT / "tests/unit/test_event_duration_evaluation.py",
        ROOT / "docs/records/event_duration_evaluation_protocol_v0.1.md", dataset_path, build_path,
        parent / "report.json", parent / "manifest.json", base / "study_contract_v01.json"])}
    rows, articles, verified_pages = [], {}, set()
    for case_id, annotated in refs.items():
        prepared, live = (base / "cases" / case_id / name for name in ("prepared", "live"))
        files.verify_manifest(prepared)
        files.verify_manifest(live)
        bindings.update(files.bindings([p for folder in (prepared, live) for p in folder.iterdir() if p.is_file()]))
        source, case, page, article = [json.loads((prepared / name).read_bytes()) for name in (
            "catalog.json", "case.json", "source_page.json", "article.json")]
        if annotated["source"] != case["source"]:
            raise ValueError("Reference source identity differs")
        if files.sha(source["exact_text"].encode()) != case["quote_sha256"]:
            raise ValueError("Excerpt hash differs")
        if page["page_text"][case["page_start_offset"]:case["page_end_offset"]] != source["exact_text"]:
            raise ValueError("Excerpt offsets differ from the registered page")
        if files.sha(page["page_text"].encode()) != case["source"]["page_text_sha256"]:
            raise ValueError("Registered page hash differs")
        pdf = Path(case["source"]["original_pdf_path"])
        bindings.update(files.bindings([pdf]))
        if bindings[str(pdf.resolve())] != case["source"]["original_pdf_sha256"]:
            raise ValueError("Original PDF hash differs")
        key = (str(pdf), case["page"])
        if key not in verified_pages:
            with fitz.open(pdf) as document:
                if document[case["page"] - 1].get_text("text") != page["page_text"]:
                    raise ValueError("Fresh PDF text differs from the frozen page")
            verified_pages.add(key)
        raw = (live / "response.bin").read_bytes()
        result = evaluate(raw, source, annotated["reference"])
        original = json.loads((live / "result.json").read_bytes())
        if original["status"] != "output_rejected" or result["original_parser"]["accepted"] or (
                result["original_parser"]["error"] != original["error"]):
            raise ValueError("Original parser verdict no longer reproduces")
        articles[article["article_id"]] = article
        rows.append({"case": case, "source": source, "full_registered_page": page, "annotation": annotated,
                     "raw_native_reply": json.loads(raw), "original_result": original, "evaluation": result})
    summary = {"cases": len(rows), "original_rejections_preserved": len(rows),
               "raw_target_duration_comparisons": dict(Counter(
                   r["evaluation"]["events"][0]["target_comparison"]["state"] for r in rows)),
               "event_records_with_multiple_annotated_owners": sum(
                   e["multiple_annotated_operations_in_one_event"] for r in rows for e in r["evaluation"]["events"]),
               "cases_with_repeated_duration_selections": sum(bool(r["evaluation"]["repeated_duration_selections"]) for r in rows),
               "new_api_oauth_calls": 0, "scientific_acceptance": "not_evaluated", "independent_accuracy": None}
    report = {"version": VERSION, "bindings": bindings, "reference_metadata": {k: v for k, v in dataset.items() if k != "cases"},
              "runtime_versions": {"python": sys.version, "pymupdf": fitz.VersionBind}, "summary": summary,
              "fresh_pdf_pages_verified": len(verified_pages), "cases": rows, "runtime_installed": False}
    body = ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>ARIADNE — duration ownership audit</title>'
            '<style>body{font:16px system-ui;margin:24px}table{border-collapse:collapse;width:100%}td,th{border:1px solid #abc;'
            'padding:8px;vertical-align:top}pre,blockquote{white-space:pre-wrap;overflow-wrap:anywhere}'
            '[hidden]{display:none!important}</style><h1>Длительность и операция: офлайн-сравнение</h1>'
            '<p>Разметка ассистента после просмотра ответов. Три известных случая, не независимая оценка. '
            'Оценщик использует явные метки; семантическое извлечение не реализовано. Все исходные отказы сохранены. '
            'Совпадение поля длительности не подтверждает событие, образец, метод или ответ целиком.</p><p>Algorithm: '
            + VERSION + '; snapshot: ' + files.sha(files.encode(bindings)) + '</p>'
            '<label>Поиск <input id="q" type="search"></label>' + detail("Сводка", summary))
    for row in rows:
        case = row["case"]
        body += '<article data-case data-search><h2>' + html.escape(case["id"]) + '</h2><p>' + html.escape(case["question"]) + '</p>'
        body += '<blockquote>' + html.escape(case["exact_text"]) + '</blockquote><a href="' + html.escape(
            Path(case["source"]["original_pdf_path"]).as_uri() + '#page=' + str(case["page"]), quote=True) + '">Original PDF</a>'
        for label, field in (("Оценка сырых полей; ответ остаётся отклонённым", "evaluation"),
                             ("Предварительная разметка операций", "annotation"), ("Точный исходный каталог", "source"),
                             ("Исходный native reply без исправлений", "raw_native_reply"),
                             ("Исходный отказ", "original_result"), ("Полная зарегистрированная страница", "full_registered_page"),
                             ("Вопрос, точные offsets, hashes, исходная разметка", "case")):
            body += detail(label, row[field])
        body += '</article>'
    body += '<h2>TAC: все работы этого этапа</h2><table><thead><tr>' + ''.join('<th>' + name + '</th>' for name in (
        "Title", "Authors", "Journal", "Year", "Abstract", "Conclusions", "Terms", "Original file")) + '</tr></thead><tbody>'
    for article in articles.values():
        body += '<tr data-tac data-search>'
        for field in ("title", "authors", "journal", "year", "abstract", "conclusions", "terms"):
            body += '<td>' + ("Отсутствует / не собрано на этой стадии" if article[field] is None else detail("Развернуть", article[field]))
            body += '</td>'
        body += '<td><a href="' + html.escape(Path(article["original_pdf_path"]).as_uri(), quote=True) + '">Original PDF</a></td></tr>'
    body += ('</tbody></table><script>document.getElementById("q").addEventListener("input",e=>{for(const r of '
             'document.querySelectorAll("[data-search]"))r.hidden=!r.textContent.toLocaleLowerCase().includes('
             'e.target.value.toLocaleLowerCase())})</script></html>\n')

    class CheckHTML(HTMLParser):
        def __init__(self) -> None:
            super().__init__()
            self.links: list[str] = []
            self.cases = self.tac = 0

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            values = dict(attrs)
            if tag == "a" and values.get("href"):
                self.links.append(str(values["href"]))
            self.cases += tag == "article" and "data-case" in values
            self.tac += tag == "tr" and "data-tac" in values

    check = CheckHTML()
    check.feed(body)
    if check.cases != len(rows) or check.tac != len(articles):
        raise ValueError("HTML scope differs")
    for href in check.links:
        url = urlparse(href)
        if url.scheme != "file" or not Path(url2pathname(url.path)).is_file():
            raise ValueError("HTML PDF link is missing")
    report["html_qa"] = {"method": "static_not_browser", "case_cards": check.cases,
                         "tac_rows": check.tac, "existing_pdf_links": len(check.links)}
    files.verify(bindings)
    args.output.mkdir(parents=True, exist_ok=False)
    for name, digest in bindings.items():
        source_path = Path(name)
        if source_path.is_relative_to(ROOT) and source_path.suffix in {".py", ".md", ".json", ".bin"}:
            target = args.output / "source_snapshot" / source_path.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            raw_source = source_path.read_bytes()
            if files.sha(raw_source) != digest:
                raise ValueError("Input changed during snapshot")
            files.save(target, raw_source)
    files.write(args.output / "report.json", report)
    files.save(args.output / "review.html", body.encode())
    files.manifest(args.output)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
