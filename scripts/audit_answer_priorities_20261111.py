"""Offline schema/source-contract comparison, historical replay, package and HTML audit."""

from __future__ import annotations

import argparse
import html
import json
import os
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import jsonschema

from scripts import audit_answer_series_20261111 as series
from scripts import bilingual_lexical_admission_20261110 as replay
from scripts import gigachat_answer_smoke as f
from scripts import quantitative_binding_20261111 as quant

BASE = f.ROOT / "output/answer_priorities_20261111"
OLD = f.ROOT / "output/answer_series_live_20261111"
TARGETS = {"Kondo_04", "Nambu_10", "Peng_01"}
PROTOCOL = f.ROOT / "docs/records/answer_priorities_2026-11-11_v0.1.md"


def read(path):
    return json.loads(path.read_bytes())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def schema_delta(before, after):
    """Only the F-ID array cardinality/uniqueness and single-citation bounds may differ."""
    if before == after:
        return False
    old, current = json.loads(before), json.loads(after)
    schema = current["response_format"]["schema"]
    require(schema["properties"]["claims"].pop("maxItems") == len(schema["$defs"]["_Claim"]["properties"]["text"]["enum"]),
            "Unexpected F-ID maximum")
    require(schema["properties"]["claims"].pop("uniqueItems") is True, "Missing uniqueItems")
    citations = schema["$defs"]["_Claim"]["properties"]["citation_ids"]
    require(citations.pop("minItems") == citations.pop("maxItems") == 1, "Unexpected citation cardinality")
    require(old == current, "Native changed outside declared schema constraints")
    return True


def api_replay(api, retrieval, native, response_raw):
    from fastapi.testclient import TestClient

    from app.core.config import get_settings
    from app.db.session import get_session
    from app.generation import required_fields_guard_routes as routes
    from app.generation import service
    from app.main import app
    from app.retrieval.search import SearchResponse, SearchResult

    settings = f.configure().model_copy(update={"gigachat_credentials": "offline-placeholder"})
    provider = routes.make_provider(settings)
    calls = []

    def post(url, body, authorization, *, oauth=False):
        calls.append("oauth" if oauth else "model")
        if oauth:
            return b'{"access_token":"offline-placeholder"}'
        require(body == native, "Synthetic API native differs from current preparation")
        return response_raw

    provider._post = post

    class Session:
        rollbacks = 0

        def execute(self, statement):
            require(str(statement) == "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY", "Unexpected SQL")

        def rollback(self):
            self.rollbacks += 1

        def __getattr__(self, name):
            raise AssertionError("Offline API forbids DB access: " + name)

    session = Session()
    raw = SearchResponse(**{**retrieval, "results": [SearchResult(**r) for r in retrieval["results"]]})

    def dependency():
        yield session

    app.dependency_overrides[get_session] = dependency
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        with patch.object(service, "search_chunks", lambda *a, **kw: deepcopy(raw)), \
                patch.object(routes, "make_provider", lambda s: provider), TestClient(app) as client:
            response = client.post("/answer/experimental/required-fields", json=api)
        require(calls == ["oauth", "model"] and session.rollbacks == 1, "Synthetic API repeated or omitted rollback")
        return {"http_status": response.status_code, "body": response.json()}
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_settings, None)


