"""Verify frozen five-question inputs and selected raw sources; no gold or DB."""

from __future__ import annotations

import json
import sys
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import fitz

from scripts import gigachat_answer_smoke as files
from scripts.prepare_benchmark_inputs_20261103 import BASE, CASES, FREEZE, PROTOCOL, ROOT, VERSION, GoldReadGuard, load_cases

SELECTION = BASE / "prepared_selection_v01.json"


def read(path: Path) -> Any:
    return json.loads(path.read_bytes())


def verify_native(raw: bytes, contract: dict[str, Any], question: str) -> dict[str, Any]:
    if files.sha(raw) != contract["request_sha256"] or len(raw) != contract["request_bytes"]:
        raise ValueError("Frozen native request digest/size differs")
    native = json.loads(raw)
    if native["model"] != "GigaChat-2-Max" or native["max_tokens"] != 1200:
        raise ValueError("Frozen model/token limit differs")
    user = [m["content"] for m in native["messages"] if m["role"] == "user"]
    if len(user) != 1 or question not in user[0]:
        raise ValueError("Verbatim question missing from native user message")
    return native


def detail(title: str, value: Any) -> str:
    raw = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)
    return "<details><summary>" + escape(title) + "</summary><pre>" + escape(raw) + "</pre></details>"


def render(report: dict[str, Any]) -> str:
    body = """<!doctype html><html lang="ru"><meta charset="utf-8"><title>ARIADNE — пять входов без отправки</title>
<style>body{font:16px/1.5 system-ui;margin:30px;color:#182f42}table{border-collapse:collapse;width:100%}
td,th{border:1px solid #bccad5;padding:10px;vertical-align:top}td{max-width:340px}
pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f2f5f8;padding:12px}
section{margin:28px 0;border-top:2px solid #acbecd}summary{cursor:pointer}input{padding:8px}
[hidden]{display:none!important}.scroll{overflow:auto}</style><body><h1>Пять входов: подготовлены, не отправлены</h1>
<p>Текущий /answer, отдельный процесс для каждого вопроса, read-only БД и локальный индекс.
Эталонные ответы, ожидаемые статьи и заметки проверки не поступали в подготовку.
Вопросы сохранены дословно. Ответов модели и научных оценок нет. Все live budgets закрыты.</p>"""
    body += detail("Итог и ограничения", report["summary"])
    body += detail("Версия и SHA256 замороженных входов", {"version": VERSION, "bindings": report["bindings"]})
    body += '<h2>TAC: все статьи выбранных источников</h2><label>Поиск <input id="q" type="search"></label>'
    body += '<div class="scroll"><table id="tac"><thead><tr>'
    body += "".join("<th>" + x + "</th>" for x in (
        "Title", "Authors", "Journal", "Year", "Abstract", "Conclusions", "Terms", "Original file"))
    body += "</tr></thead><tbody>"
    for article in report["articles"]:
        body += "<tr>"
        for field in ("title", "authors", "journal", "year", "abstract", "conclusions", "terms"):
            value = article.get(field)
            value = value if value is not None else "Не собрано в этом этапе"
            preview = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
            body += "<td>" + detail(preview[:120], value) + "</td>"
        body += "<td><a href='" + escape(Path(article["original_pdf_path"]).as_uri(), quote=True) + "'>PDF</a></td></tr>"
    body += "</tbody></table></div>"
    for row in report["cases"]:
        case, contract = row["case"], row["contract"]
        body += "<section id='" + case["id"] + "'><h2>" + case["id"] + "</h2><p>" + escape(case["question"]) + "</p>"
        body += "<p>" + escape(contract["preparation_status"]) + "; bytes=" + str(contract["request_bytes"]) + "</p>"
        body += detail("API-вход: только вопрос и текущие настройки", row["api_request"])
        body += detail("Фактический gate/status", row["gate_response"] or row["trace"]["metadata"])
        body += detail("Замороженный contract", contract)
        body += detail("Неотправленный native request", row["native_request"])
        body += detail("Полная трасса и source registry", {"trace": row["trace"], "sources": row["sources"]})
        for evidence in row["trace"]["evidence"]:
            body += detail("Исходный фрагмент " + evidence["citation_id"], evidence)
            for page in row["sources"]["pages"].values():
                if page["article_id"] == evidence["article_id"] and evidence["page_start"] <= page["page_number"] <= evidence["page_end"]:
                    url = Path(page["original_pdf_path"]).as_uri() + "#page=" + str(page["page_number"])
                    body += "<p><a href='" + escape(url, quote=True) + "'>PDF стр. " + str(page["page_number"]) + "</a></p>"
                    body += detail("Полный сырой контекст страницы — не сводка", page)
        body += "</section>"
    body += """<script>document.querySelector('#q').addEventListener('input',e=>{
for(const r of document.querySelectorAll('#tac tbody tr'))
r.hidden=!r.textContent.toLocaleLowerCase().includes(e.target.value.toLocaleLowerCase());});</script></body></html>"""
    return body


