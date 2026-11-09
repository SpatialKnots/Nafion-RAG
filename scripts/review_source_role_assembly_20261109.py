"""Review finite assembly, explicit real abstention and unchanged old inputs."""

from __future__ import annotations

import argparse
import copy
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

import fitz

from app.generation import answer_facts, service
from app.generation.providers import Evidence, GeneratedClaim, GenerationOutputError, ProviderResult
from app.generation.source_role_assembly import prepare
from app.retrieval.search import SearchResponse, SearchResult
from scripts import gigachat_answer_smoke as files
from scripts.benchmark_retrieval_capture_20261105 import read
from scripts.check_answer_fidelity_20261105 import native
from scripts.check_requested_context_runtime_20261105 import render
from scripts.reference_quote_runtime_checks_20261105 import CORPUS_BASE
from scripts.review_benchmark_retrieval_repair_20261105 import check_html, detail
from scripts.source_role_assembly_20261109 import BASE, PROTOCOL


def run(output: Path, comparison: Path, junit: Path) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    files.verify_manifest(BASE / "freeze_v01")
    files.verify_manifest(comparison)
    initial = read(BASE / "freeze_v01/bindings.json")
    drift = []
    for name, digest in initial.items():
        path = Path(name)
        if path.is_relative_to(files.ROOT / "app") and files.sha(path.read_bytes()) != digest:
            snapshot = BASE / "freeze_v01/source_snapshot" / path.relative_to(files.ROOT)
            if files.sha(snapshot.read_bytes()) != digest:
                raise ValueError("Missing bound initial source")
            drift.append({"path": name, "before": digest, "after": files.sha(path.read_bytes()), "snapshot": str(snapshot)})
    if {Path(d["path"]).relative_to(files.ROOT).as_posix() for d in drift} != {
            "app/generation/answer_facts.py", "app/generation/service.py", "app/ui.py"}:
        raise ValueError("Unexpected old app drift")
    new = {str(p) for p in files.ROOT.joinpath("app").rglob("*.py")} - set(initial)
    if new != {str(files.ROOT / "app/generation/source_role_assembly.py")}:
        raise ValueError("Unexpected new app modules")
    data = read(BASE / "controls_v01.json")
    controls = []
    roles_only = copy.deepcopy(data["real"])
    roles_only["id"] = "real_Lin_roles_only_explicit_label_missing"
    roles_only["sources"] = [e for i, e in enumerate(roles_only["sources"]) if i != 1]
    roles_only["layers"] = {e["chunk_id"]: roles_only["layers"][e["chunk_id"]] for e in roles_only["sources"]}
    files.write(output / "supplemental_real_roles_only.json", roles_only)
    for case in data["constructed"] + [data["real"], roles_only]:
        result = prepare(case["question"], [Evidence(**e) for e in case["sources"]], case["reference"], case["layers"])
        if result.eligible != case["expected_complete"]:
            raise ValueError("Assembly control differs: " + case["id"])
        if result.eligible:
            answer_facts.selection_records(result.evidence)
            for raw, derived in zip(result.display, result.evidence, strict=True):
                answer_facts.verify_raw_binding(derived.text, raw.text, article_id=raw.article_id, chunk_id=raw.chunk_id,
                    citation_id=raw.citation_id, page_start=raw.page_start, page_end=raw.page_end)
        controls.append({**case, "observed": result.metadata()})
    case = data["constructed"][0]
    bundle = prepare(case["question"], [Evidence(**e) for e in case["sources"]], case["reference"], case["layers"])
    settings = files.configure()
    captured = native("CONSTRUCTED_ASSEMBLY", {"retrieval": {"query": case["question"]},
        "evidence": [vars(e) for e in bundle.evidence]}, settings, output)
    body = read(output / "CONSTRUCTED_ASSEMBLY_native_unsent.json")
    rows = json.loads(body["messages"][-1]["content"].split("Source-bound records:\n", 1)[1])
    if rows != answer_facts.prompt_records(bundle.evidence):
        raise ValueError("Decoded native records changed")
    for row in rows:
        parent = next(e for e in bundle.display if e.citation_id == row["citation_id"])
        if (row["source_role_assembly"]["source_marker_quote"] not in parent.text
                or not all(f["source_quote"] in parent.text for f in row["source_bound_facts"])):
            raise ValueError("Native marker/fact quote absent from raw source")
    retrieval = SearchResponse(case["question"], [SearchResult(e["article_id"], e["chunk_id"], e["title"], e["doi"],
        e["page_start"], e["page_end"], e["source_type"], e["text"], 0.8, "constructed", full_text=e["text"],
        text_layer="original") for e in case["sources"]], {"explicit_source_reference": case["reference"]})
    actual = []
    for mode in ("complete", "abstain", "invalid"):
        class Synthetic:
            def __init__(self, selected_mode):
                self.mode = selected_mode

            def generate(self, question, evidence, **kwargs):
                selected = answer_facts.selection_records(evidence)
                chosen = [GeneratedClaim(k, [r["citation_id"]]) for k, r in selected.items()]
                if self.mode == "invalid":
                    chosen[-1] = GeneratedClaim("F999", chosen[-1].citation_ids)
                return ProviderResult(self.mode != "abstain", [] if self.mode == "abstain" else chosen, "SYNTHETIC_ASSEMBLY", None)

        with patch.object(service, "search_chunks", return_value=retrieval):
            try:
                response = service.answer_question(None, settings, case["question"], answer_language="ru", provider=Synthetic(mode))
            except GenerationOutputError as exc:
                if mode != "invalid":
                    raise
                result = {"mode": mode, "rejected": True, "error": str(exc)}
            else:
                if response.status != ("answered" if mode == "complete" else "insufficient_evidence"):
                    raise ValueError("Synthetic actual service outcome differs")
                result = {"mode": mode, "response": service.answer_response_to_dict(response)}
        files.write(output / f"SYNTHETIC_{mode}_service.json", result)
        actual.append(result)
    from app.ui import _prepared_statement_text
    display = [_prepared_statement_text(e.text, answer_facts.SOURCE_TYPE) for e in bundle.evidence]
    if not all("Electrolyte MIX-A." in text and "Текстовая связь разделов" in text for text in display):
        raise ValueError("UI literal marker missing")
    files.write(output / "constructed_UI_text.json", display)
    suites = list(ET.parse(junit).getroot().iter("testsuite"))
    counts = {k: sum(int(s.get(k, 0)) for s in suites) for k in ("tests", "failures", "errors", "skipped")}
    scope = read(junit.with_suffix(".scope.json"))
    if counts["failures"] or counts["errors"] or scope["exit_code"] or scope["external_network_denials"]:
        raise ValueError("Affected tests failed or external network attempted")
    articles, corpus = read(CORPUS_BASE / "Q01/articles.json"), read(CORPUS_BASE / "Q01/corpus.json")
    pdfs, fresh_pages = [], {}
    for article in articles.values():
        path = Path(article["original_pdf_path"])
        if files.sha(path.read_bytes()) != article["original_pdf_sha256"]:
            raise ValueError("Corpus original PDF changed")
        pdfs.append(path)
    for source in data["real"]["sources"]:
        parent = corpus[source["chunk_id"]]
        if source["text"] != parent["full_text"]:
            raise ValueError("Unchanged real source differs")
        path = Path(articles[source["article_id"]]["original_pdf_path"])
        with fitz.open(path) as pdf:
            for page in range(source["page_start"], source["page_end"] + 1):
                raw = pdf[page - 1].get_text()
                if not raw:
                    raise ValueError("Unexpected empty real control PDF page")
                fresh_pages[(str(path), page)] = {"path": str(path), "page": page, "sha256": files.sha(raw.encode())}
    summary = {"version": "source_role_assembly_v0.1", "constructed_controls": len(data["constructed"]),
        "constructed_complete": sum(c["expected_complete"] for c in data["constructed"]),
        "real_controls": [{"id": c["id"], "complete": c["observed"]["eligible"], "reason": c["observed"]["reason"]}
                          for c in controls[-2:]],
        "affected_tests": counts, "final_service_comparison": read(comparison / "service/summary.json"),
        "synthetic_service_controls": actual, "constructed_native_unsent": captured,
        "fresh_real_control_pages": list(fresh_pages.values()), "corpus_PDF_hashes": len(pdfs), "runtime_drift": drift,
        "new_app_modules": sorted(new), "real_model_calls": 0, "real_oauth_calls": 0, "new_slots": 0,
        "new_DB_preparation": False, "independent_scientific_accuracy": None,
        "limitations": ["Strict explicit marker only, constructed complete cases, no new natural complete assembly",
            "Lin Abstract lacks explicit shared label: unresolved; Methods/aliases bridge not implemented",
            "Old five/76/native unchanged; no measured gain on them",
            "No real model/OAuth/DB preparation/browser/PDF visual/full suite/cache-ORM/concurrency/deployment acceptance"]}
    paths = [*files.ROOT.joinpath("app").rglob("*.py"), Path(__file__), PROTOCOL,
        files.ROOT / "scripts/source_role_assembly_20261109.py", files.ROOT / "scripts/source_role_assembly_controls_20261109.py",
        files.ROOT / "scripts/test_source_role_assembly_20261109.py", files.ROOT / "tests/unit/test_source_role_assembly.py",
        BASE / "controls_v01.json", BASE / "freeze_v01/manifest.json", comparison / "manifest.json", junit,
        junit.with_suffix(".scope.json"), *pdfs]
    bindings = files.bindings(paths)
    prior = read(files.ROOT / "output/natural_source_grammar_20261109/review_v02/report.json")
    report = {"summary": summary, "cases": copy.deepcopy(prior["cases"]), "articles": articles,
              "regressions": summary["final_service_comparison"]["regressions"], "controls": controls, "bindings": bindings}
    document = render(report).replace("Сохранение запрошенного контекста в runtime", "Пункт 4: сборка ролей по явному label")
    note = ("<p><strong>Полные сборки здесь искусственные. Реальный Lin остаётся unresolved: общий article_id "
            "не заменяет явную связь электролита. Прежние пять запросов не изменились.</strong></p>")
    document = document.replace("<table>", note + "<table>", 1)
    extra = "<h2>Source-role controls</h2>"
    for item in controls:
        extra += detail(item["id"] + " — " + ("complete" if item["observed"]["eligible"] else "unresolved"), item)
    extra += detail("Синтетические actual service controls, не ответы реальной модели", actual)
    extra += detail("Текст UI с точными маркерами", display)
    extra += detail("Actual decoded native records для constructed случая", rows)
    document = document.replace("<h2>TAC:", extra + "<h2>TAC:")
    qa = check_html(document, article_count=len(articles), case_count=5)
    files.verify(bindings)
    files.write(output / "report.json", report)
    files.write(output / "qa.json", qa)
    files.save(output / "review.html", document.encode())
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--comparison", required=True, type=Path)
    parser.add_argument("--junit", required=True, type=Path)
    args = parser.parse_args()
    policy = files.NetworkPolicy()
    sys.addaudithook(policy)
    summary = run(args.output, args.comparison, args.junit)
    if policy.denied:
        raise ValueError("External network attempted")
    files.write(args.output / "network.json", {"denials": policy.denied})
    files.manifest(args.output)
    print(json.dumps({k: v for k, v in summary.items() if k not in {"final_service_comparison", "synthetic_service_controls"}}), flush=True)


if __name__ == "__main__":
    main()
