"""Read frozen development results; no network, DB or production changes."""

from __future__ import annotations

import argparse
import html
import json
import sys
from dataclasses import asdict
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlparse
from urllib.request import url2pathname

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import gigachat_answer_smoke as smoke  # noqa: E402
from scripts.requested_information_audit import VERSION, audit_duration, duration_spans  # noqa: E402


def no_network(event: str, args: tuple[object, ...]) -> None:
    if event in {"socket.connect", "socket.getaddrinfo", "socket.sendto"}:
        raise AssertionError("Network forbidden in offline requested-information audit")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sys.addaudithook(no_network)
    from sqlalchemy.engine import Engine

    from app.generation.gigachat import GigaChatAnswerProvider, _json
    from app.generation.providers import Evidence, GenerationOutputError
    from app.generation.service import _validate_claims

    roots = [ROOT / ("output/" + name) for name in (
        "gigachat_answer_batch_20261029_v02", "gigachat_abstention_live_20261029",
        "gigachat_answerability_pair_20261029")]
    inputs = [Path(__file__), ROOT / "scripts/requested_information_audit.py",
              ROOT / "tests/unit/test_requested_information_audit.py",
              ROOT / "docs/records/requested_information_audit_protocol_v0.1.md",
              ROOT / "app/generation/gigachat.py", ROOT / "app/generation/providers.py",
              ROOT / "app/generation/service.py"]
    provider = GigaChatAnswerProvider(credentials="offline-placeholder", scope="GIGACHAT_API_PERS",
                                      model="GigaChat-2-Max", timeout_seconds=120, max_tokens=1200)
    rows, articles = [], {}
    with patch.object(Engine, "connect", side_effect=AssertionError("DB forbidden in offline audit")) as db_connect, patch.object(
            GigaChatAnswerProvider, "_post", side_effect=AssertionError("Transport forbidden in offline audit")) as transport:
        for root in roots:
            for live in sorted((root / "cases").glob("*/live")):
                prepared = live.parent / "prepared"
                for folder in (prepared, live):
                    smoke.verify_manifest(folder)
                    inputs.extend(p for p in folder.rglob("*") if p.is_file())
                contract = json.loads((prepared / "contract.json").read_bytes())
                assert smoke.sha((prepared / "request.json").read_bytes()) == contract["request_sha256"]
                assert (prepared / "request.json").read_bytes() == (live / "request.json").read_bytes()
                slot = smoke.LEDGER / contract["request_sha256"]
                assert (slot / "result.json").read_bytes() == (live / "result.json").read_bytes()
                inputs.extend([slot / "result.json", slot / "attempt.json"])
                trace = json.loads((prepared / "trace.json").read_bytes())
                sources = json.loads((prepared / "sources.json").read_bytes())
                for page in sources["pages"].values():
                    pdf = Path(page["original_pdf_path"])
                    assert smoke.sha(pdf.read_bytes()) == page["original_pdf_sha256"]
                    inputs.append(pdf)
                for article in json.loads((prepared / "articles.json").read_bytes()):
                    if article["article_id"] in articles:
                        assert articles[article["article_id"]] == article
                    articles[article["article_id"]] = article
                api_request = json.loads((prepared / "api_request.json").read_bytes())
                api = json.loads((live / "api_response.json").read_bytes())
                native = _json((live / "response.bin").read_bytes())
                evidence = [Evidence(**e) for e in trace["evidence"]]
                audit, error = None, None
                try:
                    generated = provider._parse_response(native)
                    if generated.answerable:
                        _validate_claims(generated.claims, evidence)
                        audit = asdict(audit_duration(api_request["question"], [c.text for c in generated.claims]))
                        layer = "valid_answer_duration_diagnostic_only"
                    else:
                        layer = "model_abstention_not_semantically_validated"
                except GenerationOutputError as exc:
                    error = str(exc)
                    layer = "runtime_output_rejected_not_a_scientific_abstention"
                assert (error is None) == (api["http_status"] == 200)
                mentions = [{"citation_id": e.citation_id, "article_id": e.article_id,
                             "chunk_id": e.chunk_id, "page_start": e.page_start, "page_end": e.page_end,
                             "spans_in_exact_evidence_text": [asdict(s) for s in duration_spans(e.text)]}
                            for e in evidence]
                rows.append({"id": root.name + "/" + live.parent.name, "question": api_request["question"],
                             "prepared_path": str(prepared), "live_path": str(live),
                             "http_status": api["http_status"], "finish_reason": native["choices"][0]["finish_reason"],
                             "layer": layer, "parser_error": error, "audit": audit,
                             "evidence_time_mentions_unverified": mentions, "api": api,
                             "native": native, "trace": trace, "sources": sources})
    assert db_connect.call_count == transport.call_count == 0
    assert len(rows) == 8
    flagged = [r["id"] for r in rows if r["audit"] and r["audit"]["state"] == "no_duration_expression_detected"]
    assert len(flagged) == 2  # Frozen observed development set, not an accuracy target.
    assert all(r["id"].endswith("/missing_hold_duration") for r in rows if r["id"] in flagged)
    bindings = smoke.bindings(inputs)
    report = {"version": VERSION, "historical_cases": len(rows), "lexically_flagged_answers": flagged,
              "rejected_outputs": sum(r["parser_error"] is not None for r in rows),
              "model_abstentions": sum(r["layer"] == "model_abstention_not_semantically_validated" for r in rows),
              "new_api_calls": 0, "database_connections": "forbidden", "network": "forbidden",
              "runtime_installed": False, "scientific_coverage": "not_evaluated", "independent_accuracy": None,
              "source_documents": len(articles), "bindings": bindings, "cases": rows}

    def detail(label: str, value: object) -> str:
        return '<details><summary>' + html.escape(label) + '</summary><pre>' + html.escape(
            value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)) + '</pre></details>'

    body = ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>ARIADNE — offline audit</title>'
            '<style>body{font:16px system-ui;margin:24px}td,th{border:1px solid #abc;padding:8px;vertical-align:top}'
            'table{border-collapse:collapse;width:100%}pre{white-space:pre-wrap;overflow-wrap:anywhere}'
            '[hidden]{display:none!important}</style><h1>Offline: запрошенная длительность</h1>'
            '<p>8 сохранённых результатов; 2 ответа без распознанного выражения длительности. '
            'Число с единицей времени остаётся непроверенным: подготовка, отрицание, другой образец или работа '
            'не доказывают требуемое измерение. Runtime не изменён; новых API calls — 0. '
            'Это лексическая диагностика, не scientific acceptance.</p><p>Algorithm: ' + VERSION
            + '; input snapshot: ' + smoke.sha(smoke.encode(bindings))
            + '</p><label>Поиск <input id="q" type="search"></label>')
    for row in rows:
        body += '<article data-case data-search><h2>' + html.escape(row["id"]) + '</h2><p>' + html.escape(row["question"]) + '</p>'
        body += detail("Слой результата", {k: row[k] for k in ("http_status", "finish_reason", "layer", "parser_error")})
        body += detail("Лексическая диагностика; связь с экспериментом не проверена", row["audit"])
        body += detail("Все выражения времени в evidence; без вывода о роли", row["evidence_time_mentions_unverified"])
        body += detail("Публичный ответ без исправления", row["api"]) + detail("Native response", row["native"])
        body += detail("Полный запрос", (Path(row["prepared_path"]) / "request.json").read_text(encoding="utf-8"))
        body += detail("Полный retrieval/evidence", row["trace"]) + detail("Все source pages/layers/PDF hashes", row["sources"])
        body += '</article>'
    body += '<h2>TAC: все выбранные документы</h2><table><thead><tr>' + ''.join('<th>' + x + '</th>' for x in (
        "Title", "Authors", "Journal", "Year", "Abstract", "Conclusions", "Terms", "Original file")) + '</tr></thead><tbody>'
    for article in articles.values():
        body += '<tr data-tac data-search>'
        for field in ("title", "authors", "journal", "year", "abstract", "conclusions", "terms"):
            value = article[field]
            body += '<td>' + ("Отсутствует / не собрано на этой стадии" if value is None else detail("Развернуть", value)) + '</td>'
        body += '<td><a href="' + html.escape(Path(article["original_pdf_path"]).as_uri(), quote=True) + '">Original PDF</a></td></tr>'
    body += ('</tbody></table><script>document.getElementById("q").addEventListener("input",e=>{for(const r of '
             'document.querySelectorAll("[data-search]"))r.hidden=!r.textContent.toLocaleLowerCase().includes('
             'e.target.value.toLocaleLowerCase())})</script></html>\n')

    class CheckHTML(HTMLParser):
        def __init__(self) -> None:
            super().__init__()
            self.links: list[str] = []
            self.cases = self.tac = 0

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            values = dict(attrs)
            if tag == "a" and values.get("href"):
                self.links.append(str(values["href"]))
            self.cases += tag == "article" and "data-case" in values
            self.tac += tag == "tr" and "data-tac" in values

    check = CheckHTML()
    check.feed(body)
    for href in check.links:
        parsed = urlparse(href)
        assert parsed.scheme == "file" and Path(url2pathname(parsed.path)).is_file()
    assert check.cases == 8 and check.tac == len(articles)
    smoke.verify(bindings)
    report["html_qa"] = {"method": "static_not_browser", "cases": check.cases, "tac_rows": check.tac,
                         "existing_pdf_links": len(check.links)}
    args.output.mkdir(parents=True, exist_ok=False)
    smoke.write(args.output / "report.json", report)
    smoke.save(args.output / "review.html", body.encode("utf-8"))
    smoke.manifest(args.output)
    print(json.dumps({k: report[k] for k in ("historical_cases", "lexically_flagged_answers", "rejected_outputs",
                                           "model_abstentions", "source_documents", "new_api_calls", "html_qa")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
