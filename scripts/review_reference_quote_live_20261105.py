"""Offline review of the two real attempts; never repair or resend model output."""

from __future__ import annotations

import argparse
import difflib
import json
import re
from pathlib import Path
from typing import Any

import fitz

from app.generation.lithiation_overview import allowed_claims
from app.generation.providers import Evidence
from scripts import gigachat_answer_smoke as files
from scripts import review_user_benchmark_live_20261104 as presentation
from scripts import run_reference_quote_live_20261105 as live
from scripts.reference_quote_runtime_checks_20261105 import raw_evidence
from scripts.review_benchmark_retrieval_repair_20261105 import presence

ROOT = files.ROOT
INTAKE = ROOT / "output/user_benchmark_20261103/review_v01"


def character_comparison(expected: dict[str, list[str]], claims: list[dict[str, Any]]) -> dict[str, Any]:
    comparisons = []
    for claim in claims:
        text, citations = claim["text"], claim["citation_ids"]
        pool = [(citation, allowed) for citation, texts in expected.items() for allowed in texts]
        citation, allowed = max(pool, key=lambda pair: difflib.SequenceMatcher(None, pair[1], text, autojunk=False).ratio())
        changes = []
        for tag, start, end, actual_start, actual_end in difflib.SequenceMatcher(None, allowed, text, autojunk=False).get_opcodes():
            if tag != "equal":
                changes.append({"operation": tag, "expected_offset": [start, end], "actual_offset": [actual_start, actual_end],
                    "expected": allowed[start:end], "actual": text[actual_start:actual_end],
                    "expected_codepoints": [f"U+{ord(c):04X}" for c in allowed[start:end]],
                    "actual_codepoints": [f"U+{ord(c):04X}" for c in text[actual_start:actual_end]]})
        comparisons.append({"actual_claim": claim, "closest_allowed_citation": citation, "allowed_claim": allowed,
            "exact_text": text == allowed, "exact_citation": citations == [citation], "character_changes": changes,
            "digit_surface_sequences_equal": re.findall(r"\d+(?:[.,]\d+)*", text) == re.findall(r"\d+(?:[.,]\d+)*", allowed),
            "scientific_value_or_unit_ownership_validated": False})
    return {"origin": "assistant_posthoc_character_diagnostic_not_scientific_score", "claims": comparisons,
            "exact_claims": sum(c["exact_text"] and c["exact_citation"] for c in comparisons), "claim_count": len(comparisons),
            "all_required_claims_exact": {(c["citation_ids"][0], c["text"]) for c in claims if len(c["citation_ids"]) == 1}
                                       == {(citation, text) for citation, texts in expected.items() for text in texts}}


