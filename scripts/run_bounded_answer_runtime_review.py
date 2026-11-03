"""Actual offline ASGI checks with substituted GigaChat transport, never live calls."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import gigachat_answer_smoke as files  # noqa: E402

PROTOCOL = ROOT / "docs/records/bounded_answer_runtime_protocol_v0.1.md"


def history(stage: Path) -> dict[str, Any]:
    before = json.loads((stage / "before_bindings.json").read_bytes())
    snapshots = {str(Path(k).resolve()): Path(v) for k, v in before["snapshot_paths"].items()}
    old = json.loads((ROOT / "output/user_questions_20261030/live_review_v01/report.json").read_bytes())
    drift = []
    for name, digest in old["bindings"].items():
        path = Path(name)
        current = files.sha(path.read_bytes())
        if current == digest:
            continue
        if name not in snapshots or files.sha(snapshots[name].read_bytes()) != digest:
            raise ValueError(f"Undeclared historical drift: {path}")
        drift.append({"path": name, "original_sha256": digest, "current_sha256": current,
                      "original_snapshot": str(snapshots[name])})
    return {"historical_binding_count": len(old["bindings"]), "declared_app_drift": drift,
            "old_current_code_guard": "expected_to_reject_stale_candidates_not_modified"}


def run(stage: Path, prepared: Path, output: Path) -> dict[str, Any]:
    import fitz
    from fastapi.testclient import TestClient
    from sqlalchemy.engine import Engine

    import app.main as main
    from app.core.config import Settings
    from app.db.session import get_session
    from app.generation import service
    from app.generation.gigachat import AUTH_URL, CHAT_URL, GigaChatAnswerProvider
    from app.generation.presentation import capture_sources
    from app.retrieval.search import SearchResponse, SearchResult
    from app.ui import _answer_payload_panel

    if output.exists():
        raise FileExistsError(output)
    historical = history(stage)
    before_inputs = [stage / "before_bindings.json", *(stage / "before").glob("*.py")]
    paths = [*ROOT.glob("app/**/*.py"), Path(__file__), PROTOCOL, *before_inputs,
             ROOT / "tests/unit/test_lithiation_overview.py", ROOT / "tests/unit/test_comparison_scope_runtime.py",
             ROOT / "scripts/lithiation_subject_context_audit.py", ROOT / "scripts/lithiation_operation_audit.py",
             ROOT / "scripts/event_value_ownership_audit.py"]
    bindings = files.bindings(paths)
    articles, pages, frozen = {}, {}, {}
    for case_id in ("q1_swelling_forms", "q2_best_mixture", "q3_lithiation_methods"):
        folder = prepared / case_id / "prepared"
        files.verify_manifest(folder)
        bindings.update(files.bindings([p for p in folder.iterdir() if p.is_file()]))
        frozen[case_id] = {"request": json.loads((folder / "api_request.json").read_bytes()),
                           "trace": json.loads((folder / "trace.json").read_bytes())}
        for article in json.loads((folder / "articles.json").read_bytes()):
            articles[article["article_id"]] = article
        for page in json.loads((folder / "sources.json").read_bytes())["pages"].values():
            pages[(page["article_id"], page["page_number"])] = page
    for page in pages.values():
        original, layer = Path(page["original_pdf_path"]), Path(page["layer_pdf_path"])
        if files.sha(original.read_bytes()) != page["original_pdf_sha256"]:
            raise ValueError("Original PDF drift")
        with fitz.open(layer) as pdf:
            if pdf[page["page_number"] - 1].get_text() != page["page_text"]:
                raise ValueError("Fresh page extraction drift")
        bindings.update(files.bindings([original, layer]))
    settings = Settings(_env_file=None, gigachat_credentials="synthetic-offline", rag_model="GigaChat-2-Max",
                        rag_provider="gigachat", rag_top_k=5, rag_gigachat_max_tokens=1200, rag_timeout_seconds=120)
    original_answer = main.answer_question
    rows = []
    requests = [(case_id, "select_exact", None, 200) for case_id in frozen]
    requests += [("q1_swelling_forms", "old_bad_answer", None, 502),
                 ("q3_lithiation_methods", "invent_duration", None, 502),
                 ("q3_lithiation_methods", "abstain", None, 200),
                 ("q3_lithiation_methods", "select_exact", "Методики литирования Nafion: литирования не проводили.", 200)]
    original_overrides = dict(main.app.dependency_overrides)
    main.app.dependency_overrides[get_session] = lambda: object()
    try:
        for case_id, mode, constructed_text, expected_http in requests:
            trace = frozen[case_id]["trace"]
            retrieval = SearchResponse(query=trace["retrieval"]["query"],
                results=[SearchResult(**r) for r in trace["retrieval"]["results"]], metadata=trace["retrieval"]["metadata"])
            if constructed_text:
                from dataclasses import replace
                retrieval = SearchResponse(query=retrieval.query,
                    results=[replace(retrieval.results[0], snippet=constructed_text, full_text=constructed_text)], metadata={})
            captured, transport = {}, []

            def traced(*args: Any, _captured: dict[str, Any] = captured, **kwargs: Any) -> Any:
                def observe(received: Any, e: Any, m: Any) -> None:
                    _captured.update({"retrieval": received, "evidence": e, "metadata": m})
                return original_answer(*args, **kwargs, trace_observer=observe)

            def fake_post(self: Any, url: str, body: bytes, authorization: str, *, oauth: bool = False,
                          _transport: list[dict[str, Any]] = transport, _mode: str = mode, _case_id: str = case_id,
                          _captured: dict[str, Any] = captured) -> bytes:
                if self.credentials != "synthetic-offline":
                    raise ValueError("Offline settings lost")
                _transport.append({"url": url, "request": json.loads(body) if not oauth else "synthetic_oauth_only",
                                   "request_sha256": files.sha(body), "request_bytes": len(body),
                                   "request_raw_utf8": body.decode("utf-8") if not oauth else None})
                if url == AUTH_URL and oauth:
                    return b'{"access_token":"synthetic-token"}'
                if url != CHAT_URL or oauth:
                    raise ValueError("Unexpected substituted endpoint")
                native = json.loads(body)
                schema = native["response_format"]["schema"]
                allowed = schema["$defs"]["_Claim"]["properties"]["text"]["enum"]
                text = allowed[0]
                if _mode == "old_bad_answer":
                    old = json.loads((prepared / _case_id / "live/api_response.json").read_bytes())
                    text = old["body"]["claims"][-1]["text"]
                elif _mode == "invent_duration":
                    text = "Для литирования Nafion требуется 2 ч: это полный протокол."
                content = {"answerable": _mode != "abstain", "claims": [] if _mode == "abstain" else
                           [{"text": text, "citation_ids": [_captured["evidence"][0].citation_id]}]}
                _transport[-1]["synthetic_response_content"] = content
                _transport[-1]["native_schema_expected_valid"] = _mode in {"select_exact", "abstain"}
                return json.dumps({"choices": [{"finish_reason": "stop", "message": {
                    "role": "assistant", "content": json.dumps(content, ensure_ascii=False)}}]}, ensure_ascii=False).encode()

            with patch.object(main, "get_settings", lambda: settings), patch.object(main, "answer_question", traced), \
                    patch.object(service, "search_chunks", lambda *a, _retrieval=retrieval, **kw: _retrieval), \
                    patch.object(GigaChatAnswerProvider, "_post", fake_post), \
                    patch.object(Engine, "connect", side_effect=AssertionError("DB forbidden")):
                with TestClient(main.app) as client:
                    result = client.post("/answer", json=frozen[case_id]["request"])
            if result.status_code != expected_http:
                raise ValueError(f"Unexpected HTTP result: {case_id}/{mode}: {result.status_code}: {result.text}")
            body = result.json()
            if case_id == "q2_best_mixture" or constructed_text:
                if transport or body["status"] != "insufficient_evidence":
                    raise ValueError("Gate must stop before provider")
            if mode == "abstain" and body["status"] != "insufficient_evidence":
                raise ValueError("Abstention changed")
            if expected_http == 200 and mode == "select_exact" and not constructed_text and case_id != "q2_best_mixture":
                if body["status"] != "answered" or len(transport) != 2:
                    raise ValueError("Expected bounded selection")
            panel = _answer_payload_panel(body, frozen[case_id]["request"]["question"],
                                          presentation_sources=capture_sources(captured["retrieval"], captured["evidence"]))
            panel = local_pdf_links(panel, body.get("citations", []), articles)
            rows.append({"id": case_id + ":" + mode + (":constructed_negative" if constructed_text else ""),
                         "question": frozen[case_id]["request"]["question"], "http_status": result.status_code,
                         "body": body, "synthetic_transport": transport, "panel_html": panel,
                         "origin": "synthetic_offline_selection_not_actual_model_answer",
                         "constructed_source": constructed_text})
            print(json.dumps({"id": rows[-1]["id"], "http": result.status_code, "fake_transport_calls": len(transport)}), flush=True)
    finally:
        main.app.dependency_overrides.clear()
        main.app.dependency_overrides.update(original_overrides)
    originals = {case_id: json.loads((prepared / case_id / "live/api_response.json").read_bytes())
                 for case_id in ("q1_swelling_forms", "q2_best_mixture")}
    for case_id in originals:
        bindings.update(files.bindings([prepared / case_id / "live/api_response.json"]))
    summary = {"asgi_cases": len(rows), "http_statuses": [r["http_status"] for r in rows],
               "fake_transport_calls": sum(len(r["synthetic_transport"]) for r in rows),
               "real_model_oauth_db_calls": 0, "new_live_slots": 0, "fresh_pages": len(pages), "tac_works": len(articles),
               "runtime_changes": True, "independent_accuracy": None, "new_native_enum_provider_support": "untested_live"}
    report = {"version": "bounded_answer_runtime_v0.1", "bindings": bindings, "historical": historical,
              "rows": rows, "original_actual_answers": originals, "articles": articles,
              "summary": summary, "scientific_acceptance": "not_established"}
    files.verify(bindings)
    output.mkdir(parents=True)
    files.write(output / "report.json", report)
    render(report, output)
    (output / "source_snapshot").mkdir()
    for path in [Path(__file__), PROTOCOL, *ROOT.glob("app/generation/*.py")]:
        files.save(output / "source_snapshot" / path.name, path.read_bytes())
    files.manifest(output)
    return summary


def local_pdf_links(panel: str, citations: list[dict[str, Any]], articles: dict[str, Any]) -> str:
    """Offline review only; registered files replace app-navigation URLs."""
    def replace_link(match: re.Match[str]) -> str:
        href = html.unescape(match["href"])
        for citation in citations:
            article_id = citation["article_id"]
            if href.startswith((f"/articles/{article_id}/", f"/ui/articles/{article_id}/")) or href == f"/ui/articles/{article_id}":
                article = articles[article_id]
                url = Path(article["original_pdf_path"]).as_uri() + '#page=' + str(citation["page_start"])
                return 'href=' + match["quote"] + html.escape(url, quote=True) + match["quote"]
        return match.group()
    return re.sub(r"href=(?P<quote>['\"])(?P<href>[^'\"]+)(?P=quote)", replace_link, panel)


def render(report: dict[str, Any], output: Path) -> None:
    def esc(value: Any) -> str:
        return html.escape(str(value), quote=True)

    def detail(label: str, value: Any) -> str:
        return ('<details><summary>' + esc(label) + '</summary><pre>'
                + esc(json.dumps(value, ensure_ascii=False, indent=2)) + '</pre></details>')

    body = ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>ARIADNE — bounded runtime</title>'
            '<style>body{font:16px system-ui;margin:24px;color:#18333f}table{border-collapse:collapse;width:100%}'
            'td,th{border:1px solid #abc;padding:8px;vertical-align:top}pre{white-space:pre-wrap;overflow-wrap:anywhere}'
            '.source-exact{white-space:pre-wrap;max-height:30rem;overflow:auto}[hidden]{display:none!important}</style>'
            '<h1>Три runtime-исправления: синтетическая offline-проверка</h1><p>Новых реальных ответов GigaChat здесь нет. '
            'Transport полностью подставной; ASGI /answer, parser, schema и local validation настоящие. '
            'Q1 arithmetic вычисляет система; GigaChat в новом контракте выбирает готовый текст. Q3 выбирает точные '
            'атрибутированные цитаты. Q2 отклоняется из-за неподтверждённой области optimum.</p>'
            + detail("Неизменённые прежние реальные ответы", report["original_actual_answers"])
            + detail("Объявленный current-code drift и original snapshots", report["historical"]))
    for row in report["rows"]:
        body += '<h2>' + esc(row["id"]) + '</h2><p>Синтетический выбор, не новый model output.</p>'
        body += row["panel_html"] + detail("Полный ASGI/transport result", {k: v for k, v in row.items() if k != "panel_html"})
    body += ('<h2>TAC: все пять работ</h2><label>Поиск <input id="q" type="search"></label><table id="tac"><thead><tr>'
             + ''.join('<th>' + h + '</th>' for h in ('Title', 'Authors', 'Journal', 'Year', 'Abstract', 'Conclusions',
                                                    'Terms', 'hyperlink to original file')) + '</tr></thead><tbody>')
    for article in report["articles"].values():
        body += '<tr>'
        for key in ('title', 'authors', 'journal', 'year', 'abstract', 'conclusions', 'terms'):
            value = article.get(key)
            body += '<td>' + (detail("Полный текст / metadata", value) if value is not None else 'Неизвестно / не собрано') + '</td>'
        body += ('<td><a href="' + esc(Path(article["original_pdf_path"]).as_uri()) + '">Оригинальный PDF</a>'
                 + detail("Provenance", article) + '</td></tr>')
    body += ('</tbody></table>' + detail("Итоги", report["summary"])
             + '<script>document.getElementById("q").addEventListener("input",e=>{const s=e.target.value.toLowerCase();'
             'document.querySelectorAll("#tac tbody tr").forEach(r=>r.hidden=!r.textContent.toLowerCase().includes(s))});'
             '</script></html>')
    files.save(output / "review.html", body.encode())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.stage, args.prepared, args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
