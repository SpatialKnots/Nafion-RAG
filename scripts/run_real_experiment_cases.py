"""Evaluate unchanged dependency prototype on twelve preliminary real excerpts."""

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

from scripts import gigachat_answer_smoke as smoke  # noqa: E402
from scripts.experiment_sentence_links import VERSION as PROTOTYPE_VERSION  # noqa: E402
from scripts.experiment_sentence_links import dependencies  # noqa: E402
from scripts.real_relation_evaluation import VERSION, compare_relations, summarize  # noqa: E402
from scripts.requested_context_links import SourceEvidence, SourcePage  # noqa: E402


def no_network(event: str, args: tuple[object, ...]) -> None:
    if event in {"socket.connect", "socket.getaddrinfo", "socket.sendto"}:
        raise AssertionError("Network forbidden in real-excerpt evaluation")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sys.addaudithook(no_network)
    import fitz

    parent = ROOT / "output/experiment_sentence_links_20261029/review_v02"
    case_file = ROOT / "docs/records/real_experiment_cases_v0.1.json"
    build_file = ROOT / "output/real_experiment_cases_20261029/build_manifest_v01.json"
    smoke.verify_manifest(parent)
    previous = json.loads((parent / "report.json").read_bytes())
    smoke.verify(previous["bindings"])
    build = json.loads(build_file.read_bytes())
    smoke.verify(build["bindings"])
    dataset = json.loads(case_file.read_bytes())
    assert dataset["version"] == "real_experiment_cases_v0.1" and len(dataset["cases"]) == 12
    bindings = {**previous["bindings"], **build["bindings"], **smoke.bindings([
        case_file, build_file, Path(__file__), ROOT / "scripts/real_relation_evaluation.py",
        ROOT / "tests/unit/test_real_relation_evaluation.py", ROOT / "docs/records/real_experiment_cases_protocol_v0.1.md"])}
    # Capture bindings before running the unchanged prototype on the annotated set.
    pages, articles = {}, {}
    for row in previous["cases"]:
        for p in row["sources"]["pages"].values():
            pages[(p["article_id"], p["page_number"], p["text_layer_id"])] = p
        for a in json.loads((Path(row["prepared_path"]) / "articles.json").read_bytes()):
            articles[a["article_id"]] = a
    selected_pages, selected_articles, rows = {}, {}, []
    for case in dataset["cases"]:
        source = case["source"]
        key = (source["article_id"], source["page_number"], source["text_layer_id"])
        p = pages[key]
        assert source["original_pdf_sha256"] == p["original_pdf_sha256"]
        assert smoke.sha(Path(p["original_pdf_path"]).read_bytes()) == p["original_pdf_sha256"]
        assert p["text_layer"] == "original"
        if key not in selected_pages:
            with fitz.open(p["original_pdf_path"]) as document:
                assert document[p["page_number"] - 1].get_text("text") == p["page_text"]
            selected_pages[key] = p
        assert smoke.sha(p["page_text"].encode()) == source["page_text_sha256"]
        quote = case["exact_text"]
        assert p["page_text"][case["page_start_offset"]:case["page_end_offset"]] == quote
        assert smoke.sha(quote.encode()) == case["quote_sha256"]
        a = articles[case["article_id"]]
        selected_articles[a["article_id"]] = a
        page = SourcePage(p["article_id"], p["page_number"], p["text_layer"], p["text_layer_id"],
                          p["original_pdf_path"], p["original_pdf_sha256"], p["page_text"])
        # Curated excerpt IDs are not DB chunk IDs or production retrieval results.
        evidence = SourceEvidence("R1", p["article_id"], "curated_excerpt/" + case["id"], quote,
                                  p["page_number"], p["page_number"], p["text_layer"],
                                  tuple(author["name"] for author in a["authors"] or []), a["year"])
        graph = dependencies(evidence, [page])
        result = compare_relations(quote, case["preliminary_annotation"], graph)
        rows.append({"case": case, "graph": graph, "comparison": result,
                     "input_mode": "curated_exact_excerpt_not_runtime_retrieval", "scientific_answer_generated": False})
    summary = summarize([r["comparison"] for r in rows])
    assert len(rows) == len({r["case"]["id"] for r in rows}) == 12
    report = {"version": VERSION, "prototype_version": PROTOTYPE_VERSION, "bindings": bindings,
              "runtime_versions": {"python": sys.version, "pymupdf": fitz.VersionBind},
              "dataset": {k: v for k, v in dataset.items() if k != "cases"}, "summary": summary,
              "answer_annotation_states": dict(Counter(r["case"]["answer_state"] for r in rows)),
              "cases_with_open_annotation_notes": sum(bool(r["case"]["unresolved"]) for r in rows),
              "source_documents": len(selected_articles), "source_pages_verified_against_pdf": len(selected_pages),
              "new_api_calls": 0, "database_use": "none_no_database_imports", "runtime_installed": False,
              "prototype_modified": False, "cases": rows, "full_source_pages": list(selected_pages.values())}

    def detail(label: str, value: object) -> str:
        return '<details><summary>' + html.escape(label) + '</summary><pre>' + html.escape(
            value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)) + '</pre></details>'

    body = ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>ARIADNE — 12 real excerpts</title>'
            '<style>body{font:16px system-ui;margin:24px}table{border-collapse:collapse;width:100%}td,th{border:1px solid #abc;'
            'padding:8px;vertical-align:top}pre,blockquote{white-space:pre-wrap;overflow-wrap:anywhere}'
            '[hidden]{display:none!important}</style><h1>12 реальных фрагментов: предварительная разметка</h1>'
            '<p>Выборка из уже известных страниц, не independent gold и не accuracy. Прототип не изменён. '
            'Вопросы и ожидаемые ответы размечены ассистентом; научные ответы моделью не генерировались и не оценивались. '
            'Сравниваются только указанные связи. Непомеченные пары не считаются отрицательными.</p><p>Algorithm: '
            + PROTOTYPE_VERSION + '; evaluator: ' + VERSION + '; snapshot: ' + smoke.sha(smoke.encode(bindings))
            + '</p><label>Поиск <input id="q" type="search"></label>' + detail("Сводка", summary))
    for row in rows:
        case = row["case"]
        href = Path(case["source"]["original_pdf_path"]).as_uri() + '#page=' + str(case["page"])
        body += '<article data-case data-search><h2>' + html.escape(case["id"]) + '</h2><p>' + html.escape(case["question"]) + '</p>'
        body += '<blockquote>' + html.escape(case["exact_text"]) + '</blockquote>'
        body += '<a href="' + html.escape(href, quote=True) + '">Original PDF</a>'
        body += detail("Предварительная интерпретация ассистента, не подтверждённый ответ", {
            "answer_state": case["answer_state"], "note": case["preliminary_note"], "open_notes": case["unresolved"]})
        body += detail("Точная привязка: страница, слой, offsets, hashes", {
            "source": case["source"], "page_start_offset": case["page_start_offset"],
            "page_end_offset": case["page_end_offset"], "quote_sha256": case["quote_sha256"]})
        body += detail("Предварительные зависимости и границы", case["preliminary_annotation"])
        body += detail("Сравнение с неизменённым прототипом", row["comparison"]) + detail("Полный граф", row["graph"]) + '</article>'
    body += '<h2>Полные зарегистрированные страницы</h2>'
    for p in selected_pages.values():
        body += detail(articles[p["article_id"]]["title"] + ' p.' + str(p["page_number"]), p)
    body += '<h2>TAC: все 5 работ выбранного набора</h2><table><thead><tr>' + ''.join('<th>' + x + '</th>' for x in (
        "Title", "Authors", "Journal", "Year", "Abstract", "Conclusions", "Terms", "Original file")) + '</tr></thead><tbody>'
    for a in selected_articles.values():
        body += '<tr data-tac data-search>'
        for field in ("title", "authors", "journal", "year", "abstract", "conclusions", "terms"):
            body += '<td>' + ("Отсутствует / не собрано на этой стадии" if a[field] is None else detail("Развернуть", a[field])) + '</td>'
        body += '<td><a href="' + html.escape(Path(a["original_pdf_path"]).as_uri(), quote=True) + '">Original PDF</a></td></tr>'
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
    for href in check.links:
        url = urlparse(href)
        assert url.scheme == "file" and Path(url2pathname(url.path)).is_file()
    assert check.cases == 12 and check.tac == len(selected_articles) == 5
    report["html_qa"] = {"method": "static_not_browser", "case_cards": check.cases, "tac_rows": check.tac,
                         "existing_pdf_links": len(check.links)}
    smoke.verify(bindings)
    args.output.mkdir(parents=True, exist_ok=False)
    for name, digest in bindings.items():
        source = Path(name)
        if source.is_relative_to(ROOT) and source.suffix in {".py", ".md", ".json"} and (
                source.relative_to(ROOT).parts[0] in {"app", "scripts", "tests", "docs"} or name in build["bindings"]):
            target = args.output / "source_snapshot" / source.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            raw = source.read_bytes()
            assert smoke.sha(raw) == digest
            smoke.save(target, raw)
    smoke.write(args.output / "report.json", report)
    smoke.save(args.output / "review.html", body.encode("utf-8"))
    smoke.manifest(args.output)
    print(json.dumps({"summary": summary, "source_documents": len(selected_articles),
                      "source_pages_verified_against_pdf": len(selected_pages), "new_api_calls": 0}, ensure_ascii=False))


if __name__ == "__main__":
    main()
