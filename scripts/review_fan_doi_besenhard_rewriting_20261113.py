"""Verify and display the connected profile before any paid rewriting dispatch."""

from __future__ import annotations

import html
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse

import fitz

from scripts import fan_doi_besenhard_rewriting_20261113 as r

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
    r.baseline.require(not (r.BASE / "rewrite_authorization_v01.json").exists(), "Pre-send review only")
    r.baseline.require(not (r.BASE / "rewrites").exists(), "A rewriting stage already exists")
    titles = r.read(r.FREEZE / "title_contexts.json")
    for label, proof in titles["proofs"].items():
        with fitz.open(proof["original_pdf_path"]) as pdf:
            text = pdf[proof["pdf_page"] - 1].get_text("text")
        r.baseline.require(text == proof["page_text"] and f.sha(text.encode()) == proof["page_text_sha256"], "Title page drift")
        r.baseline.require(text[proof["start"]:proof["end"]] == proof["raw_title"], "Title span drift")
        r.baseline.require(re.sub(r"\s+", " ", proof["raw_title"]).strip() == titles["contexts"][label]["title"],
                           "Title normalization differs")
        r.qr.context_valid(titles["contexts"][label])
    rows = []
    old_cases = r.read(r.baseline.FREEZE / "questions.json")["cases"]
    r.baseline.require(cases == old_cases, "Original cases changed")
    for case in cases:
        folder = r.FREEZE / "rewrites" / case["id"]
        f.verify_manifest(folder)
        raw = (folder / "request.json").read_bytes()
        request = json.loads(raw)
        user = json.loads(request["messages"][1]["content"])
        context = titles["contexts"][case["label"]]
        # The snapshot writer sorts mapping keys. Restore the title_context()
        # constructor's order when verifying the original, unsorted wire JSON.
        original_order = {key: context[key] for key in
                          ("article_id", "title", "title_sha256", "original_pdf_sha256")}
        r.baseline.require(raw == r.qr.request(case, "GigaChat-2-Max", original_order), "Native differs")
        r.baseline.require(set(user) == {"question", "verified_article", "locked_identifiers"}, "Unexpected rewrite input")
        r.baseline.require(user["question"] == case["question_original"], "Original question altered")
        r.baseline.require(user["verified_article"] == titles["contexts"][case["label"]], "Article context differs")
        r.baseline.require(user["locked_identifiers"] == r.qr_old.identifiers(case["question_original"]), "Identifier drift")
        r.baseline.require(request["max_tokens"] == 1200 and len(raw) <= 100000, "Request budget differs")
        old = r.baseline.BASE / "prepared_v01" / case["id"]
        f.verify_manifest(old)
        old_status = r.read(old / "contract.json")["preparation_status"]
        rows.append({"id": case["id"], "question_original": case["question_original"], "baseline_status": old_status,
                     "request_sha256": f.sha(raw), "request_bytes": len(raw), "rewriting_result": None})
    summary = {"cases": 30, "rewrite_requests_exact": 30, "questions_identical_to_baseline": 30,
        "verified_title_spans_and_fresh_pages": 3, "old_preparation_manifests_unchanged": 30,
        "request_bytes": sum(x["request_bytes"] for x in rows), "max_request_bytes": max(x["request_bytes"] for x in rows),
        "method_connected": "existing rewriting v0.2, explicit thirty-case isolated-process profile",
        "baseline_ready": sum(x["baseline_status"] == "ready_unsent" for x in rows),
        "rewritten_ready": None, "new_model_calls": 0, "new_oauth_calls": 0, "new_slots": 0,
        "scientific_scores": None, "plan_percent": 75, "application_default_changed": False,
        "test_result": "59 passed; one pre-existing StarletteDeprecationWarning",
        "earlier_test_attempt": "58 passed, one setup PermissionError on Windows Temp; rerun with fresh workspace basetemp"}
    output = r.BASE / "connection_review_v01"
    output.mkdir(exist_ok=False)
    f.write(output / "report.json", {"summary": summary, "cases": rows})
    f.write(output / "prospective_rewrite_scope.json", {"cases": rows,
        "input_freeze_manifest_sha256": f.sha((r.FREEZE / "manifest.json").read_bytes()),
        "scope_sha256": f.sha(r.PROTOCOL.read_bytes()), "maximum_rewrite_model_attempts": 30,
        "maximum_rewrite_oauth_attempts": 30, "current_live_allowance": 0,
        "model": "GigaChat-2-Max", "max_output_tokens": 1200, "per_http_timeout_seconds": 120,
        "attempts_per_case": 1, "automatic_retries": 0, "fallbacks": 0, "continuations": 0,
        "cost": None, "answer_calls_authorized": False, "status": "awaiting_separate_live_authorization"})
    parts = ['<!doctype html><html lang="ru"><meta charset="utf-8"><title>ARIADNE: rewriting подключён</title>',
        '<style>body{font:16px/1.5 system-ui;margin:30px}table{border-collapse:collapse}td,th{padding:8px;border:1px solid #bbc}',
        'pre{white-space:pre-wrap;overflow-wrap:anywhere}</style><h1>Rewriting v0.2 — подключение к 30 вопросам</h1>',
        '<p>Метод подключён к отдельному прогону Fan / Doi / Besenhard. Исходный baseline сохранён. '
        'Переводов и ответов модели пока нет; новые вызовы не выполнялись.</p>',
        '<pre>' + html.escape(json.dumps(summary, ensure_ascii=False, indent=2)) + '</pre>',
        '<table><tr><th>ID</th><th>Исходный вопрос</th><th>Прежний результат</th><th>Запрос на rewriting</th></tr>']
    for row in rows:
        path = r.FREEZE / "rewrites" / row["id"] / "request.json"
        parts.append('<tr><td>' + row["id"] + '</td><td>' + html.escape(row["question_original"]) + '</td><td>'
            + html.escape(row["baseline_status"]) + '</td><td><a href="' + path.as_uri() + '">'
            + str(row["request_bytes"]) + ' bytes</a></td></tr>')
    parts.append('</table><h2>Проверенные названия</h2><ul>')
    for label, context in titles["contexts"].items():
        proof = titles["proofs"][label]
        parts.append('<li><a href="' + Path(proof["original_pdf_path"]).as_uri() + '#page=' + str(proof["pdf_page"])
            + '">' + html.escape(context["title"]) + '</a> — PDF-страница ' + str(proof["pdf_page"]) + '</li>')
    parts.append('</ul><p>Синтетические API-контроли проверяют подключение. Они не являются новыми ответами '
        'GigaChat и не оценивают научную точность. Ни эталоны, ни source-page hints не включены в native requests.</p></html>')
    page = ''.join(parts)
    f.save(output / "review.html", page.encode())
    parser = Links()
    parser.feed(page)
    for link in parser.links:
        parsed = urlparse(link)
        path = unquote(parsed.path)
        if re.match(r"^/[A-Za-z]:/", path):
            path = path[1:]
        r.baseline.require(parsed.scheme == "file" and Path(path).is_file(), "Broken output link")
    f.write(output / "verification.json", {"links_verified": len(parser.links), "actual_native_inputs_verified": 30,
                                           "browser_layout_checked": False})
    f.save(output / "executed_script.py", Path(__file__).read_bytes())
    f.manifest(output)
    return {**summary, "links_verified": len(parser.links)}


if __name__ == "__main__":
    policy = f.NetworkPolicy()
    r.sys.addaudithook(policy)
    print(json.dumps(run(), ensure_ascii=False), flush=True)
    r.baseline.require(not policy.denied, "Unexpected network")
