"""Offline requirement-map review with immutable parents and original PDF evidence."""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from html import escape, unescape
from pathlib import Path
from urllib.parse import urlparse

import fitz

from app.documents.service import build_pdf_url
from app.generation.answer_requirements import build_requirements, validate_requirements
from app.generation.requirements_routes import VERSION, render_requirements
from scripts import gigachat_answer_smoke as files
from scripts.answer_requirements_20261109 import BASE, PROTOCOL
from scripts.benchmark_retrieval_capture_20261105 import read
from scripts.check_requested_context_runtime_20261105 import render
from scripts.reference_quote_runtime_checks_20261105 import CORPUS_BASE
from scripts.review_benchmark_retrieval_repair_20261105 import check_html, detail
from scripts.review_methods_identity_bridge_20261109 import anchors


def local_links(document: str, articles: dict) -> tuple[str, list[dict]]:
    """Map only known original articles; synthetic IDs never become purported PDFs."""
    links = []

    def replace_link(match):
        href, label = unescape(match[1]), match[2]
        path = urlparse(href).path
        target = re.fullmatch(r"/(?:ui/)?articles/([^/]+)/(?:pdf|bibliography)", path)
        if target is None:
            raise ValueError("Unexpected review link: " + path)
        article = articles.get(target[1])
        if article is None:
            links.append({"runtime_href": href, "state": "constructed_source_no_registered_PDF"})
            return "<span title='Искусственный источник: PDF не зарегистрирован'>" + label + "</span>"
        page = re.search(r"page=(\d+)", href)
        number = int(page[1]) if page else 1
        pdf = Path(article["original_pdf_path"])
        if not pdf.is_file():
            raise ValueError("Missing actual PDF")
        resolved = pdf.as_uri() + "#page=" + str(number)
        links.append({"runtime_href": href, "state": "registered_original_PDF", "local_href": resolved})
        return '<a href="' + escape(resolved, quote=True) + '">' + label + "</a>"

    return re.sub(r'<a href="([^"]*)">(.*?)</a>', replace_link, document, flags=re.S), links


