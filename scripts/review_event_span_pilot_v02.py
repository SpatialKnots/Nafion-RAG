"""Offline strict replay and complete review of the bounded v0.2 live pilot."""

from __future__ import annotations

import argparse
import html
import json
import sys
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlparse
from urllib.request import url2pathname

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.generation.gigachat import GigaChatAnswerProvider  # noqa: E402
from scripts import gigachat_answer_smoke as files  # noqa: E402
from scripts import run_event_span_pilot_v02 as pilot  # noqa: E402
from scripts.event_span_checks_v02 import compare  # noqa: E402
from scripts.event_spans_v02 import parse_proposal  # noqa: E402


def no_network(event: str, args: tuple[object, ...]) -> None:
    if event in {"socket.connect", "socket.getaddrinfo", "socket.sendto", "socket.sendmsg"}:
        raise AssertionError("Network forbidden in postflight replay")


def detail(label: str, value: object) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)
    return '<details><summary>' + html.escape(label) + '</summary><pre>' + html.escape(text) + '</pre></details>'


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sys.addaudithook(no_network)
    study = pilot.read_study()
    bindings = {**study["bindings"], **files.bindings([pilot.BASE / "study_contract_v01.json", Path(__file__)])}
    rows, articles = [], {}
    with patch.object(GigaChatAnswerProvider, "_post", side_effect=AssertionError("Transport forbidden in replay")) as transport:
        for case_id in pilot.IDS:
            prepared, live = (pilot.BASE / "cases" / case_id / name for name in ("prepared", "live"))
            source_row = json.loads((prepared / "input.json").read_bytes())
            request = json.loads((prepared / "request.json").read_bytes())
            old_prepared = ROOT / "output/gigachat_event_pilot_20261029/cases" / case_id / "prepared"
            files.verify_manifest(old_prepared)
            article = json.loads((old_prepared / "article.json").read_bytes())
            bindings.update(files.bindings([old_prepared / "article.json", old_prepared / "manifest.json"]))
            articles[article["article_id"]] = article
            row = {"id": case_id, "input": source_row, "request": request, "raw_native_reply_text": None,
                   "restored": None, "comparison": None, "offline_replay": "not_applicable_no_model_reply"}
            if not live.exists():
                row["result"] = {"status": "not_attempted_after_transport_stop", "model_attempts": 0, "oauth_attempts": 0}
            else:
                files.verify_manifest(live)
                bindings.update(files.bindings([p for p in live.iterdir() if p.is_file()]))
                result = json.loads((live / "result.json").read_bytes())
                attempt = json.loads((live / "attempt.json").read_bytes())
                slot = files.LEDGER / attempt["request_sha256"]
                for name in ("attempt.json", "result.json"):
                    if (slot / name).read_bytes() != (live / name).read_bytes():
                        raise ValueError("Global slot differs from durable case result")
                    bindings.update(files.bindings([slot / name]))
                row["result"] = result
                if (live / "response.bin").exists():
                    raw = (live / "response.bin").read_bytes()
                    row["raw_native_reply_text"] = raw.decode("utf-8", errors="backslashreplace")
                    try:
                        restored = parse_proposal(raw, source_row["source"])
                    except ValueError as exc:
                        if result["status"] != "output_rejected" or str(exc) != result["error"]:
                            raise ValueError("Strict offline rejection differs from live result") from exc
                        row["offline_replay"] = "identical_rejection"
                    else:
                        if result["status"] != "integrity_valid_scientific_assignment_unverified" or restored != json.loads(
                                (live / "restored.json").read_bytes()):
                            raise ValueError("Offline restored output differs from live result")
                        row["restored"] = restored
                        row["comparison"] = compare(source_row["source"], source_row["constructed_fixture"]["reference"], restored)
                        row["offline_replay"] = "identical_restored_output"
            rows.append(row)
        if transport.call_count:
            raise ValueError("Postflight unexpectedly attempted transport")
    counts = Counter(r["result"]["status"] for r in rows)
    model_attempts = sum(r["result"]["model_attempts"] for r in rows)
    oauth_attempts = sum(r["result"]["oauth_attempts"] for r in rows)
    if model_attempts > 3 or oauth_attempts > 3:
        raise ValueError("Pilot exceeded declared network budget")
    if counts["not_attempted_after_transport_stop"] and not counts["transport_failed"]:
        raise ValueError("Unattempted case without the declared stop condition")
    usage_rows = [r["result"]["usage"] for r in rows if isinstance(r["result"].get("usage"), dict)]
    usage_totals = {}
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        values = [u[key] for u in usage_rows if type(u.get(key)) is int]
        usage_totals[key] = sum(values) if values else None
    summary = {"cases": len(rows), "statuses": dict(counts), "model_attempts": model_attempts, "oauth_attempts": oauth_attempts,
               "finish_reasons": dict(Counter(r["result"].get("finish_reason") for r in rows if r["result"]["model_attempts"])),
               "sparse_checks": dict(Counter(c["state"] for r in rows if r["comparison"] for c in r["comparison"]["checks"])),
               "provider_usage_reports_available": len(usage_rows), "provider_reported_usage": usage_totals,
               "postflight_transport_calls": 0, "scientific_acceptance": "not_evaluated", "independent_accuracy": None,
               "pilot_closed_no_automatic_followups": True}
    report = {"version": pilot.VERSION, "bindings": bindings, "summary": summary, "cases": rows,
              "metadata_limits": "native_success_http_metadata_and_http_error_bodies_not_exposed_by_reused_transport"}
    body = ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>ARIADNE — live event-span pilot v0.2</title>'
            '<style>body{font:16px system-ui;margin:24px}table{border-collapse:collapse;width:100%}td,th{border:1px solid #abc;'
            'padding:8px;vertical-align:top}pre,blockquote{white-space:pre-wrap;overflow-wrap:anywhere}'
            '[hidden]{display:none!important}</style><h1>Live-пилот событий v0.2</h1>'
            '<p>Три известных случая. Сырые ответы модели и исходные отказы сохранены. '
            'Точность фрагментов и sparse checks не подтверждают научное назначение или полноту. '
            'Разметка ассистента предварительная, независимой оценки нет. /answer не изменён. '
            'Бюджет пилота закрыт; автоматических повторов нет.</p><p>Algorithm: ' + pilot.VERSION
            + '; snapshot: ' + files.sha(files.encode(bindings)) + '</p><label>Поиск <input id="q" type="search"></label>'
            + detail("Сводка", summary))
    for row in rows:
        case = row["input"]["case"]
        body += '<article data-case data-search><h2>' + html.escape(row["id"]) + '</h2><p>' + html.escape(case["question"]) + '</p>'
        body += '<blockquote>' + html.escape(case["exact_text"]) + '</blockquote><a href="' + html.escape(
            Path(case["source"]["original_pdf_path"]).as_uri() + '#page=' + str(case["page"]), quote=True) + '">Original PDF</a>'
        for label, field in (("Результат вызова / исходная ошибка", "result"), ("Полный native request", "request"),
                             ("Сырой native reply; исходные bytes сохранены отдельно", "raw_native_reply_text"),
                             ("Строго восстановленное предложение, не научная приёмка", "restored"),
                             ("Sparse checks; unscored не является успехом", "comparison"), ("Offline replay", "offline_replay")):
            body += detail(label, row[field])
        body += detail("Каталог, исходная разметка, точные привязки и полная страница", row["input"]) + '</article>'
    body += '<h2>TAC: все три работы</h2><table><thead><tr>' + ''.join('<th>' + x + '</th>' for x in (
        "Title", "Authors", "Journal", "Year", "Abstract", "Conclusions", "Terms", "Original file")) + '</tr></thead><tbody>'
    for article in articles.values():
        body += '<tr data-tac data-search>'
        for field in ("title", "authors", "journal", "year", "abstract", "conclusions", "terms"):
            body += '<td>' + ("Отсутствует / не собрано на этой стадии" if article[field] is None else detail(
                "Развернуть", article[field])) + '</td>'
        body += '<td><a href="' + html.escape(Path(article["original_pdf_path"]).as_uri(), quote=True) + '">Original PDF</a></td></tr>'
    body += ('</tbody></table><script>document.getElementById("q").addEventListener("input",e=>{for(const r of '
             'document.querySelectorAll("[data-search]"))r.hidden=!r.textContent.toLocaleLowerCase().includes('
             'e.target.value.toLocaleLowerCase())})</script></html>\n')

    class CheckHTML(HTMLParser):
        def __init__(self) -> None:
            super().__init__()
            self.cases = self.tac = 0
            self.links: list[str] = []

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            values = dict(attrs)
            self.cases += tag == "article" and "data-case" in values
            self.tac += tag == "tr" and "data-tac" in values
            if tag == "a" and values.get("href"):
                self.links.append(str(values["href"]))

    check = CheckHTML()
    check.feed(body)
    if check.cases != 3 or check.tac != 3:
        raise ValueError("HTML omits declared cases or source works")
    for href in check.links:
        url = urlparse(href)
        if url.scheme != "file" or not Path(url2pathname(url.path)).is_file():
            raise ValueError("Missing original PDF link")
    report["html_qa"] = {"method": "static_not_browser", "case_cards": check.cases,
                         "tac_rows": check.tac, "existing_original_pdf_links": len(check.links)}
    files.verify(bindings)
    args.output.mkdir(parents=True, exist_ok=False)
    files.write(args.output / "report.json", report)
    files.save(args.output / "review.html", body.encode())
    files.manifest(args.output)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
