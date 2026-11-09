"""Offline real-output comparison after the new five-case allowance is closed."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from unittest.mock import patch

from app.generation.providers import Evidence, GeneratedClaim
from app.generation.reference_quotes import resolve_selections, selection_records
from scripts import gigachat_answer_smoke as files
from scripts import review_user_benchmark_live_20261104 as presentation
from scripts import run_user_benchmark_retest_20261105 as live
from scripts.ascii_quote_selection_checks_20261105 import evaluated_evidence
from scripts.review_benchmark_retrieval_repair_20261105 import presence

ROOT = files.ROOT


def read(path):
    return json.loads(path.read_bytes())


def snapshot_scope():
    contracts = live.preparations()
    live.validate_approval(read(live.APPROVAL), {cid: c["request_sha256"] for cid, c in contracts.items()})
    closed = read(live.BASE / "scope_close_v01.json")
    if closed["remaining_allowance"] != 0 or not closed["all_older_budgets_remain_closed"]:
        raise ValueError("Review requires closed allowance")
    cases, articles, folders = [], {}, {}
    bindings = files.bindings([Path(__file__), Path(live.__file__), live.APPROVAL, live.SCOPE,
                               live.TESTS, live.BASE / "scope_close_v01.json"])
    for cid, contract in contracts.items():
        folder = live.BASE / cid / "authorized_inputs"
        files.verify_manifest(folder)
        files.verify(read(folder / "contract.json")["input_bindings"])
        folders[cid] = folder
        cases.append({"case": contract["case"], "contract": contract, "trace": read(folder / "trace.json"),
                      "sources": read(folder / "sources.json")})
        for article in read(folder / "articles.json"):
            articles[article["article_id"]] = article
        bindings.update(contract["input_bindings"])
        bindings.update(files.bindings(list(folder.iterdir())))
        slot = files.LEDGER / contract["request_sha256"]
        closed_slot = slot / "scope_closed_retest_20261105_v01.json"
        if read(closed_slot)["resend_authorized"]:
            raise ValueError("Unexpected resend permission")
        bindings.update(files.bindings([closed_slot]))
    return {"bindings": bindings, "cases": cases, "articles": list(articles.values())}, folders


def run(output, assessment):
    original_render = presentation.render

    def render(report):
        corpus_path = ROOT / "output/benchmark_retrieval_repair_20261105/capture_v02/Q01/corpus.json"
        corpus = read(corpus_path)
        intake = read(presentation.INTAKE / "report.json")
        report["bindings"].update(files.bindings([corpus_path]))
        comparison = ("<h2>Предыдущие и новые реальные результаты</h2><div class='scroll'><table>"
                      "<tr><th>Вопрос</th><th>4 ноября</th><th>До ID, 5 ноября</th><th>Новый тест</th></tr>")
        for row in report["cases"]:
            cid = row["id"]
            previous = ROOT / f"output/user_benchmark_live_20261104/{cid}/live"
            files.verify_manifest(previous)
            prior_api = read(previous / "api_response.json")
            row["previous_20261104_api_response"] = prior_api
            report["bindings"].update(files.bindings([previous / "manifest.json", previous / "api_response.json"]))
            pre_id = None
            if cid in {"Q01", "Q05"}:
                previous_id = ROOT / f"output/reference_quote_live_20261105/{cid}/live"
                files.verify_manifest(previous_id)
                pre_id = read(previous_id / "api_response.json")
                row["previous_pre_id_api_response"] = pre_id
                report["bindings"].update(files.bindings([previous_id / "manifest.json", previous_id / "api_response.json"]))
            comparison += "<tr><td>" + cid + "</td>"
            for api in (prior_api, pre_id, row["api_response"]):
                comparison += "<td>" + presentation.pre(presentation.program_text(api)) + "</td>"
            comparison += "</tr>"
            evidence = [Evidence(**e) for e in row["prepared"]["trace"]["evidence"]]
            records = selection_records(evidence)
            if records and row["api_response"]["body"].get("status") == "answered":
                native_content = json.loads(row["native_response"]["choices"][0]["message"]["content"])
                claims = resolve_selections([GeneratedClaim(**c) for c in native_content["claims"]], evidence)
                if [{"text": c.text, "citation_ids": c.citation_ids} for c in claims] != row["api_response"]["body"]["claims"]:
                    raise ValueError("Accepted public source text differs from exact server ID resolution")
                row["ascii_id_resolution_check"] = {"native_claims": native_content["claims"],
                                                    "exact_server_quote_substitution": True}
            raw = evaluated_evidence(row["prepared"]["trace"], corpus)
            target = next(a for a in report["articles"] if Path(a["original_pdf_path"]).resolve()
                          == Path(row["reference"]["source_pdf_path_verbatim"]).resolve())
            mapped = next(c for c in intake["cases"] if c["id"] == cid)
            row["reference_source_presence"] = presence(raw, target["article_id"],
                sorted({q["pdf_page"] for q in mapped["quotes"]}), mapped["quotes"])
        comparison += "</table></div>"
        report["summary"].update({"successful_api_answers": sum(
            r["api_response"]["http_status"] == 200 and r["api_response"]["body"].get("status") == "answered"
            for r in report["cases"]), "remaining_allowance": 0, "new_scope": live.VERSION,
            "returned_models": [r["result"].get("returned_model") for r in report["cases"]],
            "scope_close": read(live.BASE / "scope_close_v01.json"), "browser_execution": "untested"})
        html = original_render(report).replace("Benchmark v1.0 · Q01–Q05 · 4 ноября 2026",
                    "Benchmark v1.0 · Q01–Q05 · новый тест 5 ноября 2026")
        return html.replace("<p><label>Поиск по таблицам", comparison + "<p><label>Поиск по таблицам")

    with patch.object(presentation, "live", live), patch.object(live, "read_scope", snapshot_scope, create=True), \
            patch.object(presentation, "render", render):
        return presentation.run(output, assessment)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--assessment", type=Path, required=True)
    args = parser.parse_args()
    policy = files.NetworkPolicy()
    sys.addaudithook(policy)
    result = run(args.output, args.assessment)
    if policy.denied:
        raise ValueError("Unexpected offline network access")
    print(json.dumps(result, ensure_ascii=True, indent=2), flush=True)


if __name__ == "__main__":
    main()
