"""Source/native checks and static review; new texts are constructed controls."""

from __future__ import annotations

import argparse
import copy
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import fitz

from app.generation.answer_facts import prepare, prompt_records, selection_records, verify_raw_binding
from app.generation.answer_fidelity import prepare as fidelity
from app.generation.providers import Evidence
from scripts import gigachat_answer_smoke as files
from scripts.benchmark_retrieval_capture_20261105 import read
from scripts.check_answer_fidelity_20261105 import native
from scripts.check_requested_context_runtime_20261105 import render
from scripts.reference_quote_runtime_checks_20261105 import INTAKE
from scripts.review_benchmark_retrieval_repair_20261105 import check_html, detail
from scripts.source_paraphrases_20261109 import BASE, PREVIOUS, ROOT


def run(output: Path, comparison: Path, junit: Path) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    files.verify_manifest(BASE / "freeze_v01")
    files.verify_manifest(comparison)
    summary = read(comparison / "summary.json")
    runtime = read(BASE / "freeze_v01/bindings.json")
    drift = []
    for name, digest in runtime.items():
        path = Path(name)
        if path.is_relative_to(ROOT / "app") and files.sha(path.read_bytes()) != digest:
            snapshot = BASE / "freeze_v01/source_snapshot" / path.relative_to(ROOT)
            if files.sha(snapshot.read_bytes()) != digest:
                raise ValueError("Changed runtime has no bound original snapshot")
            drift.append({"path": name, "before": digest, "after": files.sha(path.read_bytes()), "snapshot": str(snapshot)})
    if {Path(d["path"]).relative_to(ROOT).as_posix() for d in drift} != {
            "app/generation/answer_fidelity.py", "app/generation/fact_recipes.py"}:
        raise ValueError("Unexpected existing runtime drift")
    new_modules = {str(p.resolve()) for p in ROOT.joinpath("app").rglob("*.py")} - set(runtime)
    if new_modules != {str(ROOT / "app/generation/source_paraphrases.py")}:
        raise ValueError("Unexpected new runtime modules")
    controls = read(BASE / "controls_v02.json")
    settings = files.configure()
    results, natives = [], []
    for case in controls:
        sources = [Evidence(**e) for e in case["sources"]]
        contract = fidelity(case["question"], sources)
        bundle = prepare(case["question"], sources, None, contract, answer_language="ru")
        eligible = bool(contract and contract.eligible and bundle and bundle.eligible)
        if eligible != case["expected_eligible"]:
            raise ValueError("Constructed control outcome differs: " + case["id"])
        value = {k: v for k, v in case.items() if k != "sources"}
        value.update(eligible=eligible, contract=contract.metadata(), facts=bundle.metadata(),
                     source_texts=[e.text for e in sources])
        results.append(value)
        if eligible and not case["id"].endswith(":original"):
            records = selection_records(bundle.evidence)
            for derived in bundle.evidence:
                raw = next(e for e in bundle.display if e.citation_id == derived.citation_id)
                verify_raw_binding(derived.text, raw.text, article_id=raw.article_id, chunk_id=raw.chunk_id,
                                   citation_id=raw.citation_id, page_start=raw.page_start, page_end=raw.page_end)
            label = case["id"].replace(":", "_")
            trace = {"retrieval": {"query": case["question"]}, "evidence": [vars(e) for e in bundle.evidence]}
            captured = native(label, trace, settings, output)
            body = read(output / f"{label}_native_unsent.json")
            user = body["messages"][-1]["content"]
            decoded = json.loads(user.split("\nSource-bound records:\n", 1)[1])
            if decoded != prompt_records(bundle.evidence):
                raise ValueError("Actual decoded native fields differ from raw-source facts")
            for record in decoded:
                parent = next(e for e in sources if e.citation_id == record["citation_id"])
                for fact in record["source_bound_facts"]:
                    if fact["source_quote"] not in parent.text:
                        raise ValueError("Actual native quote not present in constructed source")
            natives.append({"id": case["id"], **captured, "fact_ids": list(records),
                            "kind": "constructed_fact_bundle_not_new_production_retrieval_or_model_output"})
    tree = ET.parse(junit).getroot()
    suites = [tree] if tree.tag == "testsuite" else list(tree.iter("testsuite"))
    counts = {k: sum(int(s.get(k, 0)) for s in suites) for k in ("tests", "failures", "errors", "skipped")}
    scope = read(junit.with_suffix(".scope.json"))
    if counts["failures"] or counts["errors"] or scope["exit_code"] or scope["external_network_denials"]:
        raise ValueError("Affected tests failed or external network attempted")
    prior = read(PREVIOUS / "report.json")
    pdfs = []
    for article in prior["articles"].values():
        path = Path(article["original_pdf_path"])
        if files.sha(path.read_bytes()) != article["original_pdf_sha256"]:
            raise ValueError("Original PDF hash changed")
        pdfs.append(path)
    gold = read(INTAKE / "report.json")
    fresh_pages, fresh_spans = 0, 0
    for page in gold["source_pages"]:
        case = next(c for c in gold["cases"] if c["id"] == page["case_id"])
        with fitz.open(case["source_pdf_path_verbatim"]) as pdf:
            raw = pdf[page["pdf_page"] - 1].get_text()
        if files.sha(raw.encode()) != page["sha256"]:
            raise ValueError("Fresh reference page changed")
        fresh_pages += 1
        spans = [q["span"] for q in case["quotes"] if q["span"] and q["pdf_page"] == page["pdf_page"]]
        spans += [n["raw_span"] for n in gold["source_notes"] if n["case_id"] == case["id"] and n["pdf_page"] == page["pdf_page"]]
        for span in spans:
            if raw[span["start"]:span["end"]] != span["text"]:
                raise ValueError("Fresh reference span changed")
            fresh_spans += 1
    bindings = files.bindings([*ROOT.joinpath("app").rglob("*.py"), Path(__file__),
        ROOT / "scripts/source_paraphrases_20261109.py", ROOT / "scripts/source_paraphrase_controls_20261109.py",
        ROOT / "scripts/test_source_paraphrases_20261109.py", ROOT / "tests/unit/test_source_paraphrases.py",
        ROOT / "docs/records/source_paraphrases_protocol_2026-11-09_v0.1.md",
        ROOT / "docs/records/source_paraphrases_amendment_2026-11-09_v0.2.md",
        BASE / "controls_v02.json", comparison / "manifest.json", junit, junit.with_suffix(".scope.json"),
        INTAKE / "report.json", *pdfs])
    summary.update(affected_tests=counts, source_controls=len(results),
        runtime_drift=drift, new_runtime_modules=sorted(new_modules),
        real_original_controls=sum(c["id"].endswith(":original") for c in controls),
        constructed_positive_controls=sum(c["expected_eligible"] and not c["id"].endswith(":original") for c in controls),
        constructed_negative_controls=sum(not c["expected_eligible"] for c in controls),
        new_unsent_native_controls=natives, fresh_pdf_hashes=len(pdfs), fresh_reference_pages=fresh_pages,
        fresh_reference_spans=fresh_spans, external_network_denials=[],
        limitations=["Three finite source roles; artificial paraphrases of exposed examples, not independent scientific gold",
                     "No change/gain on original five questions; 76 old cases do not activate the new grammar",
                     "No real model/OAuth/slots or new DB preparation; original native bodies unchanged",
                     "No browser/PDF visual/full-suite/cache-ORM/concurrency/deployment acceptance"])
    report = {"summary": summary, "articles": prior["articles"], "regressions": summary["regressions"],
              "cases": [], "controls": results, "bindings": bindings}
    for original in prior["cases"]:
        cid = original["id"]
        case = copy.deepcopy(original)
        case["baseline"] = copy.deepcopy(original["repaired"])
        case["repaired"] = copy.deepcopy(original["repaired"])
        for arm, folder in (("baseline", BASE / "freeze_v01"), ("repaired", comparison)):
            trace = read(folder / f"{cid}_current.json")["trace"]
            case[arm]["full_trace_identical"] = True
            case[arm]["source_paraphrases"] = trace["metadata"].get("answer_fidelity", {}).get("source_paraphrases")
        report["cases"].append(case)
    document = render(report).replace("Сохранение запрошенного контекста в runtime", "Пункт 4: конечные перефразировки источника")
    document = document.replace("Офлайн-сравнение реального service на замороженных",
                                "Офлайн-сравнение действительного service на замороженных")
    extra = "<h2>Искусственные перефразировки и отрицательные controls</h2><p>Исходные цитаты реальны; изменённые тексты искусственные.</p>"
    for value in results:
        extra += detail(value["id"] + " — " + ("полный fact bundle" if value["eligible"] else "unresolved"), value)
    document = document.replace("<h2>TAC:", extra + "<h2>TAC:")
    qa = check_html(document, article_count=len(report["articles"]), case_count=5)
    files.verify(bindings)
    files.write(output / "report.json", report)
    files.write(output / "qa.json", qa)
    files.save(output / "review.html", document.encode())
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--comparison", type=Path, required=True)
    parser.add_argument("--junit", type=Path, required=True)
    args = parser.parse_args()
    policy = files.NetworkPolicy()
    sys.addaudithook(policy)
    summary = run(args.output, args.comparison, args.junit)
    if policy.denied:
        raise ValueError("Unexpected external network attempt")
    files.write(args.output / "network.json", {"external_network_denials": policy.denied})
    files.manifest(args.output)
    compact = {k: v for k, v in summary.items() if k not in {"regressions", "native_unsent", "new_unsent_native_controls"}}
    print(json.dumps(compact), flush=True)


if __name__ == "__main__":
    main()
