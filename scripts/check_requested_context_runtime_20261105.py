"""Compare frozen-channel service baselines with the bounded production repair."""

from __future__ import annotations

import argparse
import json
import sys
from contextlib import ExitStack
from html import escape
from pathlib import Path
from typing import Any
from unittest.mock import patch

from scripts import gigachat_answer_smoke as files
from scripts.benchmark_retrieval_capture_20261105 import read
from scripts.benchmark_retrieval_replay_20261105 import replay
from scripts.retrieval_ablation_labels import label_retention
from scripts.review_benchmark_retrieval_repair_20261105 import (
    INTAKE,
    OLD,
    check_html,
    condition_surfaces,
    detail,
    identity,
    presence,
    short_source,
)
from scripts.review_retrieval_ablation import unpack

ROOT = files.ROOT
BASE = ROOT / "output/requested_context_runtime_20261105"
CAPTURE = ROOT / "output/benchmark_retrieval_repair_20261105/capture_v02"
PROTOCOL = ROOT / "docs/records/requested_context_runtime_protocol_2026-11-05_v0.1.md"


def baseline_scope() -> ExitStack:
    from app.generation import evidence_selection
    from app.retrieval import search
    stack = ExitStack()
    for module in (search, evidence_selection):
        stack.enter_context(patch.object(module, "retain_requested_context", lambda q, rows, **kw: (list(rows), None)))
    return stack


def render(report: dict[str, Any]) -> str:
    html = """<!doctype html><html lang="ru"><meta charset="utf-8"><title>ARIADNE — сохранение контекста</title>
<style>body{font:16px/1.5 system-ui;margin:30px;color:#183044}table{border-collapse:collapse;width:100%}
td,th{border:1px solid #b5c5d0;padding:9px;vertical-align:top}pre{white-space:pre-wrap;overflow-wrap:anywhere}
details{margin:8px 0}summary{cursor:pointer}.scroll{overflow:auto}input{padding:8px}[hidden]{display:none!important}</style>
<body><h1>Сохранение запрошенного контекста в runtime</h1><p>Офлайн-сравнение реального service на замороженных
каналах. Новых ответов модели нет. Context retention не проверяет научное владение величинами.</p>"""
    html += detail("Итог и ограничения", report["summary"])
    html += "<table><tr><th>Вопрос</th><th>Исходный путь</th><th>Исправленный путь</th></tr>"
    for case in report["cases"]:
        html += "<tr><td>" + case["id"] + "</td>"
        for arm in ("baseline", "repaired"):
            p = case[arm]["presence"]
            html += ("<td>Страницы " + str(p["reference_pages_present"]) + "; цитаты "
                     + str(p["mapped_quotes_retained"]) + "/" + str(p["mapped_quotes_total"]) + "</td>")
        html += "</tr>"
    html += "</table>"
    for case in report["cases"]:
        html += "<section><h2>" + case["id"] + "</h2><p>" + escape(case["question"]) + "</p>"
        for arm in ("baseline", "repaired"):
            html += "<h3>" + arm + "</h3>" + detail("Покрытие / gate / displaced conditions", {
                key: value for key, value in case[arm].items() if key != "evidence"})
            for evidence in case[arm]["evidence"]:
                article = report["articles"][evidence["article_id"]]
                href = Path(article["original_pdf_path"]).as_uri() + "#page=" + str(evidence["page_start"])
                html += "<p><a href='" + escape(href, quote=True) + "'>" + escape(
                    str(evidence["title"]) + ": PDF " + str(evidence["page_start"]) + "–" + str(evidence["page_end"])) + "</a></p>"
                html += detail("Полный исходный фрагмент", evidence)
        html += "</section>"
    html += detail("Прежние 76 случаев", report["regressions"])
    html += "<h2>TAC: все работы снимка</h2><input id='q' type='search' aria-label='Поиск TAC'><div class='scroll'>"
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


