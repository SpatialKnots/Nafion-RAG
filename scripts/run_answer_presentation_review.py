"""Render frozen answers before/after and build unsent prompt candidates, without DB or network."""

from __future__ import annotations

import argparse
import html
import json
import sys
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import gigachat_answer_smoke as files  # noqa: E402


def no_network(event: str, args: Any) -> None:
    if event in {"socket.connect", "socket.getaddrinfo", "socket.sendto"}:
        raise AssertionError("All network forbidden during presentation review")


def load_snapshot(name: str, path: Path) -> ModuleType:
    module = ModuleType(name)
    sys.modules[name] = module
    module.__file__ = str(path)
    exec(compile(path.read_bytes(), str(path), "exec"), module.__dict__)
    return module


def run(output: Path) -> dict[str, Any]:
    import fitz
    from sqlalchemy.engine import Engine

    from app import ui
    from app.generation.gigachat import AUTH_URL, CHAT_URL, GigaChatAnswerProvider, _Answer, _json
    from app.generation.presentation import VERSION, capture_sources
    from app.generation.providers import Evidence
    from app.retrieval.search import SearchResponse, SearchResult

    if output.exists():
        raise FileExistsError(output)
    before = ROOT / "output/answer_presentation_20261030/before"
    prior_hashes = json.loads((before / "manifest.json").read_bytes())
    for name, digest in prior_hashes.items():
        if files.sha((before / name).read_bytes()) != digest:
            raise ValueError("Before-code snapshot changed")
    old_ui = load_snapshot("presentation_before_ui", before / "app/ui.py")
    old_provider = load_snapshot("presentation_before_gigachat", before / "app/generation/gigachat.py")
    if old_provider._Answer.model_json_schema() != _Answer.model_json_schema():
        raise ValueError("Answer JSON Schema changed")
    batch = ROOT / "output/gigachat_answer_batch_20261029_v02/cases"
    sources = [("swelling", ROOT / "output/user_swelling_answer_20261029"),
               ("measurement_conditions", batch / "measurement_conditions"),
               ("equilibrium_comparison", batch / "equilibrium_comparison")]
    support = ["app/ui.py", "app/generation/presentation.py", "app/generation/gigachat.py",
               "tests/unit/test_answer_presentation.py", "tests/unit/test_ui_routes.py",
               "tests/unit/test_gigachat_generation.py", "scripts/run_answer_presentation_review.py",
               "docs/records/answer_presentation_protocol_v0.1.md", "output/answer_presentation_tests_20261030_v03.xml"]
    bindings = files.bindings([ROOT / p for p in support] + [before / "manifest.json", *[before / n for n in prior_hashes]])
    output.mkdir(parents=True, exist_ok=False)
    cases, articles, verified_pages = [], {}, {}

    with patch.object(Engine, "connect", side_effect=AssertionError("DB forbidden")) as db_guard:
        for case_id, folder in sources:
            prepared, live = folder / "prepared", folder / "live"
            files.verify_manifest(prepared)
            files.verify_manifest(live)
            inputs = [prepared / n for n in ("api_request.json", "request.json", "trace.json", "sources.json", "articles.json")]
            inputs += [live / "api_response.json", live / "response.bin", live / "request.json"]
            bindings.update(files.bindings(inputs))
            if (live / "request.json").read_bytes() != (prepared / "request.json").read_bytes():
                raise ValueError("Historical prepared/live request differs")
            api = json.loads((live / "api_response.json").read_bytes())
            if api["http_status"] != 200 or api["body"]["status"] != "answered":
                raise ValueError("Declared successful-answer inventory differs")
            original_api = deepcopy(api)
            request = json.loads((prepared / "api_request.json").read_bytes())
            old_request = json.loads((prepared / "request.json").read_bytes())
            trace = json.loads((prepared / "trace.json").read_bytes())
            registry = json.loads((prepared / "sources.json").read_bytes())
            retrieval = SearchResponse(query=trace["retrieval"]["query"], metadata=trace["retrieval"]["metadata"],
                                       results=[SearchResult(**r) for r in trace["retrieval"]["results"]])
            evidence = [Evidence(**e) for e in trace["evidence"]]
            contexts = capture_sources(retrieval, evidence)
            for page in registry["pages"].values():
                pdf = Path(page["original_pdf_path"])
                if files.sha(pdf.read_bytes()) != page["original_pdf_sha256"]:
                    raise ValueError("Original PDF changed")
                bindings.update(files.bindings([pdf]))
                key = (str(pdf), page["page_number"])
                if key not in verified_pages:
                    with fitz.open(pdf) as document:
                        extracted = document[page["page_number"] - 1].get_text("text")
                    if extracted != page["page_text"]:
                        raise ValueError("Fresh PDF page extraction differs")
                    verified_pages[key] = files.sha(extracted.encode())
            current_articles = json.loads((prepared / "articles.json").read_bytes())
            for article in current_articles:
                articles.setdefault(article["article_id"], []).append(article)

            active = GigaChatAnswerProvider(credentials="offline-not-a-credential", scope="GIGACHAT_API_PERS",
                model=old_request["model"], timeout_seconds=120, max_tokens=old_request["max_tokens"])
            raw = (live / "response.bin").read_bytes()
            requests: list[dict[str, Any]] = []
            placeholders: list[str] = []

            def post(url: str, body: bytes, authorization: str, *, oauth: bool = False,
                     responses: list[str] = placeholders, captured: list[dict[str, Any]] = requests, native: bytes = raw) -> bytes:
                if url != (AUTH_URL if oauth else CHAT_URL):
                    raise ValueError("Unexpected offline boundary URL")
                responses.append("oauth_placeholder" if oauth else "saved_native_response")
                if oauth:
                    return b'{"access_token":"offline-placeholder"}'
                captured.append(_json(body))
                return native

            with patch.object(active, "_post", post):
                parsed = active.generate(request["question"], evidence, answer_style=request["answer_style"],
                                         answer_language=request["answer_language"])
            if placeholders != ["oauth_placeholder", "saved_native_response"]:
                raise ValueError("Offline replay boundary count differs")
            if [asdict(c) for c in parsed.claims] != api["body"]["claims"] or not parsed.answerable:
                raise ValueError("Saved native claims differ under current parser")
            candidate = requests[0]
            unchanged = deepcopy(candidate)
            unchanged["messages"][1]["content"] = old_request["messages"][1]["content"]
            if unchanged != old_request:
                raise ValueError("Changes extend beyond the declared user-prompt instruction")
            if candidate == old_request:
                raise ValueError("Presentation instruction did not change prompt")
            files.write(output / (case_id + "_unsent_request.json"), candidate)

            original_html = old_ui._answer_payload_panel(api["body"], request["question"])
            current_html = ui._answer_payload_panel(api["body"], request["question"], contexts)
            files.save(output / (case_id + "_before_runtime.html"), old_ui._layout("Before", original_html).body)
            files.save(output / (case_id + "_after_runtime.html"), ui._layout("After", current_html).body)
            # Offline review copy: map links only to registered local PDFs. Actual runtime markup stays above.
            page_paths = {p["article_id"]: Path(p["original_pdf_path"]) for p in registry["pages"].values()}

            def rewrite_pdf_urls(document: str, citations: list[dict[str, Any]] = api["body"]["citations"],
                                 paths: dict[str, Path] = page_paths) -> str:
                for cid in citations:
                    pdf = paths[cid["article_id"]].as_uri()
                    url = cid.get("pdf_page_url")
                    if isinstance(url, str):
                        document = document.replace(html.escape(url, quote=True), html.escape(
                            pdf + "#page=" + str(cid["page_start"]), quote=True))
                return document

            for state, module, fragment in (("before", old_ui, original_html), ("after", ui, current_html)):
                markup = module._layout("ARIADNE — " + case_id + " — " + state, fragment).body.decode()
                files.save(output / (case_id + "_" + state + ".html"), rewrite_pdf_urls(markup).encode())
            if api != original_api:
                raise ValueError("Original API payload was mutated")
            cases.append({"id": case_id, "question": request["question"], "original_api": api,
                "source_registry": registry, "presentation_sources": {k: asdict(v) for k, v in contexts.items()},
                "old_request_sha256": files.sha((prepared / "request.json").read_bytes()),
                "unsent_request_sha256": files.sha(files.encode(candidate)), "candidate_sent": False,
                "changed_fields": ["messages[1].content"], "schema_and_limits_unchanged": True,
                "saved_native_claims_unchanged": True, "api_payload_unchanged": True,
                "offline_transport_placeholders": placeholders,
                "display_only_link_mapping": "Registered PDF file URLs only; other application routes require the running app."})
        if db_guard.call_count:
            raise ValueError("DB connection attempted")

    # Copy existing brand images for an optional local static preview; no generated media.
    assets = output / "ui/assets/brand"
    assets.mkdir(parents=True)
    for path in (ROOT / "app/static/brand").glob("*.png"):
        files.save(assets / path.name, path.read_bytes())
    summary = {"answers": len(cases), "native_replays_identical": len(cases), "unsent_prompt_candidates": len(cases),
        "fresh_pdf_pages_verified": len(verified_pages), "source_documents": len(articles), "db_connections": 0,
        "model_calls": 0, "oauth_calls": 0, "new_model_behaviour": "untested", "scientific_acceptance": "not_established"}
    report = {"version": VERSION, "bindings": bindings, "summary": summary, "cases": cases, "articles": articles,
        "before_source_hashes": prior_hashes,
        "declared_application_drift": {name: {"before": digest, "current": files.sha((ROOT / name).read_bytes())}
            for name, digest in prior_hashes.items() if name.startswith("app/")},
        "historical_dependencies": "Original output manifests/source snapshots retained; current application code intentionally differs.",
        "coverage_limit": "Presentation and prompt instruction implemented; new model content/semantic behaviour not evaluated."}
    files.verify(bindings)
    files.write(output / "report.json", report)
    render_index(report, output)
    for name in support:
        destination = output / "source_snapshot" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        files.save(destination, (ROOT / name).read_bytes())
    files.write(output / "manifest.json", {"version": VERSION, "outputs": {
        p.relative_to(output).as_posix(): files.sha(p.read_bytes()) for p in sorted(output.rglob("*"))
        if p.is_file() and p.name != "manifest.json"}})
    return summary


