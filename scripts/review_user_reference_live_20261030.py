"""Offline replay and separate post-hoc review of the one authorized reference case."""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import gigachat_answer_smoke as files  # noqa: E402


def run(stage: Path, output: Path, policy: files.NetworkPolicy) -> dict[str, Any]:
    import fitz
    from fastapi.testclient import TestClient
    from sqlalchemy.engine import Engine

    from app.db.session import get_session
    from app.generation import service
    from app.generation.gigachat import AUTH_URL, CHAT_URL, GigaChatAnswerProvider, _json
    from app.main import app
    from app.retrieval.search import SearchResponse, SearchResult

    if output.exists():
        raise FileExistsError(output)
    prepared = stage / "preparation_v01"
    approved = stage / "authorized_run_v01/authorized_inputs"
    live = stage / "authorized_run_v01/live"
    reference = stage / "review_v01"
    for folder in (prepared, approved, live, reference):
        files.verify_manifest(folder)
    contract = json.loads((approved / "contract.json").read_bytes())
    files.verify(contract["input_bindings"])
    source_review = json.loads((reference / "report.json").read_bytes())
    files.verify(source_review["bindings"])
    result = json.loads((live / "result.json").read_bytes())
    api = json.loads((live / "api_response.json").read_bytes())
    trace = json.loads((live / "trace.json").read_bytes())
    sources = json.loads((live / "sources.json").read_bytes())
    original = json.loads((prepared / "user_reference_original.json").read_bytes())
    case, = original["cases"]
    if (result["model_attempts"], result["oauth_attempts"], result["automatic_retries"], result["fallbacks"]) != (1, 1, 0, 0):
        raise ValueError("Observed call inventory differs from one-call authorization")
    if result.get("postflight_input_hashes") != "verified":
        raise ValueError("Live postflight bindings were not verified")
    for name in ("request.json", "trace.json", "sources.json", "articles.json"):
        if (live / name).read_bytes() != (prepared / name).read_bytes():
            raise ValueError("Actual input/source drift: " + name)
    slot = files.LEDGER / contract["request_sha256"]
    for name in ("attempt.json", "result.json"):
        if (slot / name).read_bytes() != (live / name).read_bytes():
            raise ValueError("Append-only slot differs: " + name)
    raw = (live / "response.bin").read_bytes()
    native = _json(raw)
    if native["choices"][0]["finish_reason"] != "stop":
        raise ValueError("Unexpected native finish reason")
    retrieval = SearchResponse(query=trace["retrieval"]["query"], metadata=trace["retrieval"]["metadata"],
                               results=[SearchResult(**row) for row in trace["retrieval"]["results"]])
    called = []

    def post(self: Any, url: str, body: bytes, authorization: str, *, oauth: bool = False) -> bytes:
        if url != (AUTH_URL if oauth else CHAT_URL):
            raise ValueError("Unexpected offline endpoint")
        called.append("oauth_placeholder" if oauth else "saved_native_response")
        if oauth:
            return b'{"access_token":"offline-replay-placeholder"}'
        if body != (prepared / "request.json").read_bytes():
            raise ValueError("Offline native request differs")
        return raw

    def no_session():
        yield object()

    previous = dict(app.dependency_overrides)
    app.dependency_overrides[get_session] = no_session
    try:
        with patch.object(service, "search_chunks", return_value=retrieval), patch.object(
                GigaChatAnswerProvider, "_post", post), patch.object(
                Engine, "connect", side_effect=AssertionError("DB forbidden in offline replay")) as guard:
            with TestClient(app) as client:
                response = client.post("/answer", json=json.loads((prepared / "api_request.json").read_bytes()))
            if guard.call_count:
                raise ValueError("DB connection attempted")
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)
    if response.status_code != api["http_status"] or response.json() != api["body"]:
        raise ValueError("Offline ASGI complete status/body differs")
    if called != ["oauth_placeholder", "saved_native_response"] or policy.denied:
        raise ValueError("Unexpected offline transport inventory")
    verified_pages = []
    for page in sources["pages"].values():
        with fitz.open(page["original_pdf_path"]) as pdf:
            fresh = pdf[page["page_number"] - 1].get_text("text")
        if fresh != page["page_text"] or files.sha(fresh.encode()) != page["page_text_sha256"]:
            raise ValueError("Original selected PDF page differs")
        verified_pages.append({"original_pdf_path": page["original_pdf_path"], "page": page["page_number"]})
    for row in source_review["source_observations"]:
        with fitz.open(row["original_pdf_path"]) as pdf:
            fresh = pdf[row["pdf_page"] - 1].get_text("text")
        if fresh[row["start"]:row["end"]] != row["exact_text"]:
            raise ValueError("Kim source window differs")
    claims = api["body"]["claims"]
    if len(claims) != 2 or claims[0]["citation_ids"] != ["E1"] or claims[1]["citation_ids"] != ["E4"]:
        raise ValueError("Actual output changed; assessment needs separate review")
    coverage = [{"reference_item_verbatim": item, "assessment": "not_addressed",
                 "basis": "Neither output claim describes this particle morphology/transition or its dimensions.",
                 "origin": "assistant_posthoc_comparison_not_independent_expert_score"}
                for item in case["expected_answer_verbatim"].splitlines()]
    assessment = {
        "origin": "assistant_posthoc_comparison_of_external_user_reference_and_original_model_answer",
        "case_verdict": "does_not_answer_requested_particle_morphology",
        "first_claim": "It appends a membrane decomposition-temperature comparison to the opening morphology phrase; "
                       "the cited thermal observation does not describe particle shape or structure.",
        "second_claim": "It discusses Li-Nafion membrane swelling rather than dispersed-particle morphology.",
        "reference_item_review": coverage,
        "retrieval_observation": "Kim2015 is absent from the actual five selected fragments; "
                                 "the exact earlier loss stage (candidate retrieval/ranking/window) is not localized here.",
        "adequacy_observation": "The gate admitted sufficient_distinctive_term_coverage despite its matched_terms "
                                "omitting морфология and частиц; lexical coverage did not establish requested-information coverage.",
        "generation_observation": "The model returned answerable=true and the runtime accepted the off-target claims.",
        "reference_caveats": "Na-form/2.5wt%/ratio-versus-concentration/NMF notes remain separately preserved; "
                             "the user's original reference was not rewritten or sent to inference.",
        "scientific_scores": None,
        "general_accuracy": None,
        "independent_expert_acceptance": "not_established",
        "independence_limits": source_review["summary"]["independence"],
    }
    bound_paths = [Path(__file__), *[p for folder in (prepared, approved, live, reference, slot)
                                   for p in folder.iterdir() if p.is_file()]]
    bindings = {**contract["input_bindings"], **source_review["bindings"], **files.bindings(bound_paths)}
    summary = {"version": "external_user_reference_live_review_v0.1", "reference_cases": 1,
               "http_status": api["http_status"], "runtime_status": api["body"]["status"],
               "model_attempts": 1, "oauth_attempts": 1, "automatic_retries": 0, "fallbacks": 0,
               "returned_model": result["returned_model"], "finish_reason": native["choices"][0]["finish_reason"],
               "usage": result["usage"], "request_bytes": contract["request_bytes"],
               "request_sha256": contract["request_sha256"], "native_response_sha256": files.sha(raw),
               "offline_replay": "identical_http_status_and_complete_body", "offline_real_model_oauth_db_calls": 0,
               "selected_original_pages_freshly_verified": len(verified_pages), "reference_windows_verified": 8,
               "tac_works": len(source_review["articles"]), "case_verdict": assessment["case_verdict"],
               "scientific_scores": None, "general_accuracy": None, "plan_completion_percent": 75,
               "new_slot_status": "consumed_closed_no_resend", "monetary_cost": None}
    report = {"summary": summary, "bindings": bindings, "user_original": original, "assessment": assessment,
              "original_api": api, "original_native": native, "original_result": result,
              "original_trace": trace, "original_sources": sources, "verified_selected_pages": verified_pages,
              "separate_assistant_source_notes": source_review["source_observations"],
              "articles": source_review["articles"], "known_topic_overlap": source_review["known_topic_overlap"]}
    files.verify(bindings)
    output.mkdir(parents=True)
    files.write(output / "report.json", report)
    render(report, output)
    (output / "source_snapshot").mkdir()
    files.save(output / "source_snapshot" / Path(__file__).name, Path(__file__).read_bytes())
    files.manifest(output)
    return summary


