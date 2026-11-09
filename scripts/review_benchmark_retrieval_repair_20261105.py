"""Offline before/after retrieval experiment; gold enters only post-selection evaluation."""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import fitz

from scripts import gigachat_answer_smoke as files
from scripts.benchmark_retrieval_capture_20261105 import BASE, PROTOCOL, read
from scripts.benchmark_retrieval_replay_20261105 import replay
from scripts.explicit_reference_retrieval_20261105 import select
from scripts.retrieval_ablation_labels import label_retention
from scripts.review_retrieval_ablation import unpack

ROOT = files.ROOT
INTAKE = ROOT / "output/user_benchmark_20261103/review_v01"
OLD = ROOT / "output/retrieval_ablation_20261031/capture_v02"
ARMS = ("baseline", "wide", "explicit_reference")


def identity(rows: list[dict[str, Any]]) -> list[tuple[str, str, str]]:
    return [(r["article_id"], r["chunk_id"], files.sha(r.get("text", r.get("full_text", "")).encode())) for r in rows]


def normalized(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def presence(rows: list[dict[str, Any]], article_id: str, pages: list[int],
             quotes: list[dict[str, Any]]) -> dict[str, Any]:
    target = [r for r in rows if r["article_id"] == article_id]
    retained_pages = [p for p in pages if any(r["page_start"] <= p <= r["page_end"] for r in target)]
    anchors = []
    for number, quote in enumerate(quotes):
        if quote["span"] is None:
            continue
        raw = quote["span"]["text"]
        matches = []
        for row in target:
            text = row.get("text", row.get("full_text", "")) or ""
            if row["page_start"] <= quote["pdf_page"] <= row["page_end"] and normalized(raw) in normalized(text):
                matches.append({"chunk_id": row["chunk_id"], "raw_exact": raw in text,
                                "raw_start": text.find(raw) if raw in text else None})
        anchors.append({"quote_index": number, "page": quote["pdf_page"], "raw_source_span": quote["span"],
                        "matches": matches, "retained": bool(matches)})
    return {"article_present": bool(target), "target_chunks": [r["chunk_id"] for r in target],
            "reference_pages_present": retained_pages, "reference_pages_total": len(pages),
            "mapped_quotes_retained": sum(a["retained"] for a in anchors), "mapped_quotes_total": len(anchors),
            "anchors": anchors, "meaning_or_ownership_validated": False}


def short_source(row: dict[str, Any]) -> dict[str, Any]:
    return {key: row[key] for key in ("article_id", "chunk_id", "title", "page_start", "page_end", "text")}


def detail(label: str, value: Any) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)
    return "<details><summary>" + escape(label) + "</summary><pre>" + escape(text) + "</pre></details>"


