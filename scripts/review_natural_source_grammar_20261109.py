"""Report natural role gains separately from unchanged production answer inputs."""

from __future__ import annotations

import argparse
import copy
import json
import sys
import xml.etree.ElementTree as ET
from dataclasses import replace
from pathlib import Path

from app.generation import answer_facts, fact_recipes
from app.generation.fact_types import FactPatternError
from app.generation.providers import Evidence, GeneratedClaim
from scripts import gigachat_answer_smoke as files
from scripts.benchmark_retrieval_capture_20261105 import read
from scripts.check_answer_fidelity_20261105 import native
from scripts.check_requested_context_runtime_20261105 import render
from scripts.natural_source_controls_20261109 import build
from scripts.natural_source_grammar_20261109 import BASE, FREEZE, PROTOCOL
from scripts.reference_quote_runtime_checks_20261105 import CORPUS_BASE
from scripts.review_benchmark_retrieval_repair_20261105 import check_html, detail


def run(output: Path, comparison: Path, junit: Path) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    files.verify_manifest(FREEZE)
    files.verify_manifest(comparison)
    data = read(BASE / "controls_v01.json")
    if files.encode(build()) != (BASE / "controls_v01.json").read_bytes():
        raise ValueError("Natural source/controls/fresh PDF registration changed")
    before, after = read(FREEZE / "recipe_audit.json"), read(comparison / "recipe_audit.json")
    changes = []
    for old, new in zip(before["rows"], after["rows"], strict=True):
        if old != new:
            if old["recipe"] != "coulombic" or old["complete"] or not new["complete"]:
                raise ValueError("Unplanned natural recipe change")
            changes.append({"recipe": new["recipe"], "source": new["source"], "rendering": new["rendering"]})
    expected = {c["source"]["chunk_id"] for c in data["natural"] if c["id"].startswith("natural_conclusion")}
    if {c["source"]["chunk_id"] for c in changes} != expected:
        raise ValueError("Natural gains differ from declared development windows")
    runtime = read(FREEZE / "bindings.json")
    drift = []
    for name, digest in runtime.items():
        path = Path(name)
        if path.is_relative_to(files.ROOT / "app") and files.sha(path.read_bytes()) != digest:
            snapshot = FREEZE / "source_snapshot" / path.relative_to(files.ROOT)
            if files.sha(snapshot.read_bytes()) != digest:
                raise ValueError("Changed app source has no exact initial snapshot")
            drift.append({"path": name, "before": digest, "after": files.sha(path.read_bytes()), "snapshot": str(snapshot)})
    if {Path(d["path"]).relative_to(files.ROOT).as_posix() for d in drift} != {
            "app/generation/source_paraphrases.py", "app/generation/fact_types.py",
            "app/generation/fact_recipes.py", "app/generation/answer_facts.py"}:
        raise ValueError("Unexpected runtime drift")
    if {str(p) for p in files.ROOT.joinpath("app").rglob("*.py")} - set(runtime):
        raise ValueError("Unexpected new app modules")
    controls = []
    for case in data["natural"] + data["constructed"]:
        real = "source" in case
        src = Evidence(**case["source"]) if real else replace(Evidence(**data["natural"][1]["source"]), text=case["text"])
        recipe = case["recipe"] if real else "coulombic"
        try:
            value = fact_recipes.RECIPES[recipe](src, {"grade": "Nafion-117", "product": "b1", "comparator": "NCD"}).data()
        except FactPatternError as exc:
            complete, value = False, {"reason": str(exc)}
        else:
            complete = True
        if complete != case["expected_complete"]:
            raise ValueError("Control outcome differs: " + case["id"])
        controls.append({**case, "observed_complete": complete, "observed": value, "real_source": real})
    # Explicit component assembly. This never changes or bypasses production admission.
    abstract = next(c["source"] for c in data["natural"] if c["id"].startswith("natural_legacy"))
    conclusion = data["natural"][1]["source"]
    sources = [Evidence(**{**abstract, "citation_id": "E1"}), Evidence(**{**conclusion, "citation_id": "E2"})]
    records = [answer_facts._record(recipe, source, {}, f"F{i}") for i, (recipe, source) in enumerate(
        [("composition", sources[0]), ("capacity", sources[0]), ("coulombic", sources[1])], 1)]
    selected = [replace(source, source_type=answer_facts.SOURCE_TYPE, text=json.dumps({
        "version": answer_facts.VERSION, "family": "composition_cycling", "language": "ru", "params": {},
        "raw_source": source.text, "records": [r for r in records if r["citation_id"] == source.citation_id]}, ensure_ascii=False))
        for source in sources]
    choices = answer_facts.selection_records(selected)
    question = read(FREEZE / "service/Q01_current.json")["trace"]["retrieval"]["query"]
    captured = native("COMPONENT_NOT_PRODUCTION", {"retrieval": {"query": question}, "evidence": [vars(e) for e in selected]},
                      files.configure(), output)
    body = read(output / "COMPONENT_NOT_PRODUCTION_native_unsent.json")
    decoded = json.loads(body["messages"][-1]["content"].split("Source-bound records:\n", 1)[1])
    if decoded != answer_facts.prompt_records(selected):
        raise ValueError("Actual decoded native differs from component source records")
    for record in decoded:
        parent = next(s for s in sources if s.citation_id == record["citation_id"])
        if not all(f["source_quote"] in parent.text for f in record["source_bound_facts"]):
            raise ValueError("Actual native source quote absent from unchanged raw parent")
    rendered = answer_facts.resolve_selections([GeneratedClaim(k, [r["citation_id"]]) for k, r in choices.items()], selected)
    files.write(output / "component.json", {"scope": "explicit_component_packet_not_production_admission_or_model_output",
        "records": records, "selected_evidence": [vars(e) for e in selected], "decoded_native_records": decoded,
        "synthetic_all_id_selection_server_rendering": [vars(c) for c in rendered]})
    tree = ET.parse(junit).getroot()
    suites = list(tree.iter("testsuite"))
    counts = {k: sum(int(s.get(k, 0)) for s in suites) for k in ("tests", "failures", "errors", "skipped")}
    scope = read(junit.with_suffix(".scope.json"))
    if counts["failures"] or counts["errors"] or scope["exit_code"] or scope["external_network_denials"]:
        raise ValueError("Affected test run failed or attempted external network")
    articles = read(CORPUS_BASE / "Q01/articles.json")
    pdfs = []
    for article in articles.values():
        path = Path(article["original_pdf_path"])
        if files.sha(path.read_bytes()) != article["original_pdf_sha256"]:
            raise ValueError("Corpus PDF changed")
        pdfs.append(path)
    summary = {"natural_recipe_observations": len(after["rows"]), "corpus_chunks": 619, "works": 33,
        "complete_before": sum(r["complete"] for r in before["rows"]),
        "complete_after": sum(r["complete"] for r in after["rows"]), "new_raw_bindings": len(changes),
        "new_unique_raw_passages": len({files.sha(c["rendering"]["facts"][0]["support"]["text"].encode()) for c in changes}),
        "natural_controls": len(data["natural"]), "constructed_controls": len(data["constructed"]),
        "affected_tests": counts, "final_service_comparison": read(comparison / "service/summary.json"),
        "component_native_unsent": captured, "fresh_control_pages": len(data["fresh_pages"]),
        "narrow_CE_exact_fresh_span_observations": sum(bool(s["span_literal_in_fresh_pages"]) for s in data["fresh_spans"][:6]),
        "corpus_PDF_hashes": len(pdfs), "runtime_drift": drift, "real_model_calls": 0, "real_oauth_calls": 0,
        "new_slots": 0, "new_DB_preparation": False, "independent_scientific_accuracy": None,
        "limitations": ["One new unique exposed real CE role, three overlapping chunk bindings, not independent gold",
            "Role extraction only: no new full-family production answer/admission; original five/76/native unchanged",
            "Unlabelled recipe refusals are not automatically false refusals or evidence of scientific absence",
            "No live model/OAuth/DB preparation/browser/PDF visual/full suite/cache-ORM/concurrency/deployment acceptance"]}
    paths = [*files.ROOT.joinpath("app").rglob("*.py"), Path(__file__), PROTOCOL,
        files.ROOT / "scripts/natural_source_grammar_20261109.py", files.ROOT / "scripts/natural_source_controls_20261109.py",
        files.ROOT / "scripts/test_natural_source_grammar_20261109.py", files.ROOT / "tests/unit/test_natural_source_grammar.py",
        BASE / "controls_v01.json", FREEZE / "manifest.json", comparison / "manifest.json", junit,
        junit.with_suffix(".scope.json"), *pdfs]
    bindings = files.bindings(paths)
    prior = read(files.ROOT / "output/source_paraphrases_20261109/review_v01/report.json")
    report = {"summary": summary, "cases": copy.deepcopy(prior["cases"]), "articles": articles,
              "regressions": summary["final_service_comparison"]["regressions"], "controls": controls,
              "recipe_changes": changes, "bindings": bindings}
    document = render(report).replace("Сохранение запрошенного контекста в runtime", "Пункт 4: естественная формулировка CE")
    note = ("<p><strong>Новый результат: один естественный CE passage в трёх перекрывающихся чанках. "
            "Извлечение роли не расширяет допуск полного production-ответа. Источники прежних пяти вопросов неизменны.</strong></p>")
    document = document.replace("<table>", note + "<table>", 1)
    extra = "<h2>Естественные source windows и отдельные искусственные controls</h2>"
    for case in controls:
        extra += detail(case["id"] + " — " + ("role extracted" if case["observed_complete"] else "unresolved"), case)
    extra += detail("Полный pre-edit natural recipe audit: отказы не являются научными labels", before)
    extra += detail("Полный post-edit natural recipe audit", after)
    extra += detail("Fresh PDF registration / raw spans", {k: data[k] for k in ("fresh_pages", "fresh_spans", "source_pdf_bindings")})
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
    compact = {k: v for k, v in summary.items() if k not in {"final_service_comparison", "runtime_drift"}}
    print(json.dumps(compact), flush=True)


if __name__ == "__main__":
    main()
