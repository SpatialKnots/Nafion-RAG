"""Offline graph sidecar and constructed error checks on frozen source evidence."""

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
from scripts.experiment_sentence_links import VERSION, attach_dependencies, dependencies  # noqa: E402
from scripts.requested_context_links import SourceEvidence, SourcePage  # noqa: E402


def no_network(event: str, args: tuple[object, ...]) -> None:
    if event in {"socket.connect", "socket.getaddrinfo", "socket.sendto"}:
        raise AssertionError("Network forbidden in sentence-dependency experiment")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sys.addaudithook(no_network)
    parent = ROOT / "output/requested_context_links_20261029/review_v04"
    smoke.verify_manifest(parent)
    previous = json.loads((parent / "report.json").read_bytes())
    smoke.verify(previous["bindings"])
    cases_path = ROOT / "docs/records/experiment_sentence_links_cases_v0.1.json"
    fixtures = json.loads(cases_path.read_bytes())
    assert fixtures["version"] == "experiment_sentence_links_cases_v0.1"
    bindings = {**previous["bindings"], **smoke.bindings([
        Path(__file__), ROOT / "scripts/experiment_sentence_links.py", ROOT / "tests/unit/test_experiment_sentence_links.py",
        cases_path, ROOT / "docs/records/experiment_sentence_links_protocol_v0.1.md", parent / "report.json", parent / "manifest.json"])}
    fixture_rows = []
    for case in fixtures["cases"]:
        e = SourceEvidence("E1", "constructed", "chunk", case["text"], 1, 1, "original")
        p = SourcePage("constructed", 1, "original", "synthetic-layer", "synthetic.pdf", "a" * 64, case["text"])
        graph = dependencies(e, [p])
        observed = sum(a["state"] == "dependency_proposal_unverified" for a in graph["attempts"])
        fixture_rows.append({**case, "observed_links": observed, "matches_expectation": observed == case["expected_links"], "graph": graph})
    rows, articles = [], {}
    for row in previous["cases"]:
        items = json.loads((Path(row["prepared_path"]) / "articles.json").read_bytes())
        for a in items:
            if a["article_id"] in articles:
                assert articles[a["article_id"]] == a
            articles[a["article_id"]] = a
        metadata = {a["article_id"]: a for a in items}
        pages = [SourcePage(p["article_id"], p["page_number"], p["text_layer"], p["text_layer_id"],
                            p["original_pdf_path"], p["original_pdf_sha256"], p["page_text"])
                 for p in row["sources"]["pages"].values()]
        evidence = [SourceEvidence(e["citation_id"], e["article_id"], e["chunk_id"], e["text"], e["page_start"], e["page_end"],
                                   row["sources"]["chunk_layers"][e["chunk_id"]],
                                   tuple(a["name"] for a in metadata[e["article_id"]]["authors"] or []),
                                   metadata[e["article_id"]]["year"]) for e in row["trace"]["evidence"]]
        baseline_bytes = smoke.encode(row["context_links"])
        sidecar = attach_dependencies(row["context_links"], evidence, pages)
        assert smoke.encode(row["context_links"]) == baseline_bytes
        by_id = {e.citation_id: e for e in evidence}
        for graph in sidecar["graphs"]:
            e = by_id[graph["citation_id"]]
            for node in graph["nodes"]:
                span = node["span"]
                assert e.text[span["start"]:span["end"]] == span["text"]
                for anchor in node["page_anchors"]:
                    assert any(p.article_id == anchor["article_id"] and p.page == anchor["page"]
                               and p.text_layer_id == anchor["text_layer_id"]
                               and p.text[anchor["start"]:anchor["end"]] == anchor["text"] for p in pages)
            for attempt in graph["attempts"]:
                bridge = attempt["bridge_span"]
                assert e.text[bridge["start"]:bridge["end"]] == bridge["text"]
        rows.append({**row, "sentence_dependencies": sidecar})
    attempts = [a for r in rows for g in r["sentence_dependencies"]["graphs"] for a in g["attempts"]]
    proposals = [a for a in attempts if a["state"] == "dependency_proposal_unverified"]
    unique_source_dependencies = set()
    for row in rows:
        for graph in row["sentence_dependencies"]["graphs"]:
            for attempt in graph["attempts"]:
                if attempt["state"] == "dependency_proposal_unverified":
                    anchors = [graph["nodes"][attempt[ref]]["page_anchors"][0] for ref in ("parent", "child")]
                    unique_source_dependencies.add(tuple((a["article_id"], a["page"], a["text_layer_id"], a["start"], a["end"])
                                                         for a in anchors))
    total_nodes = sum(len(g["nodes"]) for r in rows for g in r["sentence_dependencies"]["graphs"])
    unlinked = sum(len(g["unlinked_unit_ids"]) for r in rows for g in r["sentence_dependencies"]["graphs"])
    evaluation = {"origin": fixtures["annotation_origin"], "cases": len(fixture_rows),
                  "expectation_mismatches": sum(not f["matches_expectation"] for f in fixture_rows),
                  "false_proposals_on_declared_negative_cases": sum(f["observed_links"] for f in fixture_rows if f["expected_links"] == 0),
                  "missed_declared_links": sum(max(0, f["expected_links"] - f["observed_links"]) for f in fixture_rows),
                  "cases_without_proposal": sum(f["observed_links"] == 0 for f in fixture_rows),
                  "blocked_template_attempts": sum(a["state"] != "dependency_proposal_unverified" for f in fixture_rows
                                                   for a in f["graph"]["attempts"]),
                  "cases_without_template_attempt": sum(not f["graph"]["attempts"] for f in fixture_rows),
                  "independent_accuracy": None}
    assert evaluation["expectation_mismatches"] == 0
    report = {"version": VERSION, "bindings": bindings, "historical_cases": len(rows), "source_documents": len(articles),
              "dependency_attempts": len(attempts), "proposed_dependencies": len(proposals),
              "unique_source_dependencies_by_exact_page_anchors": len(unique_source_dependencies),
              "proposal_separator_counts": dict(Counter(a["separator_kind"] for a in proposals)),
              "proposals_with_unresolved_sample_identity": sum(a["sample_identity"] == "not_established" for a in proposals),
              "blocked_reasons": dict(Counter(d for a in attempts for d in a["diagnostics"])),
              "source_units": total_nodes, "units_without_proposal": unlinked,
              "units_without_proposal_fraction": unlinked / total_nodes if total_nodes else None,
              "unit_fraction_caveat": "Includes all punctuation units in chunks; not scientific recall or a semantic uncertainty rate.",
              "scope_caveat": "Repeated selected chunks across exposed cases; punctuation units, not independent scientific examples.",
              "evaluation": evaluation, "constructed_cases": fixture_rows, "cases": rows,
              "new_api_calls": 0, "new_oauth_calls": 0, "database_use": "none_no_database_imports",
              "runtime_installed": False, "baseline_modified": False, "scientific_coverage": "not_evaluated"}

    def detail(label: str, value: object) -> str:
        return '<details><summary>' + html.escape(label) + '</summary><pre>' + html.escape(
            value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)) + '</pre></details>'

    body = ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>ARIADNE — sentence dependencies</title>'
            '<style>body{font:16px system-ui;margin:24px}table{border-collapse:collapse;width:100%}td,th{border:1px solid #abc;'
            'padding:8px;vertical-align:top}pre{white-space:pre-wrap;overflow-wrap:anywhere}[hidden]{display:none!important}'
            '</style><h1>Связи фраз одного эксперимента: offline</h1><p>Граф хранится отдельно. '
            'Исходные неопределённости и ответы не изменены. Соседство без маркера не создаёт связь; '
            'предложенная зависимость не доказывает научный вывод. Новых API calls — 0.</p><p>Algorithm: '
            + VERSION + '; snapshot: ' + smoke.sha(smoke.encode(bindings))
            + '</p><label>Поиск <input id="q" type="search"></label>'
            + detail("Результаты и ограничения", {k: v for k, v in report.items() if k not in {"bindings", "cases", "constructed_cases"}}))
    for row in rows:
        body += '<article data-case data-search><h2>' + html.escape(row["id"]) + '</h2><p>' + html.escape(row["question"]) + '</p>'
        for graph in row["sentence_dependencies"]["graphs"]:
            for attempt in graph["attempts"]:
                if attempt["state"] != "dependency_proposal_unverified":
                    continue
                nodes = graph["nodes"]
                body += detail("Предложенная зависимость: " + graph["citation_id"], {
                    "dependency": attempt, "parent": nodes[attempt["parent"]], "child": nodes[attempt["child"]]})
                for ref in (attempt["parent"], attempt["child"]):
                    for anchor in nodes[ref]["page_anchors"]:
                        body += '<a href="' + html.escape(Path(anchor["original_pdf_path"]).as_uri(), quote=True)
                        body += '#page=' + str(anchor["page"]) + '">Original PDF p.' + str(anchor["page"]) + '</a> '
        body += detail("Полный граф и blocked/unresolved", row["sentence_dependencies"])
        body += detail("Прежние требования / контекст без изменения статусов", row["context_links"])
        body += detail("Прежний публичный ответ", row["api"]) + detail("Прежний native response", row["native"])
        body += detail("Полный запрос", (Path(row["prepared_path"]) / "request.json").read_text(encoding="utf-8"))
        body += detail("Все выбранные evidence / retrieval", row["trace"]) + detail("Все source pages / layers / hashes", row["sources"])
        body += '</article>'
    body += '<h2>Constructed software cases: не независимый научный эталон</h2>'
    for f in fixture_rows:
        body += '<section data-search><h3>' + html.escape(f["id"]) + '</h3>' + detail("Ожидание / результат / граф", f) + '</section>'
    body += '<h2>TAC: все документы</h2><table><thead><tr>' + ''.join('<th>' + x + '</th>' for x in (
        "Title", "Authors", "Journal", "Year", "Abstract", "Conclusions", "Terms", "Original file")) + '</tr></thead><tbody>'
    for a in articles.values():
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
    assert check.cases == len(rows) == 8 and check.tac == len(articles)
    report["html_qa"] = {"method": "static_not_browser", "cases": check.cases, "tac_rows": check.tac,
                         "existing_pdf_links": len(check.links)}
    smoke.verify(bindings)
    args.output.mkdir(parents=True, exist_ok=False)
    for name, digest in bindings.items():
        source = Path(name)
        if source.is_relative_to(ROOT) and source.suffix in {".py", ".md", ".json"} and source.relative_to(ROOT).parts[0] in {
                "scripts", "tests", "app", "docs"}:
            target = args.output / "source_snapshot" / source.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            raw = source.read_bytes()
            assert smoke.sha(raw) == digest
            smoke.save(target, raw)
    smoke.write(args.output / "report.json", report)
    smoke.save(args.output / "review.html", body.encode("utf-8"))
    smoke.manifest(args.output)
    print(json.dumps({k: report[k] for k in ("historical_cases", "dependency_attempts", "proposed_dependencies",
                                           "proposal_separator_counts", "units_without_proposal_fraction", "evaluation", "html_qa")},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