def render(report: dict[str, Any]) -> str:
    html = """<!doctype html><html lang="ru"><meta charset="utf-8"><title>ARIADNE — поиск до/после</title>
<style>body{font:16px/1.5 system-ui;margin:30px;color:#183044}table{border-collapse:collapse;width:100%}
td,th{border:1px solid #b5c5d0;padding:9px;vertical-align:top}pre{white-space:pre-wrap;overflow-wrap:anywhere}
details{margin:8px 0}summary{cursor:pointer}.scroll{overflow:auto}input{padding:8px}[hidden]{display:none!important}</style>
<body><h1>Офлайн-поиск: до / после</h1><p>Пять раскрытых вопросов для разработки. Ответов модели нет.
v0.1: расширение окна существующего ранжирования. v0.2: явная ссылка автор/год и поиск внутри работы.
Наличие страницы или цитаты не доказывает научную достаточность. Production runtime не изменён.</p>"""
    html += detail("Итог, границы и проверки", report["summary"])
    html += "<table><tr><th>Вопрос</th><th>Было</th><th>Широкое окно</th><th>Автор/год</th></tr>"
    for case in report["cases"]:
        html += "<tr><td>" + escape(case["id"]) + "</td>"
        for arm in ARMS:
            p = case["arms"][arm]["source_presence"]
            html += ("<td>Страницы: " + str(p["reference_pages_present"]) + "; цитаты: "
                     + str(p["mapped_quotes_retained"]) + "/" + str(p["mapped_quotes_total"]) + "</td>")
        html += "</tr>"
    html += "</table>"
    for case in report["cases"]:
        html += "<section><h2>" + escape(case["id"]) + "</h2><p>" + escape(case["question"]) + "</p>"
        html += detail("Где теряется эталонный контекст — проверено после отбора", case["loss_stages"])
        html += detail("Диагностика автор/год", case["explicit_diagnostic"])
        for arm in ARMS:
            value = case["arms"][arm]
            html += "<h3>" + arm + "</h3>" + detail("Покрытие и действующий gate", {
                "presence": value["source_presence"], "adequacy": value["adequacy"],
                "boundary": value["boundary"], "condition_surfaces": value["condition_surfaces"],
            })
            for evidence in value["evidence"]:
                article = report["articles"][evidence["article_id"]]
                uri = Path(article["original_pdf_path"]).as_uri() + "#page=" + str(evidence["page_start"])
                html += "<p><a href='" + escape(uri, quote=True) + "'>" + escape(
                    str(evidence["title"]) + ": PDF " + str(evidence["page_start"]) + "–" + str(evidence["page_end"])) + "</a></p>"
                html += detail("Полный исходный фрагмент " + evidence["chunk_id"], evidence)
        html += "</section>"
    html += detail("76 старых случаев: изменения, потери и поведение gate", report["regressions"])
    html += "<h2>TAC: все 33 работы снимка</h2><input id='q' type='search' aria-label='Поиск по TAC'><div class='scroll'>"
    fields = ("title", "authors", "journal", "year", "abstract", "conclusions", "terms")
    html += "<table id='tac'><thead><tr>" + "".join("<th>" + f.title() + "</th>" for f in fields)
    html += "<th>Original file</th></tr></thead><tbody>"
    for article in report["articles"].values():
        html += "<tr>"
        for field in fields:
            value = article.get(field)
            html += "<td>" + detail(field, value if value is not None else "Не собрано / не реализовано в этом этапе") + "</td>"
        html += "<td><a href='" + escape(Path(article["original_pdf_path"]).as_uri(), quote=True) + "'>PDF</a></td></tr>"
    html += """</tbody></table></div><script>document.querySelector('#q').addEventListener('input',e=>{
for(const r of document.querySelectorAll('#tac tbody tr'))r.hidden=!r.textContent.toLocaleLowerCase().includes(
e.target.value.toLocaleLowerCase());});</script></body></html>"""
    return html


def condition_surfaces(rows: list[dict[str, Any]]) -> list[str]:
    # Literal diagnostics only; no ownership or unit conversion.
    pattern = r"\b\d+(?:[.,]\d+)?\s*(?:°\s*C|K|wt\s*%|vol\s*%|%|mA\s*/\s*cm|mAh\s*/\s*cm)"
    return sorted({m.group() for r in rows for m in re.finditer(pattern, r["text"])})


