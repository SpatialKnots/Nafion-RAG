"""Source/lineage verification and clearly labelled synthetic review examples."""

from __future__ import annotations

import argparse
import json
from html import escape
from pathlib import Path
from typing import Any

import fitz

from scripts import gigachat_answer_smoke as files
from scripts.benchmark_retrieval_capture_20261105 import read
from scripts.check_requested_context_runtime_20261105 import render
from scripts.reference_quote_runtime_checks_20261105 import BASE, INTAKE, ROOT, raw_evidence
from scripts.review_benchmark_retrieval_repair_20261105 import check_html, detail, presence


def mypy_name_only_binding(name: str, digest: str) -> dict[str, Any] | None:
    if Path(name).resolve() != (ROOT / "app/generation/reference_quotes.py").resolve():
        return None
    snapshot = BASE / "review_v02/source_snapshot/app/generation/reference_quotes.py"
    original = snapshot.read_text(encoding="utf-8")
    renamed = original.replace("words = set(", "author_words = set(", 1).replace(
        "<= words for name in named_authors", "<= author_words for name in named_authors", 1)
    if files.sha(snapshot.read_bytes()) != digest or Path(name).read_text(encoding="utf-8") != renamed:
        return None
    return {"path": name, "original_sha256": digest, "current_sha256": files.sha(Path(name).read_bytes()),
            "snapshot": str(snapshot), "change": "local_front_matter_variable_rename_only_for_mypy"}


