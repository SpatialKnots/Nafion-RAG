"""Closed-scope exact API replay and source-preserving answer/reference review."""

from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
import sys
from collections import Counter
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from scripts import run_fan_doi_besenhard_answers_20261113 as run

f, profile = run.f, run.profile


def offline_replay(row):
    from fastapi.testclient import TestClient

    from app.core.config import get_settings
    from app.db.session import get_session
    from app.generation import required_fields_guard_routes as routes
    from app.generation import service
    from app.main import app
    from app.retrieval.search import SearchResponse, SearchResult

    prepared, live = Path(row["prepared_folder"]), run.BASE / "live" / row["id"]
    settings = f.configure().model_copy(update={"gigachat_credentials": "offline-placeholder"})
    raw = run.read(prepared / "trace.json")["retrieval"]
    retrieval = SearchResponse(**{**raw, "results": [SearchResult(**r) for r in raw["results"]]})
    expected_native = (prepared / "request.json").read_bytes()
    response_raw = (live / "response.bin").read_bytes()
    provider, calls = routes.make_provider(settings), []

    def post(url, body, authorization, *, oauth=False):
        calls.append("oauth" if oauth else "model")
        if oauth:
            return b'{"access_token":"offline-placeholder"}'
        run.require(body == expected_native, "Saved-response native differs from actual sent bytes")
        return response_raw

    provider._post = post

    class Session:
        rollbacks = 0

        def execute(self, statement):
            run.require(str(statement) == "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY", "Unexpected SQL")

        def rollback(self):
            self.rollbacks += 1

        def __getattr__(self, name):
            raise AssertionError("Offline API replay forbids DB access: " + name)

    session = Session()

    def dependency():
        yield session

    app.dependency_overrides[get_session] = dependency
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        with profile.activate(row["case"], profile.load_plan(row["case"])), \
                patch.object(service, "search_chunks", lambda *a, **kw: deepcopy(retrieval)), \
                patch.object(routes, "make_provider", lambda s: provider), TestClient(app) as client:
            response = client.post("/answer/experimental/required-fields", json=run.read(prepared / "api_request.json"))
        actual = {"http_status": response.status_code, "body": response.json()}
        run.require(actual == run.read(live / "api_response.json"), "Full delivered API replay differs")
        run.require(calls == ["oauth", "model"] and session.rollbacks == 1, "Replay repeated or omitted transport/rollback")
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_settings, None)
    return {"id": row["id"], "full_api_exact": True, "native_exact": True,
            "real_model_calls": 0, "real_oauth_calls": 0, "DB_queries": 0}


def references():
    raw = (profile.baseline.PRIVATE / "supplied_original.md").read_bytes()
    original = raw.decode("utf-8-sig")
    run.require(f.sha(raw) == profile.baseline.read(profile.baseline.FREEZE / "runtime.json")["reference_document_sha256"],
                "Supplied reference document changed")
    heads = list(re.finditer(r"^### ([FDB](?:[1-9]|10))\. ([^\r\n]+)\r?$", original, re.M))
    run.require([m[1] for m in heads] == profile.baseline.IDS, "Reference case identities differ")
    rows = {}
    for i, match in enumerate(heads):
        block = original[match.end():heads[i + 1].start() if i + 1 < len(heads) else len(original)]
        answer = block.split("**Эталонный ответ:**", 1)[1].split("**Источник:**", 1)[0].strip()
        source = block.split("**Источник:**", 1)[1].split("\n---", 1)[0].strip()
        if match[1] == "B10":
            source = re.split(r"\r?\n\r?\n", source, maxsplit=1)[0]
        rows[match[1]] = {"question_original": match[2], "reference_answer_verbatim": answer,
                         "reference_source_declaration_verbatim": source}
    return rows