def run(output: Path, comparison: Path, junit: Path) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    for folder in (BASE / "freeze_v01", comparison):
        files.verify_manifest(folder)
    scope = read(junit.with_suffix(".scope.json"))
    files.verify(scope["test_bindings"])
    files.verify(scope["app_bindings"])
    suites = list(ET.parse(junit).getroot().iter("testsuite"))
    counts = {k: sum(int(s.get(k, 0)) for s in suites) for k in ("tests", "errors", "failures", "skipped")}
    if scope["exit_code"] or scope["external_network_denials"] or counts["errors"] or counts["failures"]:
        raise ValueError("Affected test scope failed")
    initial = read(BASE / "freeze_v01/bindings.json")
    drift = [{"path": name, "before": digest, "after": files.sha(Path(name).read_bytes())}
             for name, digest in initial.items() if Path(name).is_relative_to(files.ROOT / "app")
             and files.sha(Path(name).read_bytes()) != digest]
    if {Path(d["path"]).relative_to(files.ROOT).as_posix() for d in drift} != {
            "app/main.py", "app/generation/preparation_routes.py"}:
        raise ValueError("Unexpected old app drift")
    new = {str(p.resolve()) for p in (files.ROOT / "app").rglob("*.py")} - set(initial)
    if new != {str((files.ROOT / p).resolve()) for p in
               ("app/generation/answer_requirements.py", "app/generation/requirements_routes.py")}:
        raise ValueError("Unexpected new app modules")
    cases, outcomes = read(BASE / "controls_v01.json"), []
    for case in cases:
        original = copy.deepcopy(case["parent"])
        mapped = build_requirements(case["parent"])
        validate_requirements(mapped, original)
        if case["parent"] != original:
            raise ValueError("Requirement diagnostic mutated parent")
        if mapped["status"] == "not_applicable":
            if case["id"] != "unsupported_query":
                raise ValueError("Unexpected unsupported control")
        elif mapped["requirements"][-1]["state"] != case["expected_identity"]:
            raise ValueError("Declared identity outcome differs: " + case["id"])
        outcomes.append({**case, "requirements": mapped})
    files.write(output / "control_outcomes.json", outcomes)
    articles, corpus = read(CORPUS_BASE / "Q01/articles.json"), read(CORPUS_BASE / "Q01/corpus.json")
    pdfs = []
    for article in articles.values():
        path = Path(article["original_pdf_path"])
        if files.sha(path.read_bytes()) != article["original_pdf_sha256"]:
            raise ValueError("Original PDF changed")
        pdfs.append(path)
    real = outcomes[0]
    fresh = {}
    for source in real["parent"]["evidence"]:
        raw = corpus[source["chunk_id"]]
        if source["text"] != raw["full_text"] or source["source_type"] != raw["source_type"]:
            raise ValueError("Frozen real source changed")
        with fitz.open(articles[source["article_id"]]["original_pdf_path"]) as pdf:
            for n in range(source["page_start"], source["page_end"] + 1):
                fresh[(source["article_id"], n)] = pdf[n - 1].get_text()
                pdf[n - 1].get_pixmap(matrix=fitz.Matrix(1.2, 1.2)).save(str(output / f"page_{n:02}.png"))
    matches = []
    raw_by_chunk = real["parent"]["sources"]["chunks"]
    for anchor in anchors(real["requirements"]):
        raw = raw_by_chunk[anchor["chunk_id"]]["text"]
        pages = [n for (a, n), text in fresh.items() if a == anchor["article_id"]
                 and anchor["page_start"] <= n <= anchor["page_end"] and anchor["text"] in text]
        if raw[anchor["start"]:anchor["end"]] != anchor["text"] or files.sha(raw.encode()) != anchor["raw_chunk_sha256"] or not pages:
            raise ValueError("Map anchor differs from raw/fresh PDF")
        matches.append({"anchor": anchor, "fresh_PDF_pages": pages})

    ui, adapters = [], []
    for case in outcomes:
        p = copy.deepcopy(case["parent"])
        # The controls deliberately have minimal synthetic preparation wrappers.
        # Supply only the old renderer's empty qualifier presentation and known
        # source links; no metadata/decision/source is inferred or rewritten.
        p["query_qualifiers"] = {"articles": []}
        p["source_links"] = [{"citation_id": e["citation_id"],
            "pdf_url": build_pdf_url(e["article_id"], "original", e["page_start"]), "context_url": None} for e in p["evidence"]]
        payload = {"version": VERSION, "preparation": p, "requirements": build_requirements(p),
                   "generation_performed": False, "external_request_constructed": False, "network_ready": False}
        validate_requirements(payload["requirements"], p)
        fragment = render_requirements(payload)
        files.save(output / ("runtime_UI_" + str(len(adapters)) + ".html"), fragment.encode())
        local, links = local_links(fragment, articles)
        adapters.append({"id": case["id"], "synthetic_presentation_only_fields": ["query_qualifiers", "source_links"], "links": links})
        ui.append('<div data-requirement-case="' + escape(case["id"], quote=True) + '"><h2>' + escape(case["id"])
                  + " — synthetic preparation</h2>" + local + "</div>")
    ui_document = ("<!doctype html><html lang='ru'><meta charset='utf-8'><title>ARIADNE — требования ответа</title>"
        "<style>body{font:16px/1.5 system-ui;color:#183044;max-width:1150px;margin:25px auto;padding:0 20px}"
        ".claim-card{border:1px solid #abc;border-radius:8px;padding:16px;margin:16px 0}"
        "pre{white-space:pre-wrap;overflow-wrap:anywhere}table{width:100%;border-collapse:collapse}"
        "td,th{padding:8px;border:1px solid #abc}summary{cursor:pointer}details{margin:8px 0}</style><body>"
        "<h1>Требования и пробелы: read-only</h1><p>Все подготовки здесь SYNTHETIC. В первом случае raw тексты — "
        "реальная раскрытая работа Lin2020. Исходные запреты сохранены, научная поддержка не оценена. "
        "Ссылки локальной копии сопоставлены с известными PDF; у искусственных источников PDF не выдуманы.</p>"
        + "".join(ui) + "</body></html>")
    expected_rows = sum(len(c["requirements"]["requirements"]) for c in outcomes)
    if (ui_document.count("data-requirement-case=") != len(outcomes)
            or ui_document.count("data-answer-requirement=") != expected_rows
            or "<script>bad</script>" in ui_document):
        raise ValueError("UI control inventory differs")
    files.save(output / "requirements_UI.html", ui_document.encode())
    files.write(output / "UI_adapters.json", adapters)

    summary = {"version": real["requirements"]["version"], "tests": counts, "external_network_denials": scope["external_network_denials"],
        "controls": len(outcomes), "mapped": sum(c["requirements"]["status"] == "mapped" for c in outcomes),
        "requirement_rows": expected_rows, "states": dict(Counter(r["state"] for c in outcomes for r in c["requirements"]["requirements"])),
        "current_frozen_comparison": read(comparison / "service/summary.json"), "runtime_drift": drift, "new_modules": sorted(new),
        "raw_anchor_observations": len(matches),
        "unique_anchors": len({(m["anchor"]["chunk_id"], m["anchor"]["start"], m["anchor"]["end"]) for m in matches}),
        "corpus_PDF_hashes": len(pdfs), "fresh_pages": [{"article_id": a, "page": n, "sha256": files.sha(t.encode())}
            for (a, n), t in fresh.items()], "real_model_calls": 0, "real_oauth_exchanges": 0, "new_slots": 0,
        "new_DB_preparation": False, "scientific_accuracy": None, "browser_layout": "not_verified_prior_file_URL_policy_block",
        "limitations": ["One finite query family and exposed real source, not independent evaluation",
            "Synthetic preparation/DB seams; no fresh production DB preparation performed",
            "Map is diagnostic only; no retrieval actions or new admission decisions",
            "No scientific quality/refusal improvement measured; original75% unchanged"]}
    prior = read(files.ROOT / "output/methods_identity_runtime_20261109/review_v02/report.json")
    report = {"summary": summary, "cases": copy.deepcopy(prior["cases"]), "articles": articles,
              "regressions": summary["current_frozen_comparison"]["regressions"], "controls": outcomes, "source_matches": matches}
    html = render(report).replace("Сохранение запрошенного контекста в runtime", "Карта требований и пробелов ответа")
    extra = ("<h2>Карта требований: одно семейство</h2><p>Диагностика не меняет исходные запреты. "
        "Отсутствие распознанного шаблона не является отсутствием научных данных. Новые API/UI вызываются явно.</p>"
        + detail("Состояния на объявленных controls", [{"id": c["id"], "rows": [{"role": r["id"], "state": r["state"]}
            for r in c["requirements"]["requirements"]]} for c in outcomes])
        + "<iframe src='requirements_UI.html' title='Read-only requirements UI' style='width:100%;height:1100px;"
          "border:1px solid #abc'></iframe>" + detail("Raw anchors и свежие PDF", matches))
    for n in (1, 3, 7):
        extra += (f"<details><summary>Свежий PDF-рендер {n}</summary>"
                  f"<img src='page_{n:02}.png' style='max-width:100%' alt='PDF {n}'></details>")
    html = html.replace("<h2>TAC:", extra + "<h2>TAC:")
    qa = check_html(html, article_count=len(articles), case_count=5)
    qa.update(requirement_cases=len(outcomes), requirement_rows=expected_rows, original_parent_unchanged=True)
    paths = [*files.ROOT.joinpath("app").rglob("*.py"), Path(__file__), PROTOCOL,
        files.ROOT / "scripts/answer_requirements_20261109.py", files.ROOT / "scripts/answer_requirements_controls_20261109.py",
        files.ROOT / "scripts/test_answer_requirements_20261109.py", files.ROOT / "tests/unit/test_answer_requirements.py",
        BASE / "controls_v01.json", junit, junit.with_suffix(".scope.json"), *pdfs]
    report["bindings"] = files.bindings(paths)
    files.verify(report["bindings"])
    files.write(output / "report.json", report)
    files.write(output / "qa.json", qa)
    files.save(output / "review.html", html.encode())
    return {k: v for k, v in summary.items() if k not in {"current_frozen_comparison", "runtime_drift", "new_modules"}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--comparison", type=Path, required=True)
    parser.add_argument("--junit", type=Path, required=True)
    args = parser.parse_args()
    policy = files.NetworkPolicy()
    sys.addaudithook(policy)
    summary = run(args.output, args.comparison, args.junit)
    files.write(args.output / "network.json", {"external_denials": policy.denied})
    if policy.denied:
        raise ValueError("External network attempted")
    files.manifest(args.output)
    print(json.dumps(summary, ensure_ascii=True), flush=True)


if __name__ == "__main__":
    main()