def render(report: dict[str, Any], output: Path) -> None:
    def esc(value: Any) -> str:
        return html.escape(str(value), quote=True)

    def detail(label: str, value: Any) -> str:
        content = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)
        return '<details><summary>' + esc(label) + '</summary><pre>' + esc(content) + '</pre></details>'

    body = ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>ARIADNE — внешний эталон: live1</title>'
            '<style>body{font:16px system-ui;margin:24px;color:#18333f}pre{white-space:pre-wrap;overflow-wrap:anywhere}'
            'table{border-collapse:collapse;width:100%}td,th{border:1px solid #abc;padding:8px;vertical-align:top}'
            '[hidden]{display:none!important}</style><h1>Один разрешённый прогон: вопрос о морфологии</h1>'
            '<p>HTTP200/answered, но ответ не описывает запрошенную морфологию частиц. '
            'Ниже исходный ответ модели и отдельное post-hoc сопоставление ассистента. '
            'Это один внешний reference candidate с известным topic exposure; общей научной accuracy нет.</p>'
            + detail("Исходный пользовательский вопрос и эталон — без изменений", report["user_original"])
            + '<h2>Исходный ответ GigaChat — без исправлений</h2><pre>'
            + esc(report["original_api"]["body"]["answer"]) + '</pre>')
    paths = {row["article_id"]: row["original_pdf_path"] for row in report["articles"] if row.get("article_id")}
    for cite in report["original_api"]["body"]["citations"]:
        link = Path(paths[cite["article_id"]]).as_uri() + '#page=' + str(cite["page_start"])
        body += '<p><a href="' + esc(link) + '">' + esc(cite["citation_id"] + ': ' + cite["title"])
        body += ', PDFс.' + str(cite["page_start"]) + '–' + str(cite["page_end"]) + '</a></p>'
        body += detail("Фактически выданная цитата", cite)
    body += '<h2>Отдельная оценка ассистента</h2>' + detail("Сопоставление и ограничения", report["assessment"])
    for row in report["separate_assistant_source_notes"]:
        link = Path(row["original_pdf_path"]).as_uri() + '#page=' + str(row["pdf_page"])
        body += '<p><a href="' + esc(link) + '">' + esc(row["label"]) + ', Kim PDFс.' + str(row["pdf_page"]) + '</a></p>'
        body += detail("Exact source / отдельные замечания", row)
    body += ('<h2>TAC: все выбранные работы и источник эталона</h2><label>Поиск '
             '<input id="q" type="search"></label><table id="tac"><thead><tr>'
             + ''.join('<th>' + key + '</th>' for key in
                       ('Title', 'Authors', 'Journal', 'Year', 'Abstract', 'Conclusions', 'Terms', 'hyperlink to original file'))
             + '</tr></thead><tbody>')
    for article in report["articles"]:
        body += '<tr>'
        for key in ('title', 'authors', 'journal', 'year', 'abstract', 'conclusions', 'terms'):
            value = article.get(key)
            body += '<td>' + (detail("Полный текст / metadata", value) if value is not None else 'Неизвестно / не собрано') + '</td>'
        body += '<td><a href="' + esc(Path(article["original_pdf_path"]).as_uri()) + '">Оригинальный PDF</a>'
        body += detail("Provenance / scope", article) + '</td></tr>'
    body += '</tbody></table>'
    for label, key in (("Итоги и usage", "summary"), ("Исходный native JSON", "original_native"),
                       ("Исходный API response", "original_api"), ("Фактическая trace", "original_trace"),
                       ("Исходные страницы и слои", "original_sources"), ("Known topic overlap", "known_topic_overlap")):
        body += detail(label, report[key])
    body += ('<script>document.getElementById("q").addEventListener("input",e=>{const s=e.target.value.toLowerCase();'
             'document.querySelectorAll("#tac tbody tr").forEach(r=>r.hidden=!r.textContent.toLowerCase().includes(s))});'
             '</script></html>')
    files.save(output / "review.html", body.encode())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    policy = files.NetworkPolicy()
    sys.addaudithook(policy)
    files.configure()
    print(json.dumps(run(args.stage, args.output, policy), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
