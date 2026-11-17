"""Verify actual closed rewriting results and read-only answer preparation."""

from __future__ import annotations

import html
import json
import re
import sys
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse

import fitz

from scripts import fan_doi_besenhard_rewriting_20261113 as r
from scripts import fan_doi_besenhard_rewriting_prepare_20261113 as preparation

f = r.f


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.links += [v for k, v in attrs if k == "href"]


def run():
    cases = r.cases()
    preparation.verify()
    f.verify_manifest(r.BASE / "rewrite_closed_v01")
    f.verify(r.read(r.BASE / "rewrite_closed_v01/bindings.json"))
    closure = r.read(r.BASE / "rewrite_closed_v01.json")
    r.baseline.require(closure["remaining_allowance"] == 0 and len(closure["cases"]) == 30, "Rewrite scope not closed")
    r.baseline.require(r.read(r.BASE / "prepare_batch_v01.json")["finished_all"], "Preparation batch incomplete")
    contexts = r.read(r.FREEZE / "title_contexts.json")["contexts"]
    decisions = r.read(r.BASE / "meaning_review_v01.json")
    usage = Counter()
    models, finishes, rows, bindings, pages, hashes = set(), Counter(), [], {}, {}, {}
    observed_pages = 0
    for case in cases:
        cid = case["id"]
        rewrite = r.BASE / "rewrites" / cid
        f.verify_manifest(rewrite)
        result = r.read(rewrite / "result.json")
        request = (rewrite / "request.json").read_bytes()
        expected = r.FREEZE / "rewrites" / cid / "request.json"
        r.baseline.require(request == expected.read_bytes(), "Dispatched rewrite differs from frozen native")
        slot = r.LEDGER / f.sha(request)
        r.baseline.require(r.read(slot / "result.json") == result, "Attempt ledger/result differs")
        r.baseline.require(r.read(slot / "rewrite_allowance_closed_v01.json")["resend_authorized"] is False,
                           "Attempt not closed")
        r.baseline.require(result["model_attempts"] == result["oauth_attempts"] == 1 and not result["network_denials"],
                           "Attempt counts or network scope differ")
        response = (rewrite / "response.bin").read_bytes()
        r.baseline.require(f.sha(response) == result["stored_response_sha256"] == result["observed_response_sha256"],
                           "Native response digest/redaction differs")
        native = r.qr_old._json(response)
        r.baseline.require(native["usage"] == result["usage"] and native["model"] == result["returned_model"],
                           "Native metadata differs")
        models.add(native["model"])
        finishes.update(c["finish_reason"] for c in native["choices"])
        for key, number in native["usage"].items():
            r.baseline.require(type(number) is int, "Non-integer usage metadata")
            usage[key] += number
        r.baseline.require(native["usage"]["prompt_tokens"] + native["usage"]["completion_tokens"]
                           == native["usage"]["total_tokens"], "Reported token accounting differs")
        r.baseline.require(native["usage"].get("precached_prompt_tokens", 0) <= native["usage"]["prompt_tokens"],
                           "Precached token count exceeds reported input")
        try:
            parsed = r.qr.parse_response(response, case["question_original"], contexts[case["label"]])
        except ValueError as exc:
            r.baseline.require(result["status"] == "rewrite_rejected" and result["error"] == str(exc),
                               "Original rewrite rejection not reproduced")
        else:
            r.baseline.require(result["status"] == "rewrite_valid" and parsed == r.read(rewrite / "plan.json"),
                               "Original canonical rewrite not reproduced")
        returned = r.qr_old._json(native["choices"][0]["message"]["content"])
        before = r.baseline.BASE / "prepared_v01" / cid
        after = r.BASE / "prepared_v01" / cid
        f.verify_manifest(before)
        f.verify_manifest(after)
        old = r.read(before / "contract.json")
        row = {"id": cid, "article": case["label"], "question": case["question_original"],
            "actual_translation": returned["english_question"], "raw_keywords": returned.get("keywords"),
            "rewrite_status": result["status"], "rewrite_error": result.get("error"), "meaning_decision": decisions[cid],
            "baseline_status": old["preparation_status"], "baseline_ready": old["eligible_for_future_scope"],
            "canonical_normalization_diagnostics": r.read(rewrite / "plan.json")["normalization_diagnostics"]
                if (rewrite / "plan.json").exists() else None,
            "after_status": "rewrite_rejected", "after_ready": False, "answer_request_bytes": 0}
        if decisions[cid]["accept"]:
            c = r.read(after / "contract.json")
            r.baseline.require(c["case"] == case and c["transaction_read_only"] == "on"
                and c["transaction_end"] == "rollback" and not c["dispatch_allowed"]
                and c["model_calls"] == c["oauth_calls"] == c["new_slots"] == 0
                and not c["reference_read_denials"] and not c["network_denials"], "Invalid read-only preparation")
            for path, digest in c["input_bindings"].items():
                r.baseline.require(path not in bindings or bindings[path] == digest, "Conflicting per-case input hashes")
                bindings[path] = digest
            plan_bindings = r.BASE / "answer_plan_bindings_v01" / cid
            f.verify_manifest(plan_bindings)
            f.verify(r.read(plan_bindings / "bindings.json"))
            trace = r.read(after / "trace.json")
            metadata = trace["metadata"]["evidence_adequacy"]
            experiment = metadata["concept_coverage"]["rewriting_experiment"]
            r.baseline.require(experiment["version"] == r.qr.VERSION, "Rewriting not activated")
            row.update(after_status=c["preparation_status"], after_ready=c["eligible_for_future_scope"],
                       answer_request_bytes=c["request_bytes"], answer_request_sha256=c["request_sha256"],
                       article_scope_matches=c["article_scope_matches"], adequacy_reason=metadata["reason"])
            if c["generation_reached"]:
                answer_native = (after / "request.json").read_bytes()
                r.baseline.require(f.sha(answer_native) == c["request_sha256"]
                    and len(answer_native) == c["request_bytes"], "Answer native differs")
                answer_wire = json.loads(answer_native)
                r.baseline.require(case["question"] in answer_wire["messages"][1]["content"], "Original question lost")
            sources = r.read(after / "sources.json")
            r.baseline.require(not sources["diagnostics"], "Unresolved source registry")
            for region in sources["pages"].values():
                observed_pages += 1
                for path_key, hash_key in (("original_pdf_path", "original_pdf_sha256"), ("layer_pdf_path", "layer_pdf_sha256")):
                    path = region[path_key]
                    if path not in hashes:
                        hashes[path] = f.sha(Path(path).read_bytes())
                    r.baseline.require(hashes[path] == region[hash_key], "PDF changed")
                key = (region["layer_pdf_path"], region["page_number"])
                if key not in pages:
                    with fitz.open(key[0]) as pdf:
                        pages[key] = pdf[key[1] - 1].get_text("text")
                text = pages[key]
                r.baseline.require(text == region["page_text"] and f.sha(text.encode()) == region["page_text_sha256"]
                    and text[region["start"]:region["end"]] == region["quote"], "Fresh source text differs")
        else:
            r.baseline.require((after / "rewrite_rejected.json").exists(), "Rejected rewrite incorrectly prepared")
        rows.append(row)
    f.verify(bindings)
    digests = [x["answer_request_sha256"] for x in rows if x["after_ready"]]
    r.baseline.require(len(digests) == len(set(digests)), "Duplicate prepared answer requests")
    summary = {"registered_cases": 30, "actual_rewrite_model_attempts": 30, "actual_rewrite_oauth_attempts": 30,
        "format_valid": sum(x["rewrite_status"] == "rewrite_valid" for x in rows),
        "accepted_after_exposed_agent_meaning_review": sum(x["meaning_decision"]["accept"] for x in rows),
        "baseline_ready": sum(x["baseline_ready"] for x in rows), "rewritten_ready_unsent": sum(x["after_ready"] for x in rows),
        "preparation_statuses": dict(Counter(x["after_status"] for x in rows)), "returned_models": sorted(models),
        "finish_reasons": dict(finishes), "usage": dict(usage), "precached_is_subset_of_prompt": True,
        "actual_cost": None, "fresh_unique_pdf_pages": len(pages), "source_page_observations": observed_pages,
        "pdf_files_verified": len(hashes), "union_input_bindings_verified": len(bindings),
        "answer_native_total_bytes": sum(x["answer_request_bytes"] for x in rows),
        "answer_native_max_bytes": max(x["answer_request_bytes"] for x in rows),
        "new_answer_model_calls": 0, "remaining_rewrite_allowance": 0, "answer_live_authorization": False,
        "scientific_accuracy": None, "plan_percent": 75}
    summary["by_article"] = {label: {"baseline_ready": sum(x["baseline_ready"] for x in rows if x["article"] == label),
        "after_ready": sum(x["after_ready"] for x in rows if x["article"] == label)} for label in r.TITLE_PATTERNS}
    target = r.BASE / "live_review_v01"
    target.mkdir(exist_ok=False)
    f.write(target / "report.json", {"summary": summary, "cases": rows})
    f.write(target / "prospective_answer_scope.json", {"status": "not_authorized", "current_allowance": 0,
        "cases": [{"id": x["id"], "request_sha256": x["answer_request_sha256"]} for x in rows if x["after_ready"]],
        "maximum_model_attempts_if_authorized": summary["rewritten_ready_unsent"],
        "maximum_oauth_attempts_if_authorized": summary["rewritten_ready_unsent"], "model": "GigaChat-2-Max",
        "max_output_tokens": 1200, "per_http_timeout_seconds": 120, "automatic_retries": 0,
        "fallbacks": 0, "continuations": 0, "cost": None,
        "plans_manifest_sha256": f.sha((r.BASE / "plans_freeze_v01/manifest.json").read_bytes())})
    def pre(value):
        return '<pre>' + html.escape(json.dumps(value, ensure_ascii=False, indent=2)) + '</pre>'
    parts = ['<!doctype html><html lang="ru"><meta charset="utf-8"><title>ARIADNE: реальные переводы</title>',
        '<style>body{font:16px/1.5 system-ui;max-width:1500px;margin:30px auto;padding:0 20px}table{border-collapse:collapse}',
        'td,th{border:1px solid #bbc;padding:8px;vertical-align:top}pre{white-space:pre-wrap;overflow-wrap:anywhere}',
        'input{padding:8px;width:60%}details{margin:8px 0}</style><h1>Rewriting v0.2: реальный прогон 30 вопросов</h1>',
        '<p>Реальные переводы GigaChat сохранены без исправлений. Ответы на вопросы модели пока не запрашивались. '
        'Допуск запроса не означает научную правильность ответа. Смысловой review выполнен знакомым с набором агентом.</p>',
        pre(summary), '<label>Поиск <input id="q" type="search"></label><table id="cases"><thead><tr><th>ID</th>',
        '<th>Исходный вопрос</th><th>Реальный перевод</th><th>Решение</th><th>До → после</th><th>Материалы</th></tr></thead><tbody>']
    for row in rows:
        folder = r.BASE / "rewrites" / row["id"]
        after = r.BASE / "prepared_v01" / row["id"]
        links = []
        for path in (folder / "request.json", folder / "response.bin", after / "trace.json",
                     after / "request.json", after / "preparation_api_response.json"):
            if path.exists():
                links.append('<a href="' + path.as_uri() + '">' + html.escape(path.parent.name + '/' + path.name) + '</a>')
        parts.append('<tr><td>' + row["id"] + '</td><td>' + html.escape(row["question"]) + '</td><td>'
            + html.escape(row["actual_translation"]) + '<details><summary>Keywords/diagnostics</summary>'
            + pre({"raw": row["raw_keywords"], "normalization": row["canonical_normalization_diagnostics"]}) + '</details></td><td>'
            + html.escape(row["meaning_decision"]["reason"]) + '</td><td>' + row["baseline_status"] + ' → '
            + row["after_status"] + '</td><td>' + ' · '.join(links) + '</td></tr>')
    parts.append('</tbody></table><h2>Источники</h2><ul>')
    for article in r.read(r.baseline.FREEZE / "articles.json"):
        parts.append('<li><a href="' + Path(article["original_pdf_path"]).as_uri() + '">'
                     + html.escape(article["title"]) + '</a></li>')
    parts.append('</ul><script>document.getElementById("q").addEventListener("input",function(){'
        'const q=this.value.toLowerCase();document.querySelectorAll("#cases tbody tr").forEach(r=>'
        'r.hidden=!r.textContent.toLowerCase().includes(q));});</script></html>')
    page = ''.join(parts)
    f.save(target / "review.html", page.encode())
    parser = Links()
    parser.feed(page)
    for link in parser.links:
        parsed = urlparse(link)
        path = unquote(parsed.path)
        if re.match(r"^/[A-Za-z]:/", path):
            path = path[1:]
        r.baseline.require(parsed.scheme == "file" and Path(path).is_file(), "Broken review link")
    f.write(target / "verification.json", {"links_verified": len(parser.links), "rows": len(rows),
        "new_network_calls_during_review": 0, "browser_or_visual_pdf_qa": "not_run"})
    f.save(target / "executed_script.py", Path(__file__).read_bytes())
    f.manifest(target)
    return {**summary, "links_verified": len(parser.links)}


if __name__ == "__main__":
    policy = f.NetworkPolicy()
    sys.addaudithook(policy)
    print(json.dumps(run(), ensure_ascii=False), flush=True)
    r.baseline.require(not policy.denied, "Forbidden network during review")
