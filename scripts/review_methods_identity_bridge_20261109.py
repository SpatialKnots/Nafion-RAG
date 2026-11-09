"""Read-only candidate/source/layout review; no runtime patch or service invocation."""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import fitz

from app.classification.rules import classify_source_type
from app.extraction.text_quality import detect_formula_like_lines
from app.generation.providers import Evidence
from app.generation.source_role_assembly import prepare as assemble
from scripts import gigachat_answer_smoke as files
from scripts.benchmark_retrieval_capture_20261105 import read
from scripts.check_requested_context_runtime_20261105 import render
from scripts.methods_identity_bridge_20261109 import BridgeError, inspect
from scripts.reference_quote_runtime_checks_20261105 import CORPUS_BASE
from scripts.review_benchmark_retrieval_repair_20261105 import check_html, detail

BASE = files.ROOT / "output/methods_identity_bridge_20261109"
PARENT = files.ROOT / "output/source_role_assembly_20261109"


def anchors(value: Any) -> list[dict[str, Any]]:
    result = []
    if isinstance(value, dict):
        if {"chunk_id", "start", "end", "text", "raw_chunk_sha256"} <= set(value):
            result.append(value)
        for item in value.values():
            result.extend(anchors(item))
    elif isinstance(value, (list, tuple)):
        for item in value:
            result.extend(anchors(item))
    return result


