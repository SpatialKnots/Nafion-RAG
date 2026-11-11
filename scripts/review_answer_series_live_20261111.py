"""Review closed real-model attempts and replay saved native responses offline."""

from __future__ import annotations

import argparse
import html
import json
import os
import sys
from collections import Counter
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

from scripts import gigachat_answer_smoke as f
from scripts import run_answer_series_live_20261111 as run


def offline_api(prepared, live):
    from fastapi.testclient import TestClient

    from app.core.config import get_settings
    from app.db.session import get_session
    from app.generation import required_fields_guard_routes as routes
    from app.generation import service
    from app.main import app
    from app.retrieval.search import SearchResponse, SearchResult

    settings = f.configure()
    settings.gigachat_credentials = "offline-saved-response-placeholder"
    payload = run.read(prepared / "trace.json")["retrieval"]
    retrieval = SearchResponse(**{**payload, "results": [SearchResult(**r) for r in payload["results"]]})
    expected = (prepared / "request.json").read_bytes()
    response_raw = (live / "response.bin").read_bytes()
    provider = routes.make_provider(settings)
    calls = []

    def post(url, body, authorization, *, oauth=False):
        calls.append("oauth" if oauth else "model")
        if oauth:
            return b'{"access_token":"offline-placeholder"}'
        run.require(body == expected, "Offline native request differs from actual sent bytes")
        return response_raw

    provider._post = post

    class Session:
        rollbacks = 0

        def execute(self, statement):
            run.require(str(statement) == "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY",
                        "Unexpected DB access during saved-response replay")

        def rollback(self):
            self.rollbacks += 1

        def __getattr__(self, name):
            raise AssertionError("Saved-response replay forbids DB access: " + name)

    session = Session()

    def dependency():
        yield session

    app.dependency_overrides[get_session] = dependency
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        with patch.object(service, "search_chunks", lambda *a, **kw: deepcopy(retrieval)), \
                patch.object(routes, "make_provider", lambda s: provider), TestClient(app) as client:
            response = client.post("/answer/experimental/required-fields", json=run.read(prepared / "api_request.json"))
        actual = run.read(live / "api_response.json")
        run.require({"http_status": response.status_code, "body": response.json()} == actual,
                    "Saved-response API replay differs")
        run.require(calls == ["oauth", "model"] and session.rollbacks == 1, "Saved-response replay repeated transport")
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_settings, None)
        get_settings.cache_clear()
    return {"http_status": response.status_code, "full_body_exact": True,
            "synthetic_transport_calls": calls, "real_model_calls": 0, "DB_queries": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--posthoc", type=Path)
    args = parser.parse_args()
    policy = f.NetworkPolicy()
    sys.addaudithook(policy)
    closed = run.read(run.BASE / "scope_closed_v01.json")
    run.require(closed["remaining_allowance"] == 0 and len(closed["cases"]) == 30, "Review requires closed allowance")
    f.verify_manifest(run.BASE / "input_freeze_v01")
    f.verify(run.read(run.BASE / "input_freeze_v01/bindings.json"))
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    f.save(out / "executed_script.py", Path(__file__).read_bytes())
    questions = run.read(run.BASE / "input_freeze_v01/questions.json")["cases"]
    rows, counts, usage, articles, inputs = [], Counter(), Counter(), {}, []
    posthoc = run.read(args.posthoc) if args.posthoc else {}
    for case in questions:
        cid, prepared, live = case["id"], run.BASE / "prepared_v01" / case["id"], run.BASE / "live" / case["id"]
        original = next(r for r in closed["cases"] if r["id"] == cid)
        f.verify_manifest(prepared)
        f.verify(run.read(prepared / "contract.json")["input_bindings"])
        inputs.append(prepared / "manifest.json")
        result = {"id": cid, "question": case["question"], "result": original, "api_response": None,
                  "native_response": None, "offline_API_replay": None, "source_fact_protocol": None,
                  "posthoc_source_review": posthoc.get(cid), "scientific_accuracy": None}
        trace = run.read(prepared / "trace.json")
        from app.generation import answer_facts
        from app.generation.providers import Evidence

        evidence = [Evidence(**e) for e in trace["evidence"]]
        records = answer_facts.selection_records(evidence)
        result["source_fact_records"] = records
        result["evidence"] = [asdict(e) for e in evidence]
        result["registered_sources"] = run.read(prepared / "sources.json")
        for a in run.read(prepared / "articles.json"):
            articles[a["article_id"]] = a
        if (live / "result.json").exists():
            f.verify_manifest(live)
            inputs.append(live / "manifest.json")
            saved = run.read(live / "result.json")
            slot = run.LEDGER / run.read(prepared / "contract.json")["request_sha256"]
            run.require(run.read(slot / "result.json") == saved and run.read(slot / "closed.json")["allowance_closed"],
                        "Exclusive attempt ledger differs from live output")
            inputs.extend([slot / "result.json", slot / "closed.json"])
            if (live / "api_response.json").exists():
                api = run.read(live / "api_response.json")
                result["api_response"] = api
                counts["HTTP:" + str(api["http_status"])] += 1
                counts["answer:" + str(api["body"].get("answer", {}).get("status"))] += 1
                counts["guard:" + str(api["body"].get("delivery_status"))] += 1
            if (live / "request.json").exists():
                run.require((live / "request.json").read_bytes() == (prepared / "request.json").read_bytes(),
                            "Sent native differs from sealed input")
            if (live / "response.bin").exists():
                from app.generation.gigachat import _json
                try:
                    native = _json((live / "response.bin").read_bytes())
                except (ValueError, UnicodeError) as exc:
                    result["native_parse_error"] = type(exc).__name__
                else:
                    result["native_response"] = native
                    if isinstance(native, dict):
                        for key, value in (native.get("usage") or {}).items():
                            if isinstance(value, int):
                                usage[key] += value
                    if result["api_response"] is not None:
                        result["offline_API_replay"] = offline_api(prepared, live)
                    if records and isinstance(native, dict) and len(native.get("choices", [])) == 1:
                        choice = native["choices"][0]
                        try:
                            selected = _json(choice["message"]["content"])
                        except (ValueError, UnicodeError, KeyError, TypeError) as exc:
                            result["source_fact_protocol"] = {"status": "unparseable", "error": type(exc).__name__}
                        else:
                            expected = [{"text": key, "citation_ids": [record["citation_id"]]} for key, record in records.items()]
                            accepted = (choice.get("finish_reason") == "stop" and selected == {"answerable": True, "claims": expected})
                            abstained = selected == {"answerable": False, "claims": []}
                            label = "exact_ID_selection" if accepted else "abstained" if abstained else "invalid_selection"
                            result["source_fact_protocol"] = {"status": label, "scientific_accuracy": None}
                            counts["fact_protocol:" + label] += 1
        else:
            counts["not_dispatched"] += 1
        f.write(out / (cid + ".json"), result)
        rows.append(result)
        print(json.dumps({"id": cid, "offline_replay": bool(result["offline_API_replay"])}), flush=True)
    run.require(not policy.denied, "External network attempted during review")
    summary = {"cases": 30, "model_attempts": closed["model_attempts"], "oauth_attempts": closed["oauth_attempts"],
        "counts": dict(counts), "usage": dict(usage), "actual_cost": None, "remaining_allowance": 0,
        "saved_response_API_replays_exact": sum(bool(r["offline_API_replay"]) for r in rows),
        "scientific_accuracy": None, "independent_evaluation": False, "plan_percent": 75,
        "new_model_calls_during_review": 0, "network_denials_during_review": policy.denied}
    f.write(out / "report.json", {"summary": summary, "cases": rows, "articles": articles})
    links = []

    def link(path, label):
        run.require(path.is_file(), "Missing local review link")
        links.append(str(path))
        return '<a href="' + html.escape(os.path.relpath(path, out).replace("\\", "/"), quote=True) + '">' + html.escape(label) + '</a>'

    def details(label, value):
        return '<details><summary>' + html.escape(label) + '</summary><pre>' + html.escape(
            json.dumps(value, ensure_ascii=False, indent=2)) + '</pre></details>'

    table = []
    for row in rows:
        api = row["api_response"]
        delivered = api["body"].get("answer", {}).get("answer") if api else None
        extra = details("Доставленный ответ / ошибка API", api)
        extra += details("Исходный ответ модели — отдельно от серверного текста", row["native_response"])
        extra += details("Raw source/условия/цитаты", row["registered_sources"])
        extra += details("Source-bound records / статус ID-протокола", [row["source_fact_records"], row["source_fact_protocol"]])
        if row["posthoc_source_review"]:
            extra += details("Post-hoc наблюдение по источнику — не независимая оценка", row["posthoc_source_review"])
        cell = html.escape(delivered or "Ответ не доставлен; см. API/результат.") + extra
        table.append('<tr data-case><td>' + html.escape(row["id"]) + '</td><td>' + html.escape(row["question"])
            + '</td><td>' + html.escape(str(api["http_status"]) if api else row["result"]["status"])
            + '</td><td>' + cell + '</td><td>' + link(out / (row["id"] + ".json"), "Полная диагностика") + '</td></tr>')
    tac = []
    for article in articles.values():
        columns = [str(article.get(k) or "Не собрано / отсутствует в snapshot") for k in
                   ("title", "authors", "journal", "year", "abstract", "conclusions", "terms")]
        tac.append('<tr>' + ''.join('<td>' + html.escape(v) + '</td>' for v in columns)
                   + '<td>' + link(Path(article["original_pdf_path"]), "Исходный PDF") + '</td></tr>')
    body = ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>ARIADNE — реальный прогон30</title>'
        '<style>body{font:16px system-ui;margin:30px;color:#18333f}table{border-collapse:collapse;width:100%}'
        'td,th{border:1px solid #bcd;padding:8px;vertical-align:top}pre{white-space:pre-wrap;overflow-wrap:anywhere}'
        'details{max-width:65vw}input{padding:10px;width:70%;margin:16px 0}</style><h1>Реальный прогон30: закрытый scope</h1>'
        '<p>11 ноября2026. Новые реальные результаты после offline freeze. Все30 вопросов development-exposed; '
        'это runtime/ID-protocol trial, не независимая научная оценка. Серверный текст и native модельные ответы '
        'показаны отдельно. Все лимиты закрыты, повторов нет; план75% прежний.</p>'
        + details("Итог: фактические вызовы, доступность, usage и replay", summary)
        + '<p>' + link(run.BASE / "scope_closed_v01.json", "Закрытие всех30 разрешений") + ' · '
        + link(run.BASE / "approval_v01.json", "Зафиксированные запросы") + '</p>'
        '<label>Поиск <input id="search" type="search"></label><table id="cases"><thead><tr><th>ID</th><th>Вопрос</th>'
        '<th>HTTP/исход</th><th>Ответ и доказательства</th><th>Данные</th></tr></thead><tbody>' + ''.join(table)
        + '</tbody></table><h2>Все три статьи: TAC snapshot</h2><table><thead><tr>'
        + ''.join('<th>' + k + '</th>' for k in
                  ("Title", "Authors", "Journal", "Year", "Abstract", "Conclusions", "Terms", "Original file"))
        + '</tr></thead><tbody>' + ''.join(tac) + '</tbody></table>'
        '<p>Source grammar и exact citation не доказывают научную истинность. Guard not_evaluated не является '
        'научным подтверждением. Стоимость неизвестна. Новые статьи, независимая приёмка, browser layout, '
        'deployment и автоматические последующие вызовы не входят в этот scope.</p><script>'
        'document.getElementById("search").addEventListener("input",e=>{const q=e.target.value.toLocaleLowerCase();'
        'document.querySelectorAll("[data-case]").forEach(r=>r.hidden=!r.textContent.toLocaleLowerCase().includes(q));});'
        '</script></html>')
    f.save(out / "review.html", body.encode())
    f.write(out / "HTML_checks.json", {"case_rows": len(table), "article_rows": len(tac), "local_links": len(links)})
    inputs += [run.BASE / "scope_closed_v01.json", run.BASE / "approval_v01.json", Path(__file__), run.SCOPE]
    if args.posthoc:
        inputs.append(args.posthoc)
    f.write(out / "bindings.json", f.bindings(inputs))
    f.manifest(out)
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