def review():
    authorization = run.authorization()
    closed = run.read(run.BASE / "scope_closed_v01.json")
    run.require(closed["remaining_model_allowance"] == closed["remaining_oauth_allowance"] == 0, "Scope not closed")
    rows, usage, models, finishes = [], Counter(), set(), Counter()
    for row in authorization["cases"]:
        live = run.BASE / "live" / row["id"]
        f.verify_manifest(live)
        result = run.read(live / "result.json")
        slot = run.LEDGER / row["request_sha256"]
        run.require(run.read(slot / "result.json") == result and run.read(slot / "closed.json")["allowance_closed"], "Ledger differs")
        api = run.read(live / "api_response.json")
        native = profile.qr_old._json((live / "response.bin").read_bytes())
        run.require((live / "request.json").read_bytes() == (Path(row["prepared_folder"]) / "request.json").read_bytes(),
                    "Live request differs")
        run.require(f.sha((live / "response.bin").read_bytes()) == result["observed_response_sha256"]
                    == result["stored_response_sha256"], "Response changed/redacted")
        run.require(result["postflight_hashes"] == "verified" and not result["network_denials"]
                    and not result["reference_read_denials"], "Postflight diagnostics")
        models.add(native["model"])
        finishes.update(c["finish_reason"] for c in native["choices"])
        usage.update(native["usage"])
        rows.append({"id": row["id"], "case": row["case"], "result": result, "api": api,
                     "native_provider_content": native["choices"][0]["message"]["content"],
                     "prepared_folder": row["prepared_folder"]})
    refs = references()
    by_id = {r["id"]: r for r in rows}
    all_rows = []
    for case in profile.cases():
        value = by_id.get(case["id"], {"id": case["id"], "case": case, "result": {"status": "rewrite_rejected"}})
        value.update(refs[case["id"]])
        all_rows.append(value)
    summary = {"registered_questions": 30, "authorized_answer_cases": len(rows),
        "model_attempts": sum(r["result"]["model_attempts"] for r in rows),
        "oauth_attempts": sum(r["result"]["oauth_attempts"] for r in rows),
        "http_statuses": dict(Counter(r["api"]["http_status"] for r in rows)),
        "answer_statuses": dict(Counter(r["api"]["body"].get("answer", {}).get("status", "api_error") for r in rows)),
        "delivery_statuses": dict(Counter(r["api"]["body"].get("delivery_status", "api_error") for r in rows)),
        "returned_models": sorted(models), "finish_reasons": dict(finishes), "usage": dict(usage), "cost": None,
        "remaining_model_allowance": 0, "remaining_oauth_allowance": 0,
        "scientific_assessment": "pending_exposed_assistant_source_review", "scientific_accuracy": None, "plan_percent": 75}
    output = run.BASE / "review_v01"
    output.mkdir(exist_ok=False)
    f.write(output / "report.json", {"summary": summary, "cases": all_rows})
    parts = ['<!doctype html><html lang="ru"><meta charset="utf-8"><title>ARIADNE: реальные ответы</title>',
        '<style>body{font:16px/1.5 system-ui;max-width:1500px;margin:30px auto;padding:0 20px}',
        'pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f4f5f8;padding:12px}',
        'section{border-top:2px solid #bbc;margin-top:24px}table{border-collapse:collapse}td,th{border:1px solid #bbc;padding:8px}</style>',
        '<h1>Fan / Doi / Besenhard — реальные ответы после rewriting</h1>',
        '<p>Исходные ответы и ошибки сохранены. HTTP200 и ссылка не доказывают научную правильность. '
        'Пользовательские эталоны показаны отдельно; они не передавались inference workers.</p>',
        '<pre>' + html.escape(json.dumps(summary, ensure_ascii=False, indent=2)) + '</pre>']
    for row in all_rows:
        cid = row["id"]
        parts.append('<section><h2>' + cid + ' — ' + html.escape(row["question_original"]) + '</h2>')
        answer = row.get("api", {}).get("body", {})
        delivered = answer.get("answer", {})
        parts.append('<h3>Доставленный ответ</h3><pre>'
                     + html.escape(delivered.get("answer") or 'Ответ не выдан: ' + row["result"].get("status", "unknown")) + '</pre>')
        for citation in delivered.get("citations", []):
            page = citation.get("page_start")
            pdf = Path(row["case"]["original_pdf_path"]).as_uri() + ('#page=' + str(page) if page else '')
            label = str(citation.get("title") or row["case"]["label"]) + (' · PDF ' + str(page) if page else '')
            parts.append('<a href="' + pdf + '">' + html.escape(label) + '</a> · ')
        parts.append('<details><summary>Полный API результат и диагностика</summary><pre>'
            + html.escape(json.dumps(answer or row["result"], ensure_ascii=False, indent=2)) + '</pre></details>')
        parts.append('<details><summary>Пользовательский эталон — без исправлений</summary><pre>'
            + html.escape(row["reference_answer_verbatim"]) + '</pre><p>'
            + html.escape(row["reference_source_declaration_verbatim"]) + '</p></details>')
        if "api" in row:
            parts.append('<details><summary>Исходный native content модели</summary><pre>'
                         + html.escape(row["native_provider_content"]) + '</pre></details>')
            live, prepared = run.BASE / "live" / cid, Path(row["prepared_folder"])
            for path in (live / "api_response.json", live / "response.bin", live / "request.json",
                         prepared / "trace.json", prepared / "sources.json"):
                parts.append('<a href="' + path.as_uri() + '">' + html.escape(path.name) + '</a> · ')
        parts.append('</section>')
    parts.append('</html>')
    f.save(output / "review.html", ''.join(parts).encode())
    f.save(output / "executed_script.py", Path(__file__).read_bytes())
    f.manifest(output)
    return summary


def replay_all():
    run.require((run.BASE / "scope_closed_v01.json").exists(), "Close real scope first")
    rows = []
    for row in run.authorization()["cases"]:
        folder = run.BASE / "offline_replay_v01" / row["id"]
        folder.mkdir(parents=True, exist_ok=False)
        done = subprocess.run([sys.executable, "-X", "utf8", "-B", "-m", __spec__.name,
                               "replay", "--case-id", row["id"]], cwd=f.ROOT,
                              capture_output=True, text=True, encoding="utf-8", check=False)
        f.save(folder / "stdout.txt", done.stdout.encode())
        f.save(folder / "stderr.txt", done.stderr.encode())
        record = {"id": row["id"], "exit_code": done.returncode}
        if done.returncode == 0:
            record.update(json.loads(done.stdout.strip().splitlines()[-1]))
        rows.append(record)
        print(json.dumps(record), flush=True)
        if done.returncode:
            break
    value = {"cases": rows, "finished_all": len(rows) == 26 and all(x["exit_code"] == 0 for x in rows),
             "real_model_calls": 0, "real_oauth_calls": 0, "DB_queries": 0}
    f.write(run.BASE / "offline_replay_v01/report.json", value)
    f.manifest(run.BASE / "offline_replay_v01")
    return {"cases": len(rows), "finished_all": value["finished_all"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("review", "replay", "replay-all"))
    parser.add_argument("--case-id")
    args = parser.parse_args()
    policy = f.NetworkPolicy()
    sys.addaudithook(policy)
    if args.mode == "review":
        result = review()
    elif args.mode == "replay-all":
        result = replay_all()
    else:
        row = next(r for r in run.authorization()["cases"] if r["id"] == args.case_id)
        result = offline_replay(row)
    run.require(not policy.denied, "Forbidden review/replay network")
    print(json.dumps(result, ensure_ascii=False), flush=True)
