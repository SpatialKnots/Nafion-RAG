"""Prepare twelve exact-span candidate requests and constructed controls offline."""

from __future__ import annotations

import argparse
import copy
import html
import json
import sys
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import url2pathname

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import gigachat_answer_smoke as files  # noqa: E402
from scripts.event_span_checks_v02 import compare  # noqa: E402
from scripts.event_spans_v02 import VERSION, build_request, catalog, validate_reply  # noqa: E402


def no_network(event: str, args: tuple[object, ...]) -> None:
    if event in {"socket.connect", "socket.getaddrinfo", "socket.sendto", "socket.sendmsg"}:
        raise AssertionError("Network forbidden during event-span offline preparation")


def detail(label: str, value: object) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)
    return '<details><summary>' + html.escape(label) + '</summary><pre>' + html.escape(text) + '</pre></details>'


def structural_controls(value: dict, source: dict) -> list[dict]:
    """Prespecified mutations of a constructed fixture, never model responses."""
    rows = []
    for name in ("blank_diagnostic", "whitespace_diagnostic", "present_empty", "missing_nonempty", "duration_status_relation",
                 "target_present_empty", "target_missing_nonempty", "outside_span", "reversed_span", "duplicate_event", "unknown_target",
                 "integral_float_address"):
        mutated = copy.deepcopy(value)
        event = mutated["events"][0]
        if name == "blank_diagnostic":
            mutated["diagnostic"] = ""
        elif name == "whitespace_diagnostic":
            mutated["diagnostic"] = " \n"
        elif name == "present_empty":
            event["sample"] = {"status": "present", "spans": []}
        elif name == "missing_nonempty":
            event["sample"] = {"status": "not_found", "spans": [event["operation"]]}
        elif name == "duration_status_relation":
            event["duration"]["relation"] = "not_established"
        elif name == "target_present_empty":
            mutated["target"] = {"status": "present", "event_ids": []}
        elif name == "target_missing_nonempty":
            mutated["target"] = {"status": "uncertain", "event_ids": [event["id"]]}
        elif name == "outside_span":
            event["operation"]["last"] = len(source["tokens"])
        elif name == "reversed_span":
            event["operation"] = {"first": 2, "last": 0}
        elif name == "duplicate_event":
            mutated["events"][1]["id"] = event["id"]
        elif name == "unknown_target":
            mutated["target"]["event_ids"] = ["E999"]
        else:
            event["operation"]["first"] = float(event["operation"]["first"])
        try:
            validate_reply(mutated, source)
        except ValueError as exc:
            error = str(exc)
        else:
            raise ValueError("Invalid constructed control unexpectedly passed: " + name)
        rows.append({"id": name, "fixture": mutated, "expected_schema_valid": name in {
            "reversed_span", "duplicate_event", "unknown_target", "integral_float_address"}, "local_valid": False, "local_error": error})
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sys.addaudithook(no_network)
    import fitz

    parent = ROOT / "output/real_experiment_cases_20261029/review_v02"
    fixture_path = ROOT / "docs/records/event_span_fixtures_v0.2.json"
    dataset_path = ROOT / "docs/records/real_experiment_cases_v0.1.json"
    build_path = ROOT / "output/event_spans_v02_20261029/build_manifest_v01.json"
    files.verify_manifest(parent)
    previous = json.loads((parent / "report.json").read_bytes())
    files.verify(previous["bindings"])
    build = json.loads(build_path.read_bytes())
    files.verify(build["bindings"])
    if files.sha(fixture_path.read_bytes()) != build["fixture_sha256"]:
        raise ValueError("Fixture annotations changed")
    fixtures = json.loads(fixture_path.read_bytes())
    dataset = json.loads(dataset_path.read_bytes())
    prepared_fixtures = {f["case_id"]: f for f in fixtures["cases"]}
    if len(prepared_fixtures) != len(fixtures["cases"]) or set(prepared_fixtures) != {c["id"] for c in dataset["cases"]}:
        raise ValueError("Fixture scope differs from all twelve source cases")
    bindings = {**previous["bindings"], **build["bindings"], **files.bindings([
        Path(__file__), ROOT / "scripts/event_spans_v02.py", ROOT / "scripts/event_span_checks_v02.py",
        ROOT / "tests/unit/test_event_spans_v02.py", ROOT / "docs/records/event_spans_v0.2_protocol.md",
        ROOT / "scripts/check_event_span_schema_v02.py",
        fixture_path, dataset_path, build_path, parent / "report.json", parent / "manifest.json"])}
    # Verify old output manifests as immutable history; do not run or reinterpret v0.1 replies as v0.2.
    for folder in (ROOT / "output/gigachat_event_pilot_20261029/review_v02",
                   ROOT / "output/event_duration_evaluation_20261029/review_v01"):
        files.verify_manifest(folder)
        bindings.update(files.bindings([folder / "manifest.json"]))
    pages = {(p["article_id"], p["page_number"], p["text_layer_id"]): p for p in previous["full_source_pages"]}
    registry = json.loads((ROOT / "output/experiment_sentence_links_20261029/review_v02/report.json").read_bytes())
    articles = {}
    for row in registry["cases"]:
        for article in json.loads((Path(row["prepared_path"]) / "articles.json").read_bytes()):
            articles[article["article_id"]] = article
    verified_pages, selected_articles, rows, artifacts = set(), {}, [], []
    for case in dataset["cases"]:
        fixture = prepared_fixtures[case["id"]]
        source = catalog(case["exact_text"])
        if fixture["source"] != case["source"] or fixture["exact_text_sha256"] != source["exact_text_sha256"]:
            raise ValueError("Fixture source identity differs")
        identity = case["source"]
        page = pages[(case["article_id"], case["page"], identity["text_layer_id"])]
        pdf = Path(identity["original_pdf_path"])
        if files.sha(pdf.read_bytes()) != identity["original_pdf_sha256"]:
            raise ValueError("Original PDF hash differs")
        if files.sha(page["page_text"].encode()) != identity["page_text_sha256"] or (
                page["page_text"][case["page_start_offset"]:case["page_end_offset"]] != case["exact_text"]):
            raise ValueError("Raw source page or excerpt offsets differ")
        if source["exact_text_sha256"] != case["quote_sha256"]:
            raise ValueError("Source excerpt hash differs")
        key = (str(pdf), case["page"])
        if key not in verified_pages:
            with fitz.open(pdf) as document:
                if document[case["page"] - 1].get_text("text") != page["page_text"]:
                    raise ValueError("Fresh PDF extraction differs")
            verified_pages.add(key)
        article = articles[case["article_id"]]
        selected_articles[case["article_id"]] = article
        request = build_request(case["question"], source, model="GigaChat-2-Max", max_tokens=1200)
        # Request contains no fixtures, expected labels, prior replies, IDs of articles, or metadata.
        if json.loads(request["messages"][1]["content"]) != {"question": case["question"], "source": source}:
            raise ValueError("Annotation leakage into request")
        raw = files.encode(request)
        restored = validate_reply(fixture["contract_fixture"], source)
        comparison = compare(source, fixture["reference"], restored)
        rows.append({"case": case, "source": source, "constructed_fixture": fixture,
                     "restored_constructed_fixture": restored, "preliminary_checks": comparison,
                     "full_registered_page": page, "request_sha256": files.sha(raw), "request_bytes": len(raw),
                     "sent": False, "slot_reserved": False, "model_output": None})
        artifacts.append((case["id"], raw))
    first = rows[0]
    controls = structural_controls(first["constructed_fixture"]["contract_fixture"], first["source"])
    protonation = next(r for r in rows if r["case"]["id"] == "protonation_missing_time")
    wrong_stage = copy.deepcopy(protonation["constructed_fixture"]["contract_fixture"])
    drying = next(e for e in wrong_stage["events"] if e["kind"] == "drying")
    storage = next(e for e in wrong_stage["events"] if e["kind"] == "storage")
    drying["duration"]["spans"] += storage["duration"]["spans"]
    wrong_stage_result = compare(protonation["source"], protonation["constructed_fixture"]["reference"],
                                 validate_reply(wrong_stage, protonation["source"]))
    if not any(c["state"] == "forbidden_binding_proposed" for c in wrong_stage_result["checks"]):
        raise ValueError("Wrong-stage development control failed to expose annotated boundary")
    checks = Counter(c["state"] for row in rows for c in row["preliminary_checks"]["checks"])
    summary = {"cases": len(rows), "source_documents": len(selected_articles), "fresh_pdf_pages_verified": len(verified_pages),
               "constructed_events": sum(len(r["constructed_fixture"]["contract_fixture"]["events"]) for r in rows),
               "constructed_relations": sum(len(r["constructed_fixture"]["contract_fixture"]["relations"]) for r in rows),
               "preliminary_field_checks": dict(checks), "invalid_structural_controls_rejected_locally": len(controls),
               "wrong_stage_control": "formally_valid_but_forbidden_binding_proposed_against_annotation",
               "candidate_requests_unsent": len(rows), "new_api_oauth_calls": 0, "new_slot_reservations": 0,
               "scientific_acceptance": "not_evaluated", "independent_accuracy": None}
    report = {"version": VERSION, "bindings": bindings, "runtime_versions": {"python": sys.version, "pymupdf": fitz.VersionBind},
              "summary": summary, "cases": rows, "structural_controls": controls,
              "wrong_stage_control": {"case_id": "protonation_missing_time", "fixture": wrong_stage, "comparison": wrong_stage_result},
              "schema_validation": "reported_separately_in_schema_check_not_provider_validation", "runtime_installed": False}
    body = ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>ARIADNE — exact-span contract v0.2</title>'
            '<style>body{font:16px system-ui;margin:24px}table{border-collapse:collapse;width:100%}td,th{border:1px solid #abc;'
            'padding:8px;vertical-align:top}pre,blockquote{white-space:pre-wrap;overflow-wrap:anywhere}'
            '[hidden]{display:none!important}</style><h1>Контракт событий v0.2: точные фрагменты</h1>'
            '<p>12 известных фрагментов. Все приведённые события составлены ассистентом для проверки контракта; '
            'ответов модели нет. Запросы не отправлены, slots не заняты. Это не независимая оценка качества. '
            'Точность ссылок не подтверждает научное назначение, атомарность или полноту событий. '
            'Семантика target и связей между событиями этим оценщиком не проверяется.</p><p>Algorithm: '
            + VERSION + '; snapshot: ' + files.sha(files.encode(bindings)) + '</p><label>Поиск <input id="q" type="search"></label>'
            + detail("Сводка", summary) + detail("Отрицательные структурные примеры", controls)
            + detail("Контроль смешения сушки и хранения", report["wrong_stage_control"]))
    for row in rows:
        case = row["case"]
        body += '<article data-case data-search><h2>' + html.escape(case["id"]) + '</h2><p>' + html.escape(case["question"]) + '</p>'
        body += '<blockquote>' + html.escape(case["exact_text"]) + '</blockquote><a href="' + html.escape(
            Path(case["source"]["original_pdf_path"]).as_uri() + '#page=' + str(case["page"]), quote=True) + '">Original PDF</a>'
        body += ('<p>Модель не запускалась. Native candidate: ' + str(row["request_bytes"])
                 + ' bytes; SHA256 ' + row["request_sha256"] + '</p>')
        for label, field in (("События ассистента, не ответ модели", "restored_constructed_fixture"),
                             ("Предварительные проверки привязок", "preliminary_checks"), ("Разметка и open notes", "constructed_fixture"),
                             ("Нейтральный каталог точных токенов", "source"),
                             ("Полная зарегистрированная страница", "full_registered_page"),
                             ("Исходный вопрос, offsets, hashes и прежние заметки", "case")):
            body += detail(label, row[field])
        request = json.loads(next(raw for case_id, raw in artifacts if case_id == case["id"]))
        body += detail("Полный неотправленный native request", request) + '</article>'
    body += '<h2>TAC: все 5 работ этапа</h2><table><thead><tr>' + ''.join('<th>' + x + '</th>' for x in (
        "Title", "Authors", "Journal", "Year", "Abstract", "Conclusions", "Terms", "Original file")) + '</tr></thead><tbody>'
    for article in selected_articles.values():
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
    if check.cases != 12 or check.tac != 5:
        raise ValueError("HTML does not contain the complete declared scope")
    for href in check.links:
        parsed = urlparse(href)
        if parsed.scheme != "file" or not Path(url2pathname(parsed.path)).is_file():
            raise ValueError("Broken local source PDF link")
    report["html_qa"] = {"method": "static_not_browser", "case_cards": check.cases, "tac_rows": check.tac,
                         "existing_original_pdf_links": len(check.links)}
    files.verify(bindings)
    args.output.mkdir(parents=True, exist_ok=False)
    request_folder = args.output / "requests"
    request_folder.mkdir()
    for case_id, raw in artifacts:
        files.save(request_folder / (case_id + ".json"), raw)
    for name, digest in bindings.items():
        path = Path(name)
        if path.is_relative_to(ROOT) and path.suffix in {".py", ".md", ".json"}:
            target = args.output / "source_snapshot" / path.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            raw = path.read_bytes()
            if files.sha(raw) != digest:
                raise ValueError("Input changed during snapshot")
            files.save(target, raw)
    files.write(args.output / "report.json", report)
    files.save(args.output / "review.html", body.encode())
    files.manifest(args.output)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