def verify(output: Path) -> dict[str, Any]:
    first, final = BASE / "review_v01", BASE / "review_v02"
    for folder in (first, final, BASE / "freeze_v01", INTAKE):
        files.verify_manifest(folder)
    report = read(final / "report.json")
    type_drifts = []
    for name, digest in report["bindings"].items():
        if files.sha(Path(name).read_bytes()) != digest:
            mapped = mypy_name_only_binding(name, digest)
            if mapped is None:
                raise ValueError("Unexpected report binding drift")
            type_drifts.append(mapped)
    fresh_checks, stdout_drifts = [], []
    for case_id in ("Q01", "Q05"):
        folder = BASE / "fresh_v01" / case_id
        files.verify_manifest(folder)
        contract = read(folder / "contract.json")
        for name, digest in contract["input_bindings"].items():
            if files.sha(Path(name).read_bytes()) == digest:
                continue
            if mypy_name_only_binding(name, digest) is not None:
                continue
            snapshot = BASE / "capture_driver_before_stdout_fix_v01.py"
            current = Path(name).read_text(encoding="utf-8")
            if (case_id != "Q01" or Path(name).name != "capture_reference_quote_runtime_20261105.py"
                    or files.sha(snapshot.read_bytes()) != digest
                    or snapshot.read_text(encoding="utf-8").replace("ensure_ascii=False", "ensure_ascii=True") != current):
                raise ValueError("Unexpected fresh capture input drift")
            stdout_drifts.append({"path": name, "original_sha256": digest, "snapshot": str(snapshot),
                                   "change": "stdout_json_ensure_ascii_only_after_complete_Q01_capture"})
        actual = read(folder / "trace.json")
        predicted = read(final / f"{case_id}_repaired.json")["trace"]
        if actual != predicted:
            raise ValueError("Actual fresh service trace differs from frozen-channel repair")
        bodies = [(first / f"{case_id}_native_unsent.json").read_bytes(),
                  (final / f"{case_id}_native_unsent.json").read_bytes(), (folder / "request.json").read_bytes()]
        if len(set(bodies)) != 1 or files.sha(bodies[0]) != contract["request_sha256"]:
            raise ValueError("Native bytes differ across v0.1/v0.2/fresh preparation")
        if (contract["transaction_read_only"], contract["transaction_end"], contract["model_calls"], contract["oauth_calls"],
                contract["new_slots"], contract["network_denials"], contract["gold_read_denials"],
                contract["source_registry_diagnostics"]) != ("on", "rollback", 0, 0, 0, [], [], []):
            raise ValueError("Fresh preparation exceeded read-only question-only scope")
        fresh_checks.append({"case_id": case_id, "full_trace_identical_to_offline": True,
                             "native_bytes_identical_v01_v02_fresh": True, "request_bytes": len(bodies[0]),
                             "request_sha256": contract["request_sha256"], "simulated_oauth_boundaries": 1,
                             "captured_native_boundaries": 1, "real_model_calls": 0, "real_oauth_calls": 0})
    # v0.1 is preserved with its exact original source snapshot, not rebound to
    # the strengthened v0.2 author guard or changed control fixtures.
    old_report = read(first / "report.json")
    historical_drift = []
    for name, digest in old_report["bindings"].items():
        if files.sha(Path(name).read_bytes()) != digest:
            snapshot = first / "source_snapshot" / Path(name).relative_to(ROOT)
            if files.sha(snapshot.read_bytes()) != digest:
                raise ValueError("Unmapped v0.1 historical drift")
            historical_drift.append({"path": name, "snapshot": str(snapshot), "sha256": digest})
    gold = read(INTAKE / "report.json")
    corpus = read(ROOT / "output/benchmark_retrieval_repair_20261105/capture_v02/Q01/corpus.json")
    raw_pages, raw_spans, notes, checked_records = 0, 0, [], 0
    for case in gold["cases"]:
        selected = next(c for c in report["cases"] if c["id"] == case["id"])
        target = next(a for a in report["articles"].values() if Path(a["original_pdf_path"]).resolve()
                      == Path(case["source_pdf_path_verbatim"]).resolve())
        trace = read(final / f'{case["id"]}_repaired.json')["trace"]
        raw = raw_evidence(trace, corpus)
        checked_records += len(raw)
        if raw != selected["repaired"]["evidence"]:
            raise ValueError("Rendered evidence differs from actual raw quotation selection")
        with fitz.open(target["original_pdf_path"]) as document:
            for page in (p for p in gold["source_pages"] if p["case_id"] == case["id"]):
                text = document[page["pdf_page"] - 1].get_text()
                if files.sha(text.encode()) != page["sha256"]:
                    raise ValueError("Original reference page changed")
                raw_pages += 1
                for quote in case["quotes"]:
                    if quote["span"] is not None and quote["pdf_page"] == page["pdf_page"]:
                        span = quote["span"]
                        if text[span["start"]:span["end"]] != span["text"]:
                            raise ValueError("Source quote offset changed")
                        raw_spans += 1
                for note in gold["source_notes"]:
                    if note["case_id"] == case["id"] and note["pdf_page"] == page["pdf_page"]:
                        span = note["raw_span"]
                        if text[span["start"]:span["end"]] != span["text"]:
                            raise ValueError("Supplementary source span changed")
                        raw_spans += 1
                        notes.append({"case_id": case["id"], "page": page["pdf_page"], "span": span,
                            "origin": note["origin"], "retained": presence(raw, target["article_id"], [page["pdf_page"]],
                                [{"pdf_page": page["pdf_page"], "span": span}])["mapped_quotes_retained"] == 1})
    result = {"version": "reference_quote_runtime_verification_v0.2", "fresh_checks": fresh_checks,
        "report_bindings_verified": len(report["bindings"]), "fresh_pages_verified": raw_pages, "fresh_raw_spans_verified": raw_spans,
        "selected_evidence_records_verified": checked_records, "source_note_retention": notes,
        "stdout_only_driver_drift": stdout_drifts, "mypy_name_only_drift": type_drifts, "historical_v01_drift": historical_drift,
        "real_model_calls": 0, "real_oauth_calls": 0, "slots": 0}
    output.mkdir(parents=True, exist_ok=False)
    paths = [Path(__file__), ROOT / "scripts/capture_reference_quote_runtime_20261105.py",
             ROOT / "app/generation/reference_quotes.py",
             ROOT / "tests/unit/test_reference_quote_service.py", final / "manifest.json",
             BASE / "fresh_v01/Q01/manifest.json", BASE / "fresh_v01/Q05/manifest.json"]
    report["summary"]["verification"] = {k: v for k, v in result.items() if k not in {"source_note_retention", "historical_v01_drift"}}
    html = render(report).replace("Сохранение запрошенного контекста в runtime", "Автор/год: отбор источников и точные цитаты")
    examples = ("<h2>Синтетическая проверка выбора цитат</h2><p><strong>Это не ответы реальной модели.</strong> "
                "Детерминированный тест выбрал все разрешённые цитаты через настоящий service. "
                "Native requests сохранены без отправки; реальных API/OAuth вызовов нет.</p>")
    for case_id in ("Q01", "Q05"):
        answer = read(final / f"{case_id}_SYNTHETIC_selection.json")
        examples += "<h3>" + case_id + " — SYNTHETIC</h3><blockquote><pre>" + escape(answer["answer"]) + "</pre></blockquote>"
        examples += detail("Синтетический API output, не provider response", answer)
    marker = "<h2>TAC: все работы снимка</h2>"
    if marker not in html:
        raise ValueError("Review insertion point changed")
    html = html.replace(marker, examples + marker)
    qa = check_html(html, article_count=len(report["articles"]), case_count=5)
    files.write(output / "verification.json", result)
    files.write(output / "report.json", report)
    files.save(output / "review.html", html.encode())
    files.write(output / "qa.json", qa)
    files.write(output / "current_bindings.json", files.bindings(paths))
    files.manifest(output)
    return {k: v for k, v in result.items() if k not in {"source_note_retention", "historical_v01_drift"}}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.output), ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