def render_index(report: dict[str, Any], output: Path) -> None:
    def esc(value: Any) -> str:
        return html.escape(str(value), quote=True)

    def detail(label: str, value: Any) -> str:
        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)
        return '<details><summary>' + esc(label) + '</summary><pre>' + esc(text) + '</pre></details>'

    body = ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>ARIADNE — представление ответа</title>'
        '<style>body{font:16px system-ui;margin:24px;color:#18333f}table{border-collapse:collapse;width:100%}'
        'td,th{border:1px solid #abc;padding:8px;vertical-align:top}pre{white-space:pre-wrap;overflow-wrap:anywhere}'
        '[hidden]{display:none!important}</style><h1>Представление сохранённых ответов</h1><p>Algorithm: '
        + esc(report["version"]) + '; bindings SHA256: ' + files.sha(files.encode(report["bindings"]))
        + '.</p><p>Исходные ответы и статусы не исправлены. 1.54 остаётся историческим ошибочным общим максимумом; '
        'новое оформление не подтверждает его. Новых model/OAuth/DB calls — 0. '
        'Три новых prompt candidates не отправлены; содержательность будущих ответов модели не проверена.</p>'
        '<p>Ссылки PDF в локальных копиях ведут к зарегистрированным файлам. '
        'Другие ссылки приложения требуют запущенный сервер; runtime HTML сохранён отдельно без подмены URL.</p>')
    for case in report["cases"]:
        body += ('<section><h2>' + esc(case["question"]) + '</h2><p><a href="' + case["id"] + '_before.html">До</a> · '
            '<a href="' + case["id"] + '_after.html">После</a> · <a href="' + case["id"]
            + '_unsent_request.json">Неотправленный запрос</a></p>' + detail("Исходный ответ API без изменений", case["original_api"])
            + detail("Привязка полных контекстов и ограничения", case["presentation_sources"]) + '</section>')
    body += ('<h2>TAC: все работы трёх сохранённых ответов</h2><p>Архивные метаданные, не independent accuracy. '
        'Conclusions/Terms на этом этапе не собирались. Все версии метаданных сохранены.</p>'
        '<label>Поиск <input type="search" id="q"></label><table id="tac"><thead><tr>'
        + ''.join('<th>' + s + '</th>' for s in ('Title', 'Authors', 'Journal', 'Year', 'Abstract', 'Conclusions', 'Terms',
                                               'hyperlink to original file')) + '</tr></thead><tbody>')
    for values in report["articles"].values():
        a = values[0]
        body += '<tr>'
        for key in ('title', 'authors', 'journal', 'year', 'abstract', 'conclusions', 'terms'):
            value = a.get(key)
            if value is None:
                content = 'Неизвестно / не собрано'
            elif key in {"abstract", "conclusions", "terms"}:
                content = detail("Полное значение", value)
            else:
                content = esc(value if isinstance(value, (str, int)) else json.dumps(value, ensure_ascii=False))
            body += '<td>' + content + '</td>'
        body += ('<td><a href="' + esc(Path(a["original_pdf_path"]).as_uri()) + '">Оригинальный PDF</a>'
                 + detail("Все зарегистрированные варианты метаданных", values) + '</td></tr>')
    body += ('</tbody></table>' + detail("Итоги и ограничения", report["summary"])
        + '<script>document.getElementById("q").addEventListener("input",e=>{const s=e.target.value.toLowerCase();'
        'document.querySelectorAll("#tac tbody tr").forEach(r=>{r.hidden=!r.textContent.toLowerCase().includes(s)})});</script></html>')
    files.save(output / "review.html", body.encode())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sys.addaudithook(no_network)
    print(json.dumps(run(args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