def review(output: Path) -> dict[str, Any]:
    live.validate_approval(live.read(live.APPROVAL))
    closed = live.read(live.BASE / "scope_close_v01.json")
    if (closed["total_model_attempts"], closed["total_oauth_attempts"], closed["remaining_allowance"]) != (2, 2, 0):
        raise ValueError("Expected two completed attempts with closed allowance")
    # Only this offline process reads references, after all predictions are durable.
    files.verify_manifest(INTAKE)
    gold = live.read(INTAKE / "report.json")
    corpus = live.read(ROOT / "output/benchmark_retrieval_repair_20261105/capture_v02/Q01/corpus.json")
    output.mkdir(parents=True, exist_ok=False)
    rows, articles, pdfs, pages, diagnostics = [], {}, {}, {}, []
    totals = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    bindings = files.bindings([Path(__file__), live.APPROVAL, live.SCOPE, live.BASE / "scope_close_v01.json",
                              INTAKE / "manifest.json", INTAKE / "report.json"])
    for case_id in live.IDS:
        approved, actual = live.BASE / case_id / "authorized_inputs", live.BASE / case_id / "live"
        files.verify_manifest(approved)
        files.verify_manifest(actual)
        contract = live.read(approved / "contract.json")
        files.verify(contract["input_bindings"])
        trace, sources = live.read(actual / "trace.json"), live.read(actual / "sources.json")
        if trace != live.read(approved / "trace.json") or sources != live.read(approved / "sources.json"):
            raise ValueError("Actual source preparation drift")
        result, api, native = [live.read(actual / name) for name in ("result.json", "api_response.json", "response.bin")]
        if (result["model_attempts"], result["oauth_attempts"], result["automatic_retries"], result["fallbacks"]) != (1, 1, 0, 0):
            raise ValueError("Observed budget exceeds single attempt")
        if (actual / "request.json").read_bytes() != (approved / "request.json").read_bytes():
            raise ValueError("Actual native body differs")
        slot = files.LEDGER / live.REQUESTS[case_id]
        if (slot / "result.json").read_bytes() != (actual / "result.json").read_bytes():
            raise ValueError("Global slot result differs")
        if live.read(slot / "scope_closed_20261105_v01.json")["resend_authorized"]:
            raise ValueError("Closed slot unexpectedly permits resend")
        for key in totals:
            totals[key] += result["usage"][key]
        expected = allowed_claims([Evidence(**e) for e in trace["evidence"]])
        content = json.loads(native["choices"][0]["message"]["content"])
        diff = character_comparison(expected, content["claims"])
        diff["id"] = case_id
        diff["finish_reason"] = native["choices"][0]["finish_reason"]
        diff["native_answerable"] = content["answerable"]
        diagnostics.append(diff)
        replay = presentation.offline_replay(approved, actual)
        reference = next(c for c in gold["cases"] if c["id"] == case_id)
        target_pages = [p["pdf_page"] for p in gold["source_pages"] if p["case_id"] == case_id]
        for article in live.read(actual / "articles.json"):
            articles[article["article_id"]] = article
        target_id = trace["evidence"][0]["article_id"]
        source_presence = presence(raw_evidence(trace, corpus), target_id, target_pages, reference["quotes"])
        for page in sources["pages"].values():
            pdf = Path(page["original_pdf_path"])
            if files.sha(pdf.read_bytes()) != page["original_pdf_sha256"]:
                raise ValueError("Original PDF changed")
            pdfs[str(pdf)] = page["original_pdf_sha256"]
            with fitz.open(page["layer_pdf_path"]) as document:
                raw = document[page["page_number"] - 1].get_text()
            if raw != page["page_text"]:
                raise ValueError("Fresh selected page differs")
            pages[page["region_id"]] = {"page": page["page_number"], "article_id": page["article_id"],
                                        "sha256": files.sha(raw.encode())}
        changes = [change for c in diff["claims"] for change in c["character_changes"]]
        observations = [
            "Провайдер вернул answerable=true и finish_reason=stop, но локальный API отклонил неточное цитирование с HTTP502.",
            f"Точных claims {diff['exact_claims']}/{diff['claim_count']}; все исходные тексты и ошибки сохранены без исправлений.",
            "Сравнение цифр/Unicode ниже — диагностическое сопоставление строк, не независимая научная оценка.",
            "Наличие нужного источника не гарантирует соблюдение моделью длинного строкового enum. Повторов не было.",
        ]
        for change in changes:
            observations.append("Вместо " + repr(change["expected"]) + " (" + ", ".join(change["expected_codepoints"])
                                + ") пришло " + repr(change["actual"]) + " (" + ", ".join(change["actual_codepoints"]) + ").")
        rows.append({"reference": reference, "api_response": api, "native_response": native,
            "prepared": {"trace": trace, "sources": sources}, "result": result,
            "assistant_posthoc_comparison": {"verdict": "Локальный отказ: неточное Unicode-цитирование", "observations": observations,
                           "evidence_checks": diff}, "reference_retrieval_diagnostic": source_presence,
            "offline_replay": replay, "intake_notes": [n for n in gold["source_notes"] if n["case_id"] == case_id]})
        bindings.update(files.bindings([*approved.iterdir(), *actual.iterdir(), slot / "result.json",
                                        slot / "scope_closed_20261105_v01.json"]))
    summary = {"version": "reference_quote_live_review_v0.1", "actual_model_attempts": 2, "actual_oauth_attempts": 2,
        "automatic_retries": 0, "fallbacks": 0, "remaining_allowance": 0, "successful_api_answers": 0,
        "usage_reported": totals, "actual_cost": None, "exact_offline_http_replays": 2, "review_real_model_oauth_db_calls": 0,
        "fresh_selected_pages": len(pages), "pdf_hashes": len(pdfs), "returned_models": [r["result"]["returned_model"] for r in rows],
        "scientific_accuracy": None, "limitations": ["Two exposed development cases, no blind scientific evaluation",
            "Native claims are unaccepted outputs, never presented as successful API answers",
            "Unicode-diagnostic similarity is not semantic entailment", "No browser/new visual PDF/full suite/cache-ORM check"]}
    bindings.update(files.bindings([Path(name) for name in pdfs]))
    files.verify(bindings)
    report = {"summary": summary, "bindings": bindings, "cases": rows, "articles": list(articles.values()),
              "character_diagnostics": diagnostics, "fresh_selected_pages": pages}
    html = presentation.render(report).replace("Benchmark v1.0 · Q01–Q05 · 4 ноября 2026", "Q01/Q05 · две реальные попытки · 5 ноября 2026")
    html = html.replace("У Q04 остаётся замечание «физические / chemical crosslinking elements».", "")
    parser = presentation.Structure()
    parser.feed(html)
    from urllib.parse import unquote, urlparse
    for link in parser.links:
        parsed = urlparse(link)
        path = unquote(parsed.path)
        if re.match(r"^/[A-Za-z]:", path):
            path = path[1:]
        if parsed.scheme != "file" or not Path(path).is_file():
            raise ValueError("Missing or nonlocal review link")
    files.write(output / "report.json", report)
    files.write(output / "character_diagnostics.json", diagnostics)
    files.save(output / "review.html", html.encode())
    files.write(output / "qa.json", {"cases": len(rows), "tac_rows": len(articles), "tac_columns": 8,
                                     "existing_pdf_links": len(parser.links), "browser_execution": "untested"})
    files.manifest(output)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    policy = files.NetworkPolicy()
    import sys
    sys.addaudithook(policy)
    result = review(args.output)
    if policy.denied:
        raise ValueError("Unexpected offline network attempt")
    print(json.dumps(result, ensure_ascii=True, indent=2), flush=True)


if __name__ == "__main__":
    main()
