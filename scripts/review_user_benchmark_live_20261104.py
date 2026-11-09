"""Offline side-by-side benchmark review; no model calls or database access."""

from __future__ import annotations

import argparse
import json
import re
import sys
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from unittest.mock import patch
from urllib.parse import unquote, urlparse

import fitz

from scripts import gigachat_answer_smoke as files
from scripts import run_user_benchmark_live_20261104 as live
from scripts.user_benchmark_intake import parse_document

ORIGINAL = live.ROOT / "docs/records/Nafion_RAG_Benchmark_v1.0_original.md"
INTAKE = live.ROOT / "output/user_benchmark_20261103/review_v01"
ORIGINAL_SHA = "8b5450878bf9791635767f800616c38e8f1d9108852563171b8af8d1a3677332"
VERSION = "user_benchmark_comparison_v0.1"


def read(path: Path) -> Any:
    return json.loads(path.read_bytes())


def pre(value: Any) -> str:
    return "<pre>" + escape(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)) + "</pre>"


def detail(label: str, value: Any) -> str:
    return "<details><summary>" + escape(label) + "</summary>" + pre(value) + "</details>"


def inline(text: str) -> str:
    safe = escape(text)
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", safe)


def markdown(text: str) -> str:
    """Render only paragraphs/lists/simple pipe tables from preserved local text."""
    lines, parts, index = text.splitlines(), [], 0
    while index < len(lines):
        line = lines[index].strip()
        if not line:
            index += 1
            continue
        if line.startswith("|"):
            rows = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                cells = [x.strip() for x in lines[index].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-+:?", x) for x in cells):
                    rows.append(cells)
                index += 1
            parts.append("<div class='scroll'><table class='inside'>")
            for number, cells in enumerate(rows):
                tag = "th" if number == 0 else "td"
                parts.append("<tr>" + "".join(f"<{tag}>" + inline(x) + f"</{tag}>" for x in cells) + "</tr>")
            parts.append("</table></div>")
        elif line.startswith("- "):
            parts.append("<ul>")
            while index < len(lines) and lines[index].strip().startswith("- "):
                parts.append("<li>" + inline(lines[index].strip()[2:]) + "</li>")
                index += 1
            parts.append("</ul>")
        else:
            paragraph = []
            while index < len(lines) and lines[index].strip() and not lines[index].strip().startswith(("|", "- ")):
                paragraph.append(lines[index].strip())
                index += 1
            parts.append("<p>" + inline(" ".join(paragraph)) + "</p>")
    return "".join(parts)


def offline_replay(prepared: Path, actual: Path) -> dict[str, Any]:
    from fastapi.testclient import TestClient
    from sqlalchemy.engine import Engine

    from app.db.session import get_session
    from app.generation import service
    from app.generation.gigachat import AUTH_URL, CHAT_URL, GigaChatAnswerProvider
    from app.generation.providers import GenerationUnavailableError
    from app.main import app
    from app.retrieval.search import SearchResponse, SearchResult

    trace, api = read(prepared / "trace.json"), read(actual / "api_response.json")
    result = read(actual / "result.json")
    retrieval = SearchResponse(query=trace["retrieval"]["query"], metadata=trace["retrieval"]["metadata"],
                               results=[SearchResult(**r) for r in trace["retrieval"]["results"]])
    calls = []

    def post(self: Any, url: str, body: bytes, authorization: str, *, oauth: bool = False) -> bytes:
        if url != (AUTH_URL if oauth else CHAT_URL):
            raise ValueError("Unexpected offline endpoint")
        calls.append("oauth_boundary" if oauth else "native_response")
        if oauth:
            if result["model_attempts"] == 0:
                error = api["body"].get("detail", "")
                if not error.startswith("GigaChat OAuth request failed"):
                    raise ValueError("Unsupported replay failure; do not fabricate transport behavior")
                raise GenerationUnavailableError(error)
            return b'{"access_token":"offline-placeholder"}'
        if body != (prepared / "request.json").read_bytes():
            raise ValueError("Offline native body differs")
        return (actual / "response.bin").read_bytes()

    def no_session():
        yield object()

    previous = dict(app.dependency_overrides)
    app.dependency_overrides[get_session] = no_session
    try:
        with patch.object(service, "search_chunks", return_value=retrieval), patch.object(
                GigaChatAnswerProvider, "_post", post), patch.object(
                Engine, "connect", side_effect=AssertionError("DB forbidden in offline review")) as db_guard:
            with TestClient(app) as client:
                response = client.post("/answer", json=read(prepared / "api_request.json"))
            if db_guard.call_count:
                raise ValueError("DB attempted in offline replay")
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)
    expected_calls = ["oauth_boundary", "native_response"] if result["model_attempts"] else ["oauth_boundary"]
    if calls != expected_calls or response.status_code != api["http_status"] or response.json() != api["body"]:
        raise ValueError("Full offline /answer status/body/boundary inventory differs")
    return {"status": "identical_http_status_and_complete_body", "simulated_boundaries": calls,
            "real_model_calls": 0, "real_oauth_calls": 0, "db_connections": 0}