def compare(output, *, no_api=False, expected_comparison=None):
    from app.generation import answer_facts, service
    from app.generation.providers import Evidence, GeneratedClaim, GenerationOutputError

    output.mkdir(parents=True, exist_ok=False)
    f.save(output / "executed_script.py", Path(__file__).read_bytes())
    f.verify_manifest(OLD / "input_freeze_v01")
    require(read(OLD / "scope_closed_v01.json")["remaining_allowance"] == 0, "Old allowance reopened")
    app = f.bindings(series.app_paths())
    settings, rows = f.configure(), []
    for cid in series.IDS:
        prepared = OLD / "prepared_v01" / cid
        f.verify_manifest(prepared)
        api, trace = read(prepared / "api_request.json"), read(prepared / "trace.json")
        before = {"trace": trace, "generation_reached": True, "answer": None}
        after, native = replay.run_service(service, api, trace, settings)
        require(after["generation_reached"] and native, "Current preparation refused: " + cid)
        require(after["trace"]["retrieval"] == trace["retrieval"], "Retrieval changed: " + cid)
        old_native = (prepared / "request.json").read_bytes()
        changed_schema = False
        if cid not in TARGETS:
            require(after == before, "Non-target full service result changed: " + cid)
            changed_schema = schema_delta(old_native, native)
        else:
            old_request, new_request = json.loads(old_native), json.loads(native)
            require(all(old_request[k] == new_request[k] for k in ("model", "max_tokens", "stream")), "Runtime budget changed")
        evidence = [Evidence(**e) for e in after["trace"]["evidence"]]
        records = answer_facts.selection_records(evidence)
        anchors = 0
        for parent in evidence:
            if parent.source_type != "source_fact_derived":
                continue
            payload = json.loads(parent.text)
            answer_facts.verify_raw_binding(parent.text, payload["raw_source"], article_id=parent.article_id,
                chunk_id=parent.chunk_id, citation_id=parent.citation_id, page_start=parent.page_start,
                page_end=parent.page_end, source_type=payload["raw_source_type"])
            for record in records.values():
                for fact in record["facts"]:
                    require(not fact["scientific_ownership_verified"], "Scientific ownership asserted")
                    for anchor in [fact["support"], *[v["source"] for v in
                          (fact["sample"], fact["value"], fact["unit"], fact["method"], *fact["conditions"].values()) if v]]:
                        raw = payload["raw_source"]
                        require(raw[anchor["start"]:anchor["end"]] == anchor["text"]
                                and f.sha(raw.encode()) == anchor["raw_chunk_sha256"], "Raw fact anchor differs")
                        anchors += 1
        folder = output / cid
        folder.mkdir()
        f.write(folder / "after.json", after)
        f.save(folder / "request_unsent.json", native)
        if expected_comparison:
            require(after == read(expected_comparison / cid / "after.json")
                    and native == (expected_comparison / cid / "request_unsent.json").read_bytes(), "Installed app differs")
        controls = None
        if records:
            selected = quant.synthetic(service, api, trace["retrieval"], "select", settings)
            abstained = quant.synthetic(service, api, trace["retrieval"], "abstain", settings)
            require(selected["status"] == "answered" and abstained["status"] == "insufficient_evidence", "Synthetic boundary differs")
            try:
                quant.synthetic(service, api, trace["retrieval"], "invalid", settings)
            except GenerationOutputError:
                pass
            else:
                raise ValueError("Unbound prose accepted")
            try:
                answer_facts.resolve_selections([GeneratedClaim(k, ["E999"]) for k in records], evidence)
            except GenerationOutputError:
                pass
            else:
                raise ValueError("Wrong citation accepted")
            controls = {"execution": "SYNTHETIC, not new model output", "selected": selected, "abstained": abstained,
                        "invalid_prose_rejected": True, "wrong_citation_rejected": True}
        saved_api, api_controls = None, []
        if not no_api:
            saved_api = api_replay(api, trace["retrieval"], native, (OLD / "live" / cid / "response.bin").read_bytes())
            if cid in TARGETS:
                require(saved_api["http_status"] == 502, "Old incomplete free answer was accepted by new contract")
                for mode in ("select", "abstain", "prose", "wrong_citation"):
                    claims = [] if mode == "abstain" else [{"text": "invented prose" if mode == "prose" else k,
                        "citation_ids": ["E999" if mode == "wrong_citation" else r["citation_id"]]} for k, r in records.items()]
                    content = {"answerable": mode != "abstain", "claims": claims}
                    schema = json.loads(native)["response_format"]["schema"]
                    if mode in ("select", "abstain"):
                        jsonschema.validate(content, schema)
                    raw_response = f.encode({"choices": [{"finish_reason": "stop", "message": {
                        "role": "assistant", "content": json.dumps(content)}}]})
                    response = api_replay(api, trace["retrieval"], native, raw_response)
                    require(response["http_status"] == (200 if mode in ("select", "abstain") else 502), "API control differs")
                    api_controls.append({"mode": mode, "execution": "SYNTHETIC", **response})
            else:
                require(saved_api == read(OLD / "live" / cid / "api_response.json"), "Other saved API result changed")
        row = {"id": cid, "question": api["question"], "ready_unsent": True, "full_result_exact": after == before,
            "schema_only_change": changed_schema, "native_exact": native == old_native, "fact_records": records,
            "raw_anchors": anchors, "synthetic_controls": controls, "old_native_under_current_contract": saved_api,
            "synthetic_API_controls": api_controls, "scientific_accuracy": None}
        rows.append(row)
        f.write(folder / "result.json", row)
        f.manifest(folder)
        print(json.dumps({"id": cid, "target": cid in TARGETS, "ready_unsent": True}), flush=True)
    summary = {"cases": 30, "ready_unsent": 30, "retrieval_exact": 30,
        "non_target_full_results_exact": sum(r["full_result_exact"] for r in rows),
        "existing_native_schema_only_changes": sum(r["schema_only_change"] for r in rows),
        "native_unchanged": sum(r["native_exact"] for r in rows), "new_source_contracts": sorted(TARGETS),
        "fact_cases": sum(bool(r["fact_records"]) for r in rows),
        "facts": sum(len(v["facts"]) for r in rows for v in r["fact_records"].values()),
        "raw_anchors": sum(r["raw_anchors"] for r in rows), "saved_native_API_replays": 0 if no_api else 30,
        "synthetic_target_API_controls": sum(len(r["synthetic_API_controls"]) for r in rows),
        "real_model_calls": 0, "real_oauth_calls": 0, "DB_queries": 0, "new_slots": 0, "scientific_accuracy": None}
    f.verify(app)
    f.write(output / "result.json", {"summary": summary, "cases": rows})
    f.write(output / "bindings.json", {**app, **f.bindings([Path(__file__), PROTOCOL, OLD / "scope_closed_v01.json",
        OLD / "input_freeze_v01/manifest.json", f.ROOT / "pyproject.toml"])})
    f.manifest(output)
    print(json.dumps(summary), flush=True)


