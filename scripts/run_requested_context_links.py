"""Bind finite event-link proposals to frozen evidence and original source pages."""

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
from scripts.requested_context_links import VERSION, SourceEvidence, SourcePage, audit_links  # noqa: E402


def no_network(event: str, args: tuple[object, ...]) -> None:
    if event in {"socket.connect", "socket.getaddrinfo", "socket.sendto"}:
        raise AssertionError("No network permitted in frozen context-link experiment")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sys.addaudithook(no_network)
    parent = ROOT / "output/requested_information_audit_20261029/review_v02"
    smoke.verify_manifest(parent)
    previous = json.loads((parent / "report.json").read_bytes())
    smoke.verify(previous["bindings"])
    bindings = dict(previous["bindings"])
    bindings.update(smoke.bindings([Path(__file__), ROOT / "scripts/requested_context_links.py",
                                  ROOT / "tests/unit/test_requested_context_links.py", parent / "report.json",
                                  parent / "manifest.json", ROOT / "docs/records/requested_context_links_protocol_v0.1.md"]))
    rows, articles = [], {}
    for row in previous["cases"]:
        prepared = Path(row["prepared_path"])
        items = json.loads((prepared / "articles.json").read_bytes())
        for article in items:
            if article["article_id"] in articles:
                assert articles[article["article_id"]] == article
            articles[article["article_id"]] = article
        metadata = {a["article_id"]: a for a in items}
        sources = row["sources"]
        evidence = []
        for e in row["trace"]["evidence"]:
            assert e["text"] == sources["chunks"][e["chunk_id"]]["text"]
            meta = metadata[e["article_id"]]
            evidence.append(SourceEvidence(e["citation_id"], e["article_id"], e["chunk_id"], e["text"],
                                           e["page_start"], e["page_end"], sources["chunk_layers"][e["chunk_id"]],
                                           tuple(a["name"] for a in meta["authors"] or []), meta["year"]))
        pages = [SourcePage(p["article_id"], p["page_number"], p["text_layer"], p["text_layer_id"],
                            p["original_pdf_path"], p["original_pdf_sha256"], p["page_text"])
                 for p in sources["pages"].values()]
        claims = [(c["text"], c["citation_ids"]) for c in row["api"]["body"].get("claims", [])]
        audit = audit_links(row["question"], claims, evidence, pages)
        if row["http_status"] != 200:
            assert not claims
        # Check every returned exact anchor and its registered evidence identity.
        by_id = {e.citation_id: e for e in evidence}
        for c in audit["source_candidates"]:
            e = by_id[c["citation_id"]]
            assert e.text[c["value"]["start"]:c["value"]["end"]] == c["value"]["text"]
            assert e.text[c["statement"]["start"]:c["statement"]["end"]] == c["statement"]["text"]
            for anchor in c["page_anchors"]:
                registered = [p for p in pages if p.article_id == anchor["article_id"] and p.page == anchor["page"]
                              and p.text_layer_id == anchor["text_layer_id"]]
                assert any(p.text[anchor["start"]:anchor["end"]] == anchor["text"] for p in registered)
                assert anchor["article_id"] == e.article_id
        rows.append({**row, "context_links": audit})
    assert len(rows) == 8
    diagnostics = Counter(d for r in rows for c in r["context_links"]["source_candidates"] for d in c["diagnostics"])
    states = Counter(c["state"] for r in rows for c in r["context_links"]["source_candidates"])
    anchors = sum(len(c["page_anchors"]) for r in rows for c in r["context_links"]["source_candidates"])
    report = {"version": VERSION, "parent_snapshot": str(parent), "bindings": bindings,
              "cases": rows, "historical_cases": len(rows), "source_documents": len(articles),
              "source_candidate_states": dict(states), "source_diagnostics": dict(diagnostics), "exact_page_anchors": anchors,
              "new_api_calls": 0, "new_oauth_calls": 0, "database_use": "none_no_database_imports",
              "runtime_installed": False, "scientific_acceptance": "not_evaluated", "independent_accuracy": None}

    def detail(label: str, value: object) -> str:
        return '<details><summary>' + html.escape(label) + '</summary><pre>' + html.escape(
            value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)) + '</pre></details>'

    body = ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>ARIADNE — context links</title>'
            '<style>body{font:16px system-ui;margin:24px}table{border-collapse:collapse;width:100%}'
            'td,th{border:1px solid #abc;padding:8px;vertical-align:top}pre{white-space:pre-wrap;overflow-wrap:anywhere}'
            '[hidden]{display:none!important}</style><h1>Величина → эксперимент → источник: offline-прототип</h1>'
            '<p>8 сохранённых случаев. Связи остаются неопределёнными или предложенными; научной приёмки нет. '
            'Один контекст не доказывает связь. Число, критерий, подготовка и измерение учитываются отдельно. '
            'Runtime не изменён. Новых API calls — 0.</p><p>Algorithm: ' + VERSION + '; snapshot: '
            + smoke.sha(smoke.encode(bindings)) + '</p><label>Поиск <input id="q" type="search"></label>'
            + detail("Сводка диагностик", {k: v for k, v in report.items() if k not in {"cases", "bindings"}}))
    for row in rows:
        body += '<article data-case data-search><h2>' + html.escape(row["id"]) + '</h2><p>' + html.escape(row["question"]) + '</p>'
        body += detail("Требования вопроса: предложенный разбор", row["context_links"]["requirement"])
        body += detail("Связи и диагностика; научная поддержка не установлена", row["context_links"])
        for candidate in row["context_links"]["source_candidates"]:
            for anchor in candidate["page_anchors"]:
                body += '<a href="' + html.escape(Path(anchor["original_pdf_path"]).as_uri(), quote=True)
                body += '#page=' + str(anchor["page"]) + '">Original PDF p.' + str(anchor["page"]) + '</a> '
        body += detail("Прежний публичный результат", row["api"]) + detail("Native response без исправления", row["native"])
        body += detail("Прежний форматный слой", {k: row[k] for k in ("http_status", "finish_reason", "layer", "parser_error")})
        body += detail("Полный запрос", (Path(row["prepared_path"]) / "request.json").read_text(encoding="utf-8"))
        body += detail("Все evidence / retrieval", row["trace"]) + detail("Все source pages / layers / hashes", row["sources"])
        body += '</article>'
    body += '<h2>TAC: все исходные документы</h2><table><thead><tr>' + ''.join('<th>' + x + '</th>' for x in (
        "Title", "Authors", "Journal", "Year", "Abstract", "Conclusions", "Terms", "Original file")) + '</tr></thead><tbody>'
    for article in articles.values():
        body += '<tr data-tac data-search>'
        for field in ("title", "authors", "journal", "year", "abstract", "conclusions", "terms"):
            value = article[field]
            body += '<td>' + ("Отсутствует / не собрано на этой стадии" if value is None else detail("Развернуть", value)) + '</td>'
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
    for href in check.links:
        url = urlparse(href)
        assert url.scheme == "file" and Path(url2pathname(url.path)).is_file()
    assert check.cases == 8 and check.tac == len(articles)
    report["html_qa"] = {"method": "static_not_browser", "case_cards": check.cases, "tac_rows": check.tac,
                         "existing_pdf_links": len(check.links)}
    smoke.verify(bindings)
    args.output.mkdir(parents=True, exist_ok=False)
    for name, digest in bindings.items():
        source = Path(name)
        if source.is_relative_to(ROOT) and source.suffix in {".py", ".md"}:
            target = args.output / "source_snapshot" / source.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            raw = source.read_bytes()
            assert smoke.sha(raw) == digest
            smoke.save(target, raw)
    smoke.write(args.output / "report.json", report)
    smoke.save(args.output / "review.html", body.encode("utf-8"))
    smoke.manifest(args.output)
    print(json.dumps({k: report[k] for k in ("historical_cases", "source_documents", "source_candidate_states",
                                           "source_diagnostics", "exact_page_anchors", "html_qa", "new_api_calls")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