class Structure(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.headers = 0
        self.rows = 0
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.headers += tag == "th"
        self.rows += tag == "tr"
        href = dict(attrs).get("href")
        if tag == "a" and href:
            self.links.append(href)


def review(output: Path) -> dict[str, Any]:
    cases = load_cases()
    selection = read(SELECTION)
    if set(selection["prepared"]) != {c["id"] for c in cases}:
        raise ValueError("Prepared folder inventory differs")
    files.verify_manifest(FREEZE)
    bindings = files.bindings([CASES, PROTOCOL, SELECTION, Path(__file__),
                               ROOT / "tests/unit/test_benchmark_inputs_review_20261103.py"])
    metadata, rows, fresh_pages, pdf_hashes = {}, [], {}, {}
    for case in cases:
        folder = Path(selection["prepared"][case["id"]])
        files.verify_manifest(folder)
        contract, api, trace, sources, articles = [read(folder / f"{name}.json") for name in (
            "contract", "api_request", "trace", "sources", "articles")]
        if (contract["version"], contract["id"], contract["question"]) != (VERSION, case["id"], case["question"]):
            raise ValueError("Preparation identity differs")
        for key in ("maximum_model_attempts", "maximum_oauth_attempts", "new_model_calls", "new_oauth_calls", "new_slot_reservations"):
            if contract[key] != 0:
                raise ValueError("Preparation authorized/reserved live calls")
        if contract["network_denials"] or contract["gold_read_denials"]:
            raise ValueError("Forbidden access attempts recorded")
        if (set(api) != {"question", "collection", "method", "top_k", "answer_style", "answer_language"}
                or api["question"] != case["question"]):
            raise ValueError("API request has extra/mutated inputs")
        files.verify(contract["input_bindings"])
        for name, digest in contract["input_bindings"].items():
            if name in bindings and bindings[name] != digest:
                raise ValueError("Conflicting runtime/source/index bindings")
            bindings[name] = digest
        bindings.update(files.bindings([p for p in folder.iterdir() if p.is_file()]))
        for article in articles:
            old = metadata.setdefault(article["article_id"], article)
            if old != article:
                raise ValueError("Metadata drift across fresh processes")
        for page in sources["pages"].values():
            for field, digest_key in (("original_pdf_path", "original_pdf_sha256"), ("layer_pdf_path", "layer_pdf_sha256")):
                path = page[field]
                if path not in pdf_hashes:
                    pdf_hashes[path] = files.sha(Path(path).read_bytes())
                if pdf_hashes[path] != page[digest_key]:
                    raise ValueError("Selected PDF hash differs")
            key = page["layer_pdf_path"], page["page_number"]
            if key not in fresh_pages:
                with fitz.open(key[0]) as pdf:
                    fresh_pages[key] = pdf[key[1] - 1].get_text()
            if (fresh_pages[key] != page["page_text"]
                    or files.sha(page["page_text"].encode("utf-8")) != page["page_text_sha256"]
                    or page["page_text"][page["start"]:page["end"]] != page["quote"]):
                raise ValueError("Fresh source page/anchor differs")
        native = (verify_native((folder / "request.json").read_bytes(), contract, case["question"])
                  if contract["generation_reached"] else None)
        gate = read(folder / "gate_response.json") if (folder / "gate_response.json").exists() else None
        if not contract["generation_reached"] and ((folder / "request.json").exists() or gate is None):
            raise ValueError("Blocked preparation request/status inconsistent")
        rows.append({"case": case, "contract": contract, "api_request": api, "trace": trace, "sources": sources,
                     "gate_response": gate, "native_request": native, "model_answer": None, "scientific_score": None})
    summary = {"questions": len(cases), "prepared_unsent": [r["case"]["id"] for r in rows if not r["contract"]["blocking_reasons"]],
               "blocked_for_future_dispatch": [r["case"]["id"] for r in rows if r["contract"]["blocking_reasons"]],
               "request_bytes": {r["case"]["id"]: r["contract"]["request_bytes"] for r in rows},
               "selected_documents": len(metadata), "fresh_source_pages_verified": len(fresh_pages),
               "pdf_hashes_verified": len(pdf_hashes), "binding_count": len(bindings),
               "new_model_calls": 0, "new_oauth_calls": 0, "new_slot_reservations": 0, "review_db_calls": 0,
               "scientific_scores": None, "answer_quality_plan_percent": 75,
               "limitations": ["Gate admission does not prove scientific answerability or reference coverage.",
                               "No gold comparison or model outputs; corpus/topic exposure retained.",
                               "Fresh processes do not validate long-lived cache/ORM behavior.",
                               "Native bodies are unsent; no provider token usage, latency or monetary cost observed.",
                               "PDF extraction/static HTML checked; browser/PDF visual/full suite/mypy untested."]}
    report = {"version": VERSION, "bindings": bindings, "cases": rows, "articles": list(metadata.values()), "summary": summary}
    html = render(report)
    structure = Structure()
    structure.feed(html)
    if structure.headers != 8 or structure.rows != len(metadata) + 1:
        raise ValueError("TAC structure differs")
    for link in structure.links:
        url = urlparse(link)
        path = Path(unquote(url.path).lstrip("/"))
        if url.scheme != "file" or not path.is_file() or str(path.resolve()) not in {str(Path(p).resolve()) for p in pdf_hashes}:
            raise ValueError("Invalid/unregistered local PDF link")
    files.verify(bindings)
    output.mkdir(parents=True, exist_ok=False)
    files.write(output / "report.json", report)
    files.save(output / "review.html", html.encode("utf-8"))
    files.write(output / "qa.json", {"tac_rows": structure.rows - 1, "columns": structure.headers,
                "existing_pdf_links": len(structure.links), "fresh_source_pages": len(fresh_pages), "status": "passed"})
    files.write(output / "manifest.json", {"version": VERSION, "outputs": {
        p.relative_to(output).as_posix(): files.sha(p.read_bytes()) for p in sorted(output.rglob("*")) if p.is_file()}})
    return summary


if __name__ == "__main__":
    sys.addaudithook(GoldReadGuard())

    def no_network(event: str, args: tuple[Any, ...]) -> None:
        if event in {"socket.connect", "socket.getaddrinfo", "socket.sendto"}:
            raise RuntimeError("Review forbids all network/DB access")

    sys.addaudithook(no_network)
    print(json.dumps(review(BASE / "review_v01"), ensure_ascii=False))