def history(output):
    from scripts import source_paraphrases_20261109 as old

    output.mkdir(parents=True, exist_ok=False)
    f.save(output / "executed_script.py", Path(__file__).read_bytes())
    corpus = old.read(old.CORPUS_BASE / "Q01/corpus.json")
    articles = old.read(old.CORPUS_BASE / "Q01/articles.json")
    settings, rows = f.configure(), []
    for n in range(1, 6):
        cid = f"Q{n:02}"
        result, _ = old.replay(old.read(old.CORPUS_BASE / cid / "boundaries.json"), settings, corpus, articles)
        require(result == read(old.BASE / "freeze_v01" / (cid + "_current.json")), "Historical full result changed")
        old.native(cid, result["trace"], settings, output)
        before = (old.BASE / "freeze_v01" / (cid + "_native_unsent.json")).read_bytes()
        after = (output / (cid + "_native_unsent.json")).read_bytes()
        rows.append({"id": cid, "full_result_exact": True, "native_exact": before == after,
                     "native_schema_only_change": schema_delta(before, after)})
        f.write(output / (cid + "_current.json"), result)
    corpus, articles = read(old.OLD / "corpus.json"), read(old.OLD / "articles.json")
    dataset = read(old.OLD / "cases.json")["cases"]
    for index, case in enumerate(dataset):
        result, _ = old.replay(old.unpack(read(old.OLD / f"cases/{index:03}_baseline.json"), corpus), settings, corpus, articles)
        require(result == read(old.BASE / f"freeze_v01/old/{index:03}.json"), "Old service result changed: " + case["id"])
        rows.append({"id": case["id"], "full_result_exact": True})
    summary = {"service_cases_exact": len(rows), "current_native_checks": 5, "current_cases": rows[:5], "real_model_calls": 0}
    f.write(output / "result.json", {"summary": summary, "cases": rows})
    f.write(output / "bindings.json", f.bindings([Path(__file__), old.BASE / "freeze_v01/manifest.json", *series.app_paths()]))
    f.manifest(output)
    print(json.dumps(summary), flush=True)