def program_text(api: dict[str, Any] | None) -> str:
    if api is None:
        return "Не отправлен: сохранённого результата нет."
    body = api["body"]
    if api["http_status"] != 200:
        return "Техническая ошибка HTTP " + str(api["http_status"]) + ": " + str(body.get("detail", body))
    if body.get("status") != "answered":
        return "Ответ не выдан: " + str(body.get("status"))
    # The API's answer text is displayed verbatim; claims/citations remain separately inspectable.
    return body["answer"]


def render(report: dict[str, Any]) -> str:
    parts = ["""<!doctype html><html lang='ru'><meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<title>ARIADNE — ваши эталоны и ответы программы</title><style>
body{font:16px/1.55 system-ui;margin:28px;color:#183044;background:#fafbfc}
h1{font-size:28px}h2{margin-top:32px}.scroll{overflow:auto}table{border-collapse:collapse;width:100%;background:white}
th,td{border:1px solid #bccbd7;padding:16px;vertical-align:top}th{background:#eaf0f5;text-align:left}
#comparison{min-width:1250px;table-layout:fixed}#comparison>thead>tr>th:first-child{width:15%}
#comparison>thead>tr>th:nth-child(2){width:30%}#comparison>thead>tr>th:nth-child(3){width:30%}
#comparison>thead>tr>th:nth-child(4){width:25%}.inside{font-size:14px}.inside th,.inside td{padding:6px}
pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f0f4f7;padding:12px;font:14px/1.55 system-ui}
details{margin:12px 0}summary{cursor:pointer;color:#17578b}a{color:#135c96}.badge{font-weight:600}
input{padding:10px;width:min(600px,90%)}.notice{padding:16px;background:#edf3f8;border-left:4px solid #527c9e}
@media print{body{margin:0;font-size:11px}details{display:none}.scroll{overflow:visible}#comparison{min-width:0}}
</style><body><h1>Ваши эталоны и ответы ARIADNE</h1>
<p>Benchmark v1.0 · Q01–Q05 · 4 ноября 2026</p>
<div class='notice'>Эталоны и ответы показаны без исправлений. Различия — последующая проверка ассистента,
не независимая экспертная оценка. Ошибка соединения и отказ модели отделены от фактической ошибки ответа.
Участие LLM в подготовке эталонов и отдельная экспертная проверка не объявлены; прежняя тематическая
экспозиция сохраняется. У Q04 остаётся замечание «физические / chemical crosslinking elements».
Независимая научная приёмка открыта; 75% — прогресс работ, не точность.</div>"""]
    parts.append(detail("Вызовы, статусы, токены и ограничения", report["summary"]))
    parts.append("<p><label>Поиск по таблицам <input type='search' id='q'></label></p>")
    parts.append("<div class='scroll'><table id='comparison'><thead><tr><th>Вопрос</th><th>Ваш эталон</th>"
                 "<th>Ответ программы — исходный</th><th>Сравнение и источники</th></tr></thead><tbody>")
    for row in report["cases"]:
        case, assessment = row["reference"], row["assistant_posthoc_comparison"]
        parts.append("<tr id='" + case["id"] + "'><td><h2>" + case["id"] + "</h2><p>" + escape(case["question"]) + "</p>")
        parts.append(detail("Фактический результат выполнения", row["result"]))
        parts.append("</td><td>" + markdown(case["reference_answer_markdown_verbatim"]))
        parts.append("<details><summary>Существенные условия и ограничения эталона</summary>"
                     + markdown(case["conditions_markdown_verbatim"]) + "</details>")
        parts.append(detail("Дословный Markdown пользователя", case["case_markdown_verbatim"]) + "</td><td>")
        parts.append(pre(program_text(row["api_response"])))
        if row["api_response"]:
            for claim in row["api_response"]["body"].get("claims", []):
                parts.append(detail("Claim и исходные citation_ids", claim))
            parts.append(detail("Полный исходный API status/body", row["api_response"]))
        if row["native_response"]:
            parts.append(detail("Полный native response провайдера", row["native_response"]))
        parts.append("</td><td><p class='badge'>" + escape(assessment["verdict"]) + "</p>")
        parts.append("<ul>" + "".join("<li>" + escape(x) + "</li>" for x in assessment["observations"]) + "</ul>")
        parts.append(detail("Точные фрагменты для проверки замечаний", assessment.get("evidence_checks", [])))
        parts.append(detail("Попадание эталонной статьи в фактический вход", row["reference_retrieval_diagnostic"]))
        for quote in case["quotes"]:
            url = Path(case["source_pdf_path_verbatim"]).as_uri() + "#page=" + str(quote["pdf_page"])
            parts.append("<p><a href='" + escape(url, quote=True) + "'>Эталон: PDF стр. "
                         + str(quote["pdf_page"]) + "</a></p>")
        for evidence in row["prepared"]["trace"]["evidence"]:
            article = next(a for a in report["articles"] if a["article_id"] == evidence["article_id"])
            url = Path(article["original_pdf_path"]).as_uri() + "#page=" + str(evidence["page_start"])
            label = evidence["citation_id"] + ": " + str(evidence["title"]) + " · PDF "
            label += str(evidence["page_start"]) + "–" + str(evidence["page_end"])
            parts.append("<p><a href='" + escape(url, quote=True) + "'>" + escape(label) + "</a></p>")
            parts.append(detail("Точный исходный фрагмент " + evidence["citation_id"], evidence))
        parts.append(detail("Полный сырой контекст выбранных страниц", row["prepared"]["sources"]))
        parts.append(detail("Прежние замечания приёмки эталона", row["intake_notes"]))
        parts.append(detail("Проверка воспроизведения", row["offline_replay"]) + "</td></tr>")
    parts.append("</tbody></table></div><h2>Все статьи этапа — TAC</h2><div class='scroll'><table id='tac'><thead><tr>")
    parts += ["<th>" + x + "</th>" for x in
              ("Title", "Authors", "Journal", "Year", "Abstract", "Conclusions", "Terms", "Original file")]
    parts.append("</tr></thead><tbody>")
    for article in report["articles"]:
        parts.append("<tr>")
        for key in ("title", "authors", "journal", "year", "abstract", "conclusions", "terms"):
            value = article.get(key)
            parts.append("<td>" + detail(str(value)[:110] if value is not None else "Не собрано",
                                         value if value is not None else "Не собрано в этом этапе") + "</td>")
        parts.append("<td><a href='" + escape(Path(article["original_pdf_path"]).as_uri(), quote=True)
                     + "'>Оригинал PDF</a></td></tr>")
    parts.append("""</tbody></table></div><script>document.querySelector('#q').addEventListener('input',e=>{
const q=e.target.value.toLocaleLowerCase();for(const r of document.querySelectorAll('#comparison>tbody>tr,#tac>tbody>tr'))
r.hidden=!r.textContent.toLocaleLowerCase().includes(q);});</script></body></html>""")
    return "".join(parts)


