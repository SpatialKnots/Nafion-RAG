"""Verify fresh unsent requests and immutable offline checks without DB/network."""

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from scripts import gigachat_answer_smoke as files
from scripts.check_answer_fidelity_20261105 import BASE, PREVIOUS, ROOT
from scripts.review_benchmark_retrieval_repair_20261105 import check_html, detail


def read(path):
    return json.loads(path.read_bytes())


def verify(output):
    review = BASE / "review_v03"
    files.verify_manifest(review)
    files.verify_manifest(BASE / "freeze_v01")
    report = read(review / "report.json")
    files.verify(report["bindings"])
    suite = ET.parse(BASE / "tests_affected_v02.xml").getroot()
    if len(list(suite.iter("testcase"))) != 350 or any(list(suite.iter(tag)) for tag in ("failure", "error", "skipped")):
        raise ValueError("Affected tests did not all pass")
    originals = read(BASE / "freeze_v01/inputs.json")["bindings"]
    drifts = {name: {"before": digest, "after": files.sha(Path(name).read_bytes())}
              for name, digest in originals.items() if files.sha(Path(name).read_bytes()) != digest}
    if {Path(name).relative_to(ROOT).as_posix() for name in drifts} != {
            "app/generation/gigachat.py", "app/generation/service.py"}:
        raise ValueError("Unexpected pre-edit runtime drift")
    gold = ROOT / "docs/records/Nafion_RAG_Benchmark_v1.0_original.md"
    if files.sha(gold.read_bytes()) != "8b5450878bf9791635767f800616c38e8f1d9108852563171b8af8d1a3677332":
        raise ValueError("Original gold changed")
    fresh, anchor_count = [], 0
    for cid in ("Q02", "Q04"):
        folder = BASE / "fresh_v02" / cid
        files.verify_manifest(folder)
        contract = read(folder / "contract.json")
        files.verify(contract["input_bindings"])
        if (read(folder / "trace.json") != read(review / f"{cid}_repaired.json")["trace"]
                or (folder / "request.json").read_bytes() != (review / f"{cid}_native_unsent.json").read_bytes()
                or contract["transaction_read_only"] != "on" or contract["transaction_end"] != "rollback"
                or any(contract[k] != 0 for k in ("model_calls", "oauth_calls", "new_slots", "maximum_model_attempts",
                                                 "maximum_oauth_attempts"))
                or contract["network_denials"] or contract["gold_read_denials"] or contract["source_registry_diagnostics"]):
            raise ValueError("Fresh preparation differs from offline/read-only scope")
        if (files.LEDGER / contract["request_sha256"]).exists():
            raise ValueError("New request has an unexpected live slot")
        trace = read(folder / "trace.json")
        for requirement in trace["metadata"]["answer_fidelity"]["requirements"]:
            for anchor in requirement["anchors"]:
                raw = next(e for e in trace["evidence"] if e["citation_id"] == anchor["citation_id"])
                if (raw["article_id"] != anchor["article_id"] or raw["chunk_id"] != anchor["chunk_id"]
                        or files.sha(raw["text"].encode()) != anchor["raw_chunk_sha256"]
                        or raw["text"][anchor["start"]:anchor["end"]] != anchor["text"]):
                    raise ValueError("Fidelity raw anchor binding differs")
                anchor_count += 1
        fresh.append({"case_id": cid, "request_bytes": contract["request_bytes"],
                      "request_sha256": contract["request_sha256"], "full_trace_and_native_identical": True})
    for number in range(1, 6):
        files.verify_manifest(PREVIOUS / f"Q{number:02}/live")
    if read(PREVIOUS / "scope_close_v01.json")["remaining_allowance"] != 0:
        raise ValueError("Historical allowance changed")
    names = sorted(p.name for p in (BASE / "review_v02").glob("Q*.json"))
    if len(names) != 23 or not all((BASE / "review_v02" / name).read_bytes() == (review / name).read_bytes() for name in names):
        raise ValueError("Case output changed after legacy reader-only fix")
    result = {"distinct_tests_passed": 350, "new_tests": 51, "fresh_preparations": fresh,
              "raw_fidelity_anchors_verified": anchor_count, "base_report_bindings": len(report["bindings"]),
              "case_files_identical_after_legacy_adapter_fix": len(names), "pre_edit_runtime_drifts": drifts,
              "new_runtime_module": "app/generation/answer_fidelity.py", "real_model_calls": 0,
              "real_oauth_calls": 0, "new_slots": 0, "all_live_budgets_remain_closed": True}
    output.mkdir(parents=True, exist_ok=False)
    report["summary"]["verification"] = result
    bindings = files.bindings([Path(__file__), review / "manifest.json", BASE / "tests_affected_v02.xml", gold,
                               *[BASE / f"fresh_v02/{cid}/manifest.json" for cid in ("Q02", "Q04")]])
    files.write(output / "verification.json", result)
    files.write(output / "current_bindings.json", bindings)
    files.write(output / "report.json", report)
    html = (review / "review.html").read_text(encoding="utf-8")
    html = html.replace("Context retention не проверяет научное владение величинами.",
                        "Проверка покрытия не гарантирует полной научной корректности.")
    html = html.replace("<h2>TAC: все работы снимка</h2>", detail("Fresh read-only проверка, новые запросы не отправлены", result)
                        + "<h2>TAC: все работы снимка</h2>")
    files.save(output / "review.html", html.encode())
    files.write(output / "qa.json", check_html(html, article_count=len(report["articles"]), case_count=5))
    files.manifest(output)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    policy = files.NetworkPolicy()
    sys.addaudithook(policy)
    result = verify(args.output)
    if policy.denied:
        raise ValueError("Unexpected network attempt")
    print(json.dumps(result, ensure_ascii=True, indent=2), flush=True)


if __name__ == "__main__":
    main()