def package(output):
    output.mkdir(parents=True, exist_ok=False)
    source = output / "source"
    source.mkdir()
    for name in ("app", "scripts"):
        shutil.copytree(f.ROOT / name, source / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copy2(f.ROOT / "pyproject.toml", source / "pyproject.toml")
    done = subprocess.run([sys.executable, "-m", "pip", "wheel", ".", "--no-deps", "--no-index", "--no-build-isolation",
                           "--wheel-dir", str(output / "wheels")], cwd=source, capture_output=True)
    f.save(output / "build.stdout", done.stdout)
    f.save(output / "build.stderr", done.stderr)
    require(done.returncode == 0, "Wheel build failed")
    wheel, = (output / "wheels").glob("*.whl")
    installed = output / "installed"
    with zipfile.ZipFile(wheel) as archive:
        archive.extractall(installed)
    for path in series.app_paths():
        require(path.read_bytes() == (installed / path.relative_to(f.ROOT)).read_bytes(), "Wheel code/resource differs")
    driver = ("import sys,runpy; from pathlib import Path; sys.path.insert(0,sys.argv.pop(1)); "
              "from scripts import gigachat_answer_smoke as f; f.ROOT=Path(sys.argv.pop(1)); "
              "runpy.run_module('scripts.audit_answer_priorities_20261111',run_name='__main__')")
    command = [sys.executable, "-X", "utf8", "-B", "-c", driver, str(installed), str(f.ROOT), "compare", "--no-api",
        "--expected-app", str(installed / "app"), "--expected-comparison", str(BASE / "comparison_v01"),
        "--output", str(output / "comparison_v01")]
    done = subprocess.run(command, cwd=output, capture_output=True,
                          env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "GIGACHAT_CREDENTIALS": "offline-placeholder"})
    f.save(output / "replay.stdout", done.stdout)
    f.save(output / "replay.stderr", done.stderr)
    require(done.returncode == 0, "Installed app comparison failed")
    f.write(output / "result.json", {"wheel": str(wheel), "sha256": f.sha(wheel.read_bytes()),
        "app_resource_files_exact": len(series.app_paths()), "installed_cases_exact": 30})
    f.manifest(output)