class Structure(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []
        self.ids: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "a" and values.get("href"):
            self.links.append(values["href"])
        if values.get("id"):
            self.ids.append(values["id"])


def run(output: Path, assessment_path: Path) -> dict[str, Any]:
    frozen, folders = live.read_scope()
    files.verify_manifest(INTAKE)
    intake = read(INTAKE / "report.json")
    original = ORIGINAL.read_bytes()
    if files.sha(original) != ORIGINAL_SHA:
        raise ValueError("Original gold bytes differ")
    references = parse_document(original.decode("utf-8"))
    assessments = read(assessment_path)
    if (assessments["origin"] != "assistant_posthoc_not_independent_scientific_evaluation"
            or [x["id"] for x in assessments["cases"]] != list(live.IDS)):
        raise ValueError("Comparison provenance/inventory differs")
    bindings = {**frozen["bindings"], **files.bindings([
        ORIGINAL, INTAKE / "manifest.json", INTAKE / "report.json", live.APPROVAL, live.SCOPE,
        Path(__file__), Path(live.__file__), assessment_path])}
    articles = {a["article_id"]: a for a in frozen["articles"]}
    for article in intake["articles"]:
        if article["article_id"] not in articles:
            articles[article["article_id"]] = article
    cases, fresh_pages, pdfs = [], {}, {}
    for reference, prepared_row, assessment in zip(references, frozen["cases"], assessments["cases"], strict=True):
        case_id = reference["id"]
        if reference["question"] != prepared_row["case"]["question"] or case_id != assessment["id"]:
            raise ValueError("Reference/prediction question differs")
        folder = live.BASE / case_id / "live"
        api, native, replay, result = None, None, None, {"status": "not_sent"}
        if folder.exists():
            files.verify_manifest(folder)
            result = read(folder / "result.json")
            api = read(folder / "api_response.json") if (folder / "api_response.json").exists() else None
            if (result["model_attempts"] > 1 or result["oauth_attempts"] > 1
                    or result["automatic_retries"] != 0 or result["fallbacks"] != 0):
                raise ValueError("Observed per-case budget differs")
            prepared = folders[case_id]
            if (folder / "request.json").exists() and (folder / "request.json").read_bytes() != (prepared / "request.json").read_bytes():
                raise ValueError("Sent native body differs")
            for name in ("trace.json", "sources.json", "articles.json"):
                if (folder / name).read_bytes() != (prepared / name).read_bytes():
                    raise ValueError("Actual source trace differs")
            slot = files.LEDGER / prepared_row["contract"]["request_sha256"]
            for name in ("attempt.json", "result.json"):
                if (slot / name).read_bytes() != (folder / name).read_bytes():
                    raise ValueError("Global slot outcome differs")
                bindings.update(files.bindings([slot / name]))
            bindings.update(files.bindings([p for p in folder.iterdir() if p.is_file()]))
            if (folder / "response.bin").exists():
                native = read(folder / "response.bin")
            if api is not None:
                replay = offline_replay(prepared, folder)
        source_pdf = str(Path(reference["source_pdf_path_verbatim"]).resolve())
        target = next(a for a in intake["articles"] if str(Path(a["original_pdf_path"]).resolve()) == source_pdf)
        selected = [e for e in prepared_row["trace"]["evidence"] if e["article_id"] == target["article_id"]]
        for check in assessment.get("evidence_checks", []):
            evidence = next(e for e in prepared_row["trace"]["evidence"] if e["citation_id"] == check["citation_id"])
            if evidence["text"][check["start"]:check["end"]] != check["text"]:
                raise ValueError("Post-hoc diagnostic raw evidence anchor differs")
        diagnostic = {"origin": "post_prediction_reference_identity_comparison_not_inference_input",
                      "reference_article_id": target["article_id"],
                      "selected_in_prepared_evidence": bool(selected),
                      "selected_citation_ids_pages": [{k: e[k] for k in ("citation_id", "page_start", "page_end")} for e in selected],
                      "reference_pdf_pages": sorted({q["pdf_page"] for q in reference["quotes"]}),
                      "selected_reference_pdf_pages": sorted({q["pdf_page"] for q in reference["quotes"]
                                                               if any(e["page_start"] <= q["pdf_page"] <= e["page_end"]
                                                                      for e in selected)}),
                      "actual_model_request_attempted": result.get("model_attempts", 0) == 1,
                      "selection_is_not_source_or_answer_completeness": True}
        for page in prepared_row["sources"]["pages"].values():
            for field in ("original_pdf_path", "layer_pdf_path"):
                path = page[field]
                if path not in pdfs:
                    pdfs[path] = files.sha(Path(path).read_bytes())
                if pdfs[path] != page[field.replace("path", "sha256")]:
                    raise ValueError("PDF digest differs")
            key = page["layer_pdf_path"], page["page_number"]
            if key not in fresh_pages:
                with fitz.open(key[0]) as pdf:
                    fresh_pages[key] = pdf[key[1] - 1].get_text()
            if (fresh_pages[key] != page["page_text"]
                    or page["page_text"][page["start"]:page["end"]] != page["quote"]):
                raise ValueError("Fresh PDF/source window differs")
        cases.append({"id": case_id, "reference": reference, "result": result, "api_response": api,
                      "native_response": native, "prepared": prepared_row, "offline_replay": replay,
                      "reference_retrieval_diagnostic": diagnostic, "assistant_posthoc_comparison": assessment,
                      "intake_notes": [n for n in intake["source_notes"] if n["case_id"] == case_id]})
    usage = [c["result"].get("usage") for c in cases if c["result"].get("usage")]
    summary = {"actual_model_attempts": sum(c["result"].get("model_attempts", 0) for c in cases),
               "actual_oauth_attempts": sum(c["result"].get("oauth_attempts", 0) for c in cases),
               "automatic_retries": 0, "fallbacks": 0,
               "http_status_by_case": {c["id"]: c["api_response"]["http_status"] if c["api_response"] else None for c in cases},
               "usage_reported": {key: sum(u[key] for u in usage) for key in
                                  ("prompt_tokens", "completion_tokens", "total_tokens")},
               "actual_cost": None, "fresh_pages_verified": len(fresh_pages), "pdf_hashes_verified": len(pdfs),
               "offline_asgi_replays": sum(c["offline_replay"] is not None for c in cases),
               "review_real_model_oauth_calls": 0, "review_db_connections": 0,
               "independent_accuracy": None, "scientific_acceptance": "not_established",
               "answer_quality_plan_percent": 75,
               "limitations": ["n=5, prior corpus/topic exposure; reference LLM assistance/expert verification undeclared",
                               "No blind independent scientific score; assistant comparison is post-hoc",
                               "Known intake caveats remain; gold not corrected after predictions",
                               "Fresh processes do not validate cache/ORM; no full suite/mypy/browser execution yet",
                               "Technical OAuth failures do not measure scientific answer quality"]}
    report = {"version": VERSION, "bindings": bindings, "cases": cases,
              "articles": list(articles.values()), "summary": summary}
    html = render(report)
    structure = Structure()
    structure.feed(html)
    if any(structure.ids.count(key) != 1 for key in (*live.IDS, "comparison", "tac")):
        raise ValueError("HTML comparison inventory differs")
    for link in structure.links:
        parsed = urlparse(link)
        if parsed.scheme != "file" or not Path(unquote(parsed.path).lstrip("/")).is_file():
            raise ValueError("Missing/nonlocal source link")
    files.verify(bindings)
    output.mkdir(parents=True, exist_ok=False)
    files.write(output / "report.json", report)
    files.save(output / "review.html", html.encode())
    files.write(output / "qa.json", {"cases": len(cases), "tac_rows": len(articles), "tac_columns": 8,
                                    "existing_pdf_links": len(structure.links), "status": "passed"})
    files.manifest(output)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--assessment", type=Path, required=True)
    args = parser.parse_args()
    policy = files.NetworkPolicy()
    sys.addaudithook(policy)
    print(json.dumps(run(args.output, args.assessment), ensure_ascii=False))


if __name__ == "__main__":
    main()