def run(output: Path) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=False)
    app = read(BASE / "tests_v03.scope.json")["unchanged_app_bindings"]
    files.verify(app)
    prior = read(PARENT / "review_v02/report.json")
    files.verify_manifest(PARENT / "review_v02")
    files.verify_manifest(PARENT / "compare_v02")
    files.verify(prior["bindings"])
    baseline_paths = [PARENT / "compare_v02/service" / name for name in [
        *(f"Q{i:02}_current.json" for i in range(1, 6)), *(f"old/{i:03}.json" for i in range(76)),
        *(f"Q{i:02}_native_unsent.json" for i in range(1, 6))]]
    baseline = files.bindings(baseline_paths)
    cases = read(BASE / "controls_v02.json")
    controls = []
    for case in cases:
        try:
            result = inspect(*[Evidence(**e) for e in case["sources"]], case["layers"])
        except BridgeError as exc:
            complete, result = False, {"reason": str(exc)}
        else:
            complete = True
        if complete != case["expected_candidate"]:
            raise ValueError("Bridge control differs: " + case["id"])
        controls.append({**case, "observed_candidate": complete, "observed": result})
    real = controls[0]
    candidate = real["observed"]
    sources = [Evidence(**e) for e in real["sources"]]
    blocked = assemble(real["question"], sources, real["reference"], real["layers"])
    if blocked.eligible:
        raise ValueError("Read-only audit unexpectedly changed runtime admission")
    methods = sources[1]
    triggers = [{"start": m.start(), "end": m.end(), "text": m.group()} for m in re.finditer(
        r"^\s*(?:Fig\.|Figure|Рис\.)\s*\d+", methods.text, re.I | re.M)]
    section = candidate["bindings"]["methods_section"]
    lines = [line for line in section["text"].splitlines() if line.strip()]
    classification = {"registered": methods.source_type, "current_whole_chunk": classify_source_type(methods.text),
        "raw_caption_triggers": triggers, "material_preparation_span": section,
        "current_section_classifier": classify_source_type(section["text"]),
        "nonempty_lines": len(lines), "formula_like_lines": detect_formula_like_lines(section["text"]),
        "formula_line_fraction": len(detect_formula_like_lines(section["text"])) / len(lines),
        "source_type_written_back": False}
    corpus, articles = read(CORPUS_BASE / "Q01/corpus.json"), read(CORPUS_BASE / "Q01/articles.json")
    pdfs = []
    for article in articles.values():
        path = Path(article["original_pdf_path"])
        if files.sha(path.read_bytes()) != article["original_pdf_sha256"]:
            raise ValueError("Original PDF changed")
        pdfs.append(path)
    pages, fresh_text = [], {}
    for source in sources:
        if corpus[source.chunk_id]["full_text"] != source.text or corpus[source.chunk_id]["source_type"] != source.source_type:
            raise ValueError("Unchanged raw source or registered type differs")
        path = Path(articles[source.article_id]["original_pdf_path"])
        with fitz.open(path) as pdf:
            for number in range(source.page_start, source.page_end + 1):
                raw = pdf[number - 1].get_text()
                fresh_text[(source.article_id, number)] = raw
                pages.append({"path": str(path), "page": number, "sha256": files.sha(raw.encode())})
    bound = anchors(candidate["bindings"])
    matches = []
    raw_by_chunk = {s.chunk_id: s for s in sources}
    for anchor in bound:
        raw = raw_by_chunk[anchor["chunk_id"]]
        if (raw.text[anchor["start"]:anchor["end"]] != anchor["text"]
                or files.sha(raw.text.encode()) != anchor["raw_chunk_sha256"]):
            raise ValueError("Raw bridge anchor changed")
        found = [n for (article, n), text in fresh_text.items() if article == anchor["article_id"]
                 and anchor["page_start"] <= n <= anchor["page_end"] and anchor["text"] in text]
        if not found:
            raise ValueError("Bridge raw anchor absent from fresh PDF pages")
        matches.append({"anchor": anchor, "fresh_pdf_pages": found})
    unique = {(a["article_id"], a["chunk_id"], a["start"], a["end"], a["text"]) for a in bound}
    for page in (1, 3, 7):
        original = files.ROOT / f"tmp/pdfs/methods_bridge_20261109/page_{page:02}.png"
        target = output / f"page_{page:02}.png"
        files.save(target, original.read_bytes())
    suites = list(ET.parse(BASE / "tests_v03.xml").getroot().iter("testsuite"))
    counts = {k: sum(int(s.get(k, 0)) for s in suites) for k in ("tests", "failures", "errors", "skipped")}
    scope = read(BASE / "tests_v03.scope.json")
    files.verify(scope["input_bindings"])
    if counts["failures"] or counts["errors"] or scope["exit_code"] or scope["external_network_denials"]:
        raise ValueError("Diagnostic tests failed or external network attempted")
    summary = {"version": candidate["version"], "candidate_status": candidate["status"],
        "target_code": candidate["target_code"], "base_code": candidate["base_code"],
        "explicit_assumption": candidate["explicit_assumption"], "control_cases": len(controls),
        "real_positive": 1, "constructed_positives": sum(c["expected_candidate"] for c in cases[1:]),
        "constructed_negatives": sum(not c["expected_candidate"] for c in cases[1:]), "tests": counts,
        "unchanged_app_python_files": sum(p.endswith(".py") for p in app),
        "prior_service_baselines_verified_not_rerun": 81, "prior_native_bodies_verified_not_reprepared": 5,
        "new_service_runs": 0, "new_native_preparations": 0, "real_model_calls": 0, "real_oauth_calls": 0,
        "new_slots": 0, "DB_or_source_type_writes": 0, "runtime_admission": blocked.reason,
        "corpus_PDF_hashes": len(pdfs), "fresh_pages": pages, "raw_anchor_observations": len(bound),
        "unique_raw_anchors": len(unique), "visual_review": "PDF1/3/7 inspected; rendered copies retained",
        "scientific_accuracy": None,
        "limitations": ["One exposed work; ordered-list association is declared, not general semantic ownership",
            "Read-only diagnostic candidate; mixed type/explicit-marker runtime guards remain",
            "No new production assembly/live model answer, independent evaluation or new full-suite run"]}
    paths = [*map(Path, app), Path(__file__), files.ROOT / "scripts/methods_identity_bridge_20261109.py",
        files.ROOT / "scripts/methods_bridge_controls_20261109.py", files.ROOT / "scripts/test_methods_identity_bridge_20261109.py",
        files.ROOT / "tests/unit/test_methods_identity_bridge.py", BASE / "controls_v02.json", BASE / "tests_v03.xml",
        BASE / "tests_v03.scope.json", files.ROOT / "docs/records/methods_identity_bridge_protocol_2026-11-09_v0.1.md", *pdfs]
    bindings = files.bindings(paths)
    report = {"summary": summary, "candidate": candidate, "classification": classification, "controls": controls,
        "source_matches": matches, "bindings": bindings, "app_bindings": app, "prior_baselines": baseline,
        "cases": copy.deepcopy(prior["cases"]), "articles": articles, "regressions": prior["regressions"]}
    document = render(report).replace("Сохранение запрошенного контекста в runtime", "Read-only: Methods identity bridge")
    note = ("<p><strong>Кандидат связи подтверждён конечным разбором исходного текста при явно объявленном "
            "сопоставлении упорядоченных списков. Runtime admission и source_type не менялись.</strong></p>")
    document = document.replace("<table>", note + "<table>", 1)
    extra = detail("Полная цепочка источников и явное правило списков", candidate)
    extra += detail("Диагностика source_type", classification)
    extra += detail("Raw anchors и свежие PDF страницы", matches)
    for case in controls:
        extra += detail(case["id"] + " — " + ("candidate" if case["observed_candidate"] else "unresolved"), case)
    for page in (1, 3, 7):
        extra += (f"<details><summary>Визуально проверенная PDF-страница {page}</summary>"
                  f"<img src='page_{page:02}.png' style='max-width:100%' alt='PDF page {page}'></details>")
    document = document.replace("<h2>TAC:", "<h2>Methods bridge и контрольные случаи</h2>" + extra + "<h2>TAC:")
    qa = check_html(document, article_count=len(articles), case_count=5)
    files.verify(app)
    files.verify(bindings)
    files.verify(baseline)
    files.write(output / "report.json", report)
    files.write(output / "qa.json", qa)
    files.save(output / "review.html", document.encode())
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    policy = files.NetworkPolicy()
    sys.addaudithook(policy)
    summary = run(args.output)
    if policy.denied:
        raise ValueError("External network attempted")
    files.write(args.output / "network.json", {"denials": policy.denied})
    files.manifest(args.output)
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