def review(output):
    output.mkdir(parents=True, exist_ok=False)
    data = read(BASE / "comparison_v01/result.json")
    for name in ("comparison_v01", "history_v01", "wheel_v01", "catalogue_audit_v01", "pdf_probe_v01"):
        f.verify_manifest(BASE / name)
    suites = list(ET.parse(BASE / "full_v02.xml").getroot().iter("testsuite"))
    counts = {k: sum(int(s.get(k, "0")) for s in suites) for k in ("tests", "errors", "failures", "skipped")}
    require(counts["errors"] == counts["failures"] == 0, "Full suite not clean")
    links = []

    def link(path, text):
        require(path.is_file(), "Missing review link")
        links.append(str(path))
        return '<a href="' + html.escape(os.path.relpath(path, output).replace("\\", "/"), quote=True) + '">' + html.escape(text) + '</a>'

    rows = []
    for row in data["cases"]:
        selected = row["synthetic_controls"]
        answer = selected["selected"]["answer"] if selected else "Прежний свободный путь; новых ответов модели нет."
        execution = "SYNTHETIC F1, не ответ реальной модели." if selected else "Сохранён прежний путь подготовки; новый ответ отсутствует."
        details = '<details><summary>Факты, raw anchors и границы</summary><pre>' + html.escape(
            json.dumps(row, ensure_ascii=False, indent=2)) + '</pre></details>'
        rows.append('<tr data-case><td>' + row["id"] + '</td><td>' + html.escape(row["question"]) + '</td><td>'
            + ("Новый полный контракт" if row["id"] in TARGETS else "Прежний service result точен")
            + '</td><td>' + html.escape(answer) + '<p>' + execution + '</p>' + details + '</td></tr>')
    articles = read(series.CAPTURE / "articles.json")
    papers = []
    for a in articles.values():
        cells = []
        for key in ("title", "authors", "journal", "year", "abstract", "conclusions", "terms"):
            value = html.escape(str(a.get(key) or "Не собрано / отсутствует в snapshot"))
            if key in ("abstract", "conclusions", "terms"):
                value = '<details><summary>Полный snapshot: ' + key + '</summary><pre>' + value + '</pre></details>'
            cells.append('<td>' + value + '</td>')
        papers.append('<tr>' + ''.join(cells) + '<td>' + link(Path(a["pdf_path"]), "Исходный PDF") + '</td></tr>')
    summary = {**data["summary"], "pytest": counts, "history": read(BASE / "history_v01/result.json")["summary"],
        "wheel": read(BASE / "wheel_v01/result.json"), "glyphs": read(BASE / "catalogue_audit_v01/result.json"),
        "algorithm_version": "finite_complete_answer_source_binding_v0.1 + bounded_fact_selection_schema_v0.1",
        "comparison_result_sha256": f.sha((BASE / "comparison_v01/result.json").read_bytes()),
        "independent_set_status": "awaiting_user_questions_and_references", "independent_accuracy": None, "plan_percent": 75}
    body = ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>ARIADNE — приоритеты после прогона</title>'
        '<style>body{font:16px system-ui;margin:30px;color:#18333f}table{border-collapse:collapse;width:100%}'
        'td,th{border:1px solid #bcd;padding:8px;vertical-align:top}pre{white-space:pre-wrap;overflow-wrap:anywhere}'
        'details{max-width:70vw}input{padding:10px;margin:15px;width:65%}</style><h1>Офлайн-приоритеты после реального прогона</h1>'
        '<p>Native schema ограничивает число выборов и уникальность ID; клиентская проверка остаётся строгой. '
        'Три вопроса переведены на полный source-bound ответ либо отказ. Реальных model/OAuth/new slots0. '
        'Исторические семь duplicate-F1 ответов по-прежнему отклоняются; новый успех модели не измерен.</p>'
        '<p>Независимый набор предоставит пользователь. Протокол приёмки готов; случаев и независимых оценок пока нет. План75%.</p><p>'
        + ' · '.join([link(BASE / "full_v02.xml", "Полный pytest"), link(PROTOCOL, "Scope"),
                     link(f.ROOT / "docs/records/answer_priorities_independent_v0.1/README.md", "Независимая приёмка"),
                     link(OLD / "review_v02/review.html", "Неизменённый реальный прогон"),
                     *(link(BASE / "pdf_probe_v01" / (n + ".png"), "Свежий полный PDF " + n) for n in ("Kondo", "Nambu", "Peng"))])
        + '</p><details><summary>Итоги и ограничения</summary><pre>' + html.escape(json.dumps(summary, ensure_ascii=False, indent=2))
        + '</pre></details><label>Поиск<input id="search" type="search"></label><table><thead><tr><th>ID</th><th>Вопрос</th>'
        '<th>Изменение</th><th>Ответ и доказательства</th></tr></thead><tbody>' + ''.join(rows)
        + '</tbody></table><h2>Все три статьи: TAC snapshot</h2><table><thead><tr>'
        + ''.join('<th>' + k + '</th>' for k in
                  ("Title", "Authors", "Journal", "Year", "Abstract", "Conclusions", "Terms", "Original file"))
        + '</tr></thead><tbody>' + ''.join(papers) + '</tbody></table><p>Пределы: конечные грамматики на открытых development '
        'вопросах; не общая химическая/причинная/эпистемическая валидация. Новая native schema не проверена реальным '
        'провайдером. Свежий DB поиск и browser layout не измерены. Старые native ответы не исправлялись.</p><script>'
        'document.getElementById("search").addEventListener("input",e=>{const q=e.target.value.toLocaleLowerCase();'
        'document.querySelectorAll("[data-case]").forEach(r=>r.hidden=!r.textContent.toLocaleLowerCase().includes(q));});'
        '</script></html>')
    f.save(output / "review.html", body.encode())
    f.write(output / "report.json", {**summary, "HTML_case_rows": len(rows), "HTML_articles": len(papers), "local_links": len(links)})
    f.write(output / "bindings.json", f.bindings([Path(__file__), PROTOCOL, BASE / "full_v02.xml",
        *(BASE / n / "manifest.json" for n in ("comparison_v01", "history_v01", "wheel_v01", "catalogue_audit_v01", "pdf_probe_v01"))]))
    f.manifest(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("compare", "history", "package", "review"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--no-api", action="store_true")
    parser.add_argument("--expected-app", type=Path)
    parser.add_argument("--expected-comparison", type=Path)
    args = parser.parse_args()
    if args.expected_app:
        import app
        require(Path(app.__file__).resolve().parent == args.expected_app.resolve(), "Application import escaped wheel")
    policy = f.NetworkPolicy()
    sys.addaudithook(policy)
    if args.mode == "compare":
        compare(args.output.resolve(), no_api=args.no_api, expected_comparison=args.expected_comparison)
    else:
        {"history": history, "package": package, "review": review}[args.mode](args.output.resolve())
    require(not policy.denied, "Unexpected external network attempt")


if __name__ == "__main__":
    main()