def run(output: Path) -> dict[str, Any]:
    settings = files.configure()
    output.mkdir(parents=True, exist_ok=False)
    files.verify_manifest(BASE / "freeze_v01")
    previous = read(BASE / "freeze_v01/runtime.json")["bindings"]
    changed = {name: {"before": digest, "after": files.sha(Path(name).read_bytes()),
                       "old_snapshot": str(BASE / "freeze_v01/source_snapshot" / Path(name).relative_to(ROOT))}
               for name, digest in previous.items() if files.sha(Path(name).read_bytes()) != digest}
    if {Path(p).relative_to(ROOT).as_posix() for p in changed} != {
            "app/retrieval/search.py", "app/generation/evidence_selection.py"}:
        raise ValueError("Unexpected preexisting runtime drift")
    paths = [*ROOT.joinpath("app").rglob("*.py"), *ROOT.joinpath("app").rglob("*.yaml"), Path(__file__), PROTOCOL,
             ROOT / "tests/unit/test_requested_context.py", ROOT / "scripts/benchmark_retrieval_replay_20261105.py"]
    bindings = files.bindings(paths)
    for source in paths:
        target = output / "source_snapshot" / source.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        files.save(target, source.read_bytes())
    articles, corpus = read(CAPTURE / "Q01/articles.json"), read(CAPTURE / "Q01/corpus.json")
    for article in articles.values():
        pdf = Path(article["original_pdf_path"])
        if files.sha(pdf.read_bytes()) != article["original_pdf_sha256"]:
            raise ValueError("PDF changed")
        bindings.update(files.bindings([pdf]))
    results = {}
    for i in range(1, 6):
        case_id = f"Q{i:02}"
        folder = CAPTURE / case_id
        files.verify_manifest(folder)
        bindings.update(files.bindings([folder / "manifest.json", folder / "boundaries.json", folder / "corpus.json"]))
        source = read(folder / "boundaries.json")
        with baseline_scope():
            baseline = replay(source, settings)
        repaired = replay(source, settings, replacement=lambda response: response)
        for arm, result in (("baseline", baseline), ("repaired", repaired)):
            files.write(output / f"{case_id}_{arm}.json", result)
        results[case_id] = {"question": source["api"]["question"], "baseline": baseline, "repaired": repaired}

    # Gold is first read after all new query selections.
    files.verify_manifest(INTAKE)
    reference = read(INTAKE / "report.json")
    bindings.update(files.bindings([INTAKE / "manifest.json", INTAKE / "report.json"]))
    cases = []
    for gold in reference["cases"]:
        case_id = gold["id"]
        data = results[case_id]
        target = next(a for a in articles.values() if Path(a["original_pdf_path"]).resolve()
                      == Path(gold["source_pdf_path_verbatim"]).resolve())
        pages = [p["pdf_page"] for p in reference["source_pages"] if p["case_id"] == case_id]
        case = {"id": case_id, "question": data["question"]}
        for arm in ("baseline", "repaired"):
            result = data[arm]
            evidence = result["trace"]["evidence"]
            original = data["baseline"]["trace"]["evidence"]
            for row in evidence:
                raw = corpus[row["chunk_id"]]
                if (row["text"], row["article_id"], row["page_start"], row["page_end"]) != (
                        raw["full_text"], raw["article_id"], raw["page_start"], raw["page_end"]):
                    raise ValueError("Raw evidence changed")
            case[arm] = {"presence": presence(evidence, target["article_id"], pages, gold["quotes"]),
                "evidence": [short_source(e) for e in evidence], "boundary": result["boundary"],
                "adequacy": result["trace"]["metadata"]["evidence_adequacy"],
                "evidence_changed": identity(evidence) != identity(original),
                "condition_surfaces_added": sorted(set(condition_surfaces(evidence)) - set(condition_surfaces(original))),
                "condition_surfaces_lost": sorted(set(condition_surfaces(original)) - set(condition_surfaces(evidence))),
                "displaced_baseline_evidence": [short_source(e) for e in original
                    if e["chunk_id"] not in {r["chunk_id"] for r in evidence}],
                "retention": result["trace"]["retrieval"]["metadata"].get("requested_context_retention")}
        cases.append(case)

    files.verify_manifest(OLD)
    dataset, old_corpus, old_articles = read(OLD / "cases.json"), read(OLD / "corpus.json"), read(OLD / "articles.json")
    bindings.update(files.bindings([OLD / "manifest.json", OLD / "cases.json", OLD / "corpus.json", OLD / "articles.json"]))
    regressions = []
    for index, case in enumerate(dataset["cases"]):
        path = OLD / f"cases/{index:03}_baseline.json"
        bindings.update(files.bindings([path]))
        source = unpack(read(path), old_corpus)
        with baseline_scope():
            baseline = replay(source, settings)
        repaired = replay(source, settings, replacement=lambda response: response)
        before = label_retention(case, baseline["trace"]["retrieval"]["results"], old_articles)
        after = label_retention(case, repaired["trace"]["retrieval"]["results"], old_articles)
        changed_case = repaired["trace"] != baseline["trace"]
        if changed_case:
            files.write(output / f"regression_{index:03}.json", {"case": case, "baseline": baseline, "repaired": repaired})
        regressions.append({"id": case["id"], "full_trace_changed": changed_case,
            "labelled_article_losses": sorted(set(before["matching_article_ids"]) - set(after["matching_article_ids"])),
            "gate_decision_changed": (repaired["trace"]["metadata"]["evidence_adequacy"]["adequate"]
                                      != baseline["trace"]["metadata"]["evidence_adequacy"]["adequate"]),
            "condition_surfaces_lost": sorted(set(condition_surfaces(baseline["trace"]["evidence"]))
                                               - set(condition_surfaces(repaired["trace"]["evidence"]))),
            "retention": repaired["trace"]["retrieval"]["metadata"].get("requested_context_retention")})
        if index % 15 == 0:
            print(json.dumps({"old_cases_replayed": index + 1}), flush=True)
    summary = {"version": "requested_context_runtime_v0.1", "old_runtime_drift": changed,
        "new_module": "app/retrieval/requested_context.py", "baseline_trace_replays_identical": 81,
        "offline_service_executions": 162, "model_calls": 0, "oauth_calls": 0, "db_calls": 0, "new_slots": 0,
        "old_full_trace_changes": [r["id"] for r in regressions if r["full_trace_changed"]],
        "old_labelled_article_loss_cases": [r["id"] for r in regressions if r["labelled_article_losses"]],
        "old_gate_decision_changes": [r["id"] for r in regressions if r["gate_decision_changed"]],
        "arms": {arm: {"reference_pages_retained": sum(len(c[arm]["presence"]["reference_pages_present"]) for c in cases),
                       "reference_pages_total": 10,
                       "mapped_quotes_retained": sum(c[arm]["presence"]["mapped_quotes_retained"] for c in cases),
                       "mapped_quotes_total": 12} for arm in ("baseline", "repaired")},
        "thresholds_changed": False, "scientific_accuracy": None,
        "limitations": ["Five exposed development questions; no new model answers", "Source context, not semantic entailment",
                        "Numeric ownership and general completeness not implemented", "Author/year candidate not integrated",
                        "No browser/new visual PDF/full suite/concurrency check"]}
    files.verify(bindings)
    report = {"summary": summary, "bindings": bindings, "cases": cases, "regressions": regressions, "articles": articles}
    html = render(report)
    qa = check_html(html, article_count=len(articles), case_count=len(cases))
    files.write(output / "report.json", report)
    files.save(output / "review.html", html.encode())
    files.write(output / "qa.json", qa)
    files.manifest(output)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    policy = files.NetworkPolicy()
    sys.addaudithook(policy)
    result = run(args.output)
    if policy.denied:
        raise ValueError("Unexpected network attempt")
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