class ReviewStructure(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []
        self.in_tac = False
        self.tac_rows = 0
        self.tac_headers = 0
        self.sections = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "table" and attributes.get("id") == "tac":
            self.in_tac = True
        if self.in_tac:
            self.tac_rows += tag == "tr"
            self.tac_headers += tag == "th"
        self.sections += tag == "section"
        if tag == "a" and attributes.get("href"):
            self.links.append(str(attributes["href"]))

    def handle_endtag(self, tag: str) -> None:
        if tag == "table":
            self.in_tac = False


def check_html(html: str, *, article_count: int, case_count: int) -> dict[str, Any]:
    structure = ReviewStructure()
    structure.feed(html)
    if (structure.tac_rows, structure.tac_headers, structure.sections) != (article_count + 1, 8, case_count):
        raise ValueError("HTML case/TAC inventory differs")
    for href in structure.links:
        uri = urlparse(href)
        if uri.scheme != "file":
            raise ValueError("Expected original local PDF link")
        path = unquote(uri.path)
        if re.match(r"^/[A-Za-z]:", path):
            path = path[1:]
        if not Path(path).is_file():
            raise ValueError("Missing linked PDF: " + path)
    return {"sections": structure.sections, "tac_rows": structure.tac_rows - 1,
            "tac_columns": structure.tac_headers, "existing_pdf_links": len(structure.links), "browser_execution": "untested"}


def evaluate(captured: Path, output: Path, policy: files.NetworkPolicy) -> dict[str, Any]:
    settings = files.configure()
    output.mkdir(parents=True, exist_ok=False)
    paths = [Path(__file__), PROTOCOL, ROOT / "docs/records/benchmark_retrieval_repair_protocol_2026-11-05_v0.2.md",
             ROOT / "scripts/benchmark_retrieval_replay_20261105.py", ROOT / "scripts/explicit_reference_retrieval_20261105.py",
             ROOT / "tests/unit/test_explicit_reference_retrieval_20261105.py",
             ROOT / "tests/unit/test_benchmark_retrieval_replay_20261105.py"]
    bindings = files.bindings(paths)
    for source in paths:
        destination = output / "source_snapshot" / source.relative_to(ROOT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        files.save(destination, source.read_bytes())
    corpus, articles, candidates = {}, {}, {}
    for number in range(1, 6):
        case_id = f"Q{number:02}"
        folder = captured / case_id
        files.verify_manifest(folder)
        capture = read(folder / "capture.json")
        files.verify(capture["bindings"])
        bindings.update(capture["bindings"])
        bindings.update(files.bindings([folder / "manifest.json", folder / "boundaries.json", folder / "corpus.json"]))
        source = read(folder / "boundaries.json")
        current_corpus, current_articles = read(folder / "corpus.json"), read(folder / "articles.json")
        if corpus and (corpus != current_corpus or articles != current_articles):
            raise ValueError("Capture collection inventory differs between questions")
        corpus, articles = current_corpus, current_articles
        question, diagnostic = capture["case"]["question"], {}

        def candidate(baseline: Any, question: str = question, corpus: Any = corpus,
                      articles: Any = articles, source: Any = source) -> Any:
            nonlocal diagnostic
            result, diagnostic = select(question, baseline, corpus, articles, top_k=source["api"]["top_k"])
            return result

        arms = {"baseline": replay(source, settings), "wide": replay(source, settings, wide=True),
                "explicit_reference": replay(source, settings, replacement=candidate)}
        for arm, value in arms.items():
            files.write(output / f"{case_id}_{arm}.json", value)
        candidates[case_id] = {"case": capture["case"], "arms": arms, "diagnostic": diagnostic,
                               "historical_trace_identical": capture["historical_trace_identical"]}
        print(json.dumps({"selected_question_without_gold": case_id}), flush=True)

    # Selection complete. Reference answers/pages first enter here, only for assessment.
    files.verify_manifest(INTAKE)
    reference = read(INTAKE / "report.json")
    bindings.update(files.bindings([INTAKE / "manifest.json", INTAKE / "report.json"]))
    cases, fresh_pages = [], []
    for gold in reference["cases"]:
        case_id = gold["id"]
        value = candidates[case_id]
        if value["case"]["question"] != gold["question"]:
            raise ValueError("Evaluation question identity differs")
        target_path = Path(gold["source_pdf_path_verbatim"]).resolve()
        target = [a for a in articles.values() if Path(a["original_pdf_path"]).resolve() == target_path]
        if len(target) != 1:
            raise ValueError("Reference source is missing or ambiguous in captured inventory")
        article_id = target[0]["article_id"]
        pages = [p["pdf_page"] for p in reference["source_pages"] if p["case_id"] == case_id]
        with fitz.open(target_path) as document:
            for item in [p for p in reference["source_pages"] if p["case_id"] == case_id]:
                raw = document[item["pdf_page"] - 1].get_text()
                if files.sha(raw.encode()) != item["sha256"]:
                    raise ValueError("Fresh reference page hash differs")
                fresh_pages.append({"case_id": case_id, "pdf_page": item["pdf_page"], "sha256": item["sha256"]})
                for quote in gold["quotes"]:
                    if quote["span"] is not None and quote["pdf_page"] == item["pdf_page"]:
                        span = quote["span"]
                        if raw[span["start"]:span["end"]] != span["text"]:
                            raise ValueError("Reference raw offset differs")
        arms = {}
        for arm, result in value["arms"].items():
            evidence = result["trace"]["evidence"]
            old = value["arms"]["baseline"]["trace"]["evidence"]
            arms[arm] = {"source_presence": presence(evidence, article_id, pages, gold["quotes"]),
                         "adequacy": result["trace"]["metadata"]["evidence_adequacy"], "boundary": result["boundary"],
                         "evidence": [short_source(e) for e in evidence], "condition_surfaces": condition_surfaces(evidence),
                         "evidence_changed": identity(evidence) != identity(old),
                         "displaced_baseline_evidence": [short_source(e) for e in old
                             if e["chunk_id"] not in {r["chunk_id"] for r in evidence}]}
        stages = [{"name": s["name"], "count": len(s["results"]),
                   "presence": presence(s["results"], article_id, pages, gold["quotes"])}
                  for s in value["arms"]["baseline"]["stages"]]
        stages.insert(0, {"name": "collection_inventory_not_a_search_result", "count": len(corpus),
                          "presence": presence(list(corpus.values()), article_id, pages, gold["quotes"])})
        cases.append({"id": case_id, "question": gold["question"], "arms": arms, "loss_stages": stages,
                      "explicit_diagnostic": value["diagnostic"], "historical_trace_identical": value["historical_trace_identical"]})

    # Historical development regressions: use exact frozen channels, no search or embeddings.
    files.verify_manifest(OLD)
    old_corpus, old_articles, dataset = read(OLD / "corpus.json"), read(OLD / "articles.json"), read(OLD / "cases.json")
    if set(corpus) != set(old_corpus) or any(corpus[k]["full_text"] != old_corpus[k]["full_text"] for k in corpus):
        raise ValueError("Older regression corpus differs")
    bindings.update(files.bindings([OLD / "manifest.json", OLD / "corpus.json", OLD / "articles.json", OLD / "cases.json"]))
    regressions = []
    for number, case in enumerate(dataset["cases"]):
        path = OLD / f"cases/{number:03}_baseline.json"
        frozen = read(path)
        bindings.update(files.bindings([path]))
        source = unpack(frozen, old_corpus)
        baseline = replay(source, settings)
        results = {"wide": replay(source, settings, wide=True)}
        diagnostic = {}

        def candidate(baseline_response: Any, source: Any = source) -> Any:
            nonlocal diagnostic
            result, diagnostic = select(source["question"], baseline_response, corpus, articles, top_k=source["request"]["top_k"])
            return result

        results["explicit_reference"] = replay(source, settings, replacement=candidate)
        base_labels = label_retention(case, baseline["trace"]["retrieval"]["results"], old_articles)
        comparisons = {}
        for arm, result in results.items():
            labels = label_retention(case, result["trace"]["retrieval"]["results"], old_articles)
            comparisons[arm] = {"full_trace_identical": result["trace"] == baseline["trace"],
                "labels": labels, "labelled_article_ids_lost": sorted(set(base_labels["matching_article_ids"])
                                                                          - set(labels["matching_article_ids"])),
                "adequacy_metadata_changed": (result["trace"]["metadata"]["evidence_adequacy"]
                                              != baseline["trace"]["metadata"]["evidence_adequacy"]),
                "gate_decision_changed": (result["trace"]["metadata"]["evidence_adequacy"]["adequate"]
                                          != baseline["trace"]["metadata"]["evidence_adequacy"]["adequate"]),
                "boundary": result["boundary"],
                "condition_surfaces_added": sorted(set(condition_surfaces(result["trace"]["evidence"]))
                                                    - set(condition_surfaces(baseline["trace"]["evidence"]))),
                "condition_surfaces_lost": sorted(set(condition_surfaces(baseline["trace"]["evidence"]))
                                                   - set(condition_surfaces(result["trace"]["evidence"])))}
            if not comparisons[arm]["full_trace_identical"]:
                files.write(output / f"regression_{number:03}_{arm}.json", result)
        regressions.append({"id": case["id"], "baseline_labels": base_labels, "explicit_diagnostic": copy.deepcopy(diagnostic),
                            "arms": comparisons})
        if number % 10 == 0:
            print(json.dumps({"replayed_old_cases": number + 1}), flush=True)
    if policy.denied:
        raise ValueError("Unexpected network activity")
    summary = {"version": "benchmark_retrieval_repair_v0.2", "model_calls": 0, "oauth_calls": 0, "new_slots": 0,
        "historical_baselines_identical": sum(c["historical_trace_identical"] for c in cases),
        "fresh_reference_pages_verified": len(fresh_pages), "pdf_hashes_verified": len(articles),
        "new_case_service_runs": 15, "old_case_service_runs": len(regressions) * 3,
        "old_cases": len(regressions), "network_denials": policy.denied, "production_changes": False,
        "arms": {}, "independent_accuracy": None,
        "limitations": ["Five exposed development cases, not independent validation", "No generated answers or provider fix",
                        "Page/quote retention does not establish semantic ownership or scientific adequacy",
                        "Two original unmapped quotes remain unmapped; 12 mapped quotes measured separately",
                        "No new expert labels; old positive article labels are coarse",
                        "Uncited questions, quantity validation, completeness, ORM/concurrency and browser untested"]}
    for arm in ARMS:
        values = [c["arms"][arm]["source_presence"] for c in cases]
        summary["arms"][arm] = {"reference_pages_retained": sum(len(v["reference_pages_present"]) for v in values),
            "reference_pages_total": sum(v["reference_pages_total"] for v in values),
            "mapped_quotes_retained": sum(v["mapped_quotes_retained"] for v in values),
            "mapped_quotes_total": sum(v["mapped_quotes_total"] for v in values)}
        if arm != "baseline":
            summary["arms"][arm].update(old_full_trace_changes=[r["id"] for r in regressions if not r["arms"][arm]["full_trace_identical"]],
                old_labelled_article_losses=[r["id"] for r in regressions if r["arms"][arm]["labelled_article_ids_lost"]],
                old_adequacy_metadata_changes=[r["id"] for r in regressions if r["arms"][arm]["adequacy_metadata_changed"]],
                old_gate_decision_changes=[r["id"] for r in regressions if r["arms"][arm]["gate_decision_changed"]])
    # Bind remaining algorithm helpers and PDFs; verify again before final report.
    bindings.update(files.bindings([ROOT / "scripts/retrieval_ablation_labels.py", ROOT / "scripts/review_retrieval_ablation.py",
                                   *[Path(a["original_pdf_path"]) for a in articles.values()]]))
    files.verify(bindings)
    report = {"summary": summary, "bindings": bindings, "cases": cases, "regressions": regressions,
              "articles": articles, "fresh_reference_pages": fresh_pages}
    html = render(report)
    qa = check_html(html, article_count=len(articles), case_count=len(cases))
    files.write(output / "report.json", report)
    files.save(output / "review.html", html.encode())
    files.write(output / "qa.json", qa)
    files.manifest(output)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--captured", type=Path, default=BASE / "capture_v02")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    policy = files.NetworkPolicy()
    sys.addaudithook(policy)
    print(json.dumps(evaluate(args.captured, args.output, policy), ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
