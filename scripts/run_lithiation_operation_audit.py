"""Run the offline source-only operation sidecar on frozen and post-hoc text."""

from __future__ import annotations

import argparse
import html
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import event_value_ownership_audit as mapping  # noqa: E402
from scripts import gigachat_answer_smoke as files  # noqa: E402
from scripts import lithiation_operation_audit as operation  # noqa: E402

PROTOCOL = ROOT / "docs/records/lithiation_operation_audit_protocol_v0.1.md"
EXTRA_CONTROLS = (
    ("explicit_ru_membrane", "Проводили литирование мембран Nafion в 2.0 M LiOH при 60–80 °C в течение 120 мин."),
    ("explicit_en_membrane", "Nafion membranes were lithiated in LiOH for 2 hours."),
    ("explicit_ru_dispersion", "Проводили литирование водно-спиртовой дисперсии Nafion раствором LiOH."),
    ("cleaning_then", "Nafion was cleaned for 2 hours, then lithiated in LiOH."),
    ("cleaning_same_region", "После очистки Nafion в течение 2 ч проводили литирование Nafion в LiOH."),
    ("negated_reagent", "Для литирования Nafion не использовали LiOH."),
    ("interrogative", "Литирование Nafion проводили?"),
    ("counterfactual", "Литирование Nafion проводили бы при 60 °C."),
    ("shared_conditions", "Nafion was lithiated under the same conditions in LiOH."),
    ("two_repeated_times", "Nafion was lithiated for 2 hours. Nafion was not lithiated for 2 hours."),
    ("source_line_break", "Проводили литиро-\nвание мембран Nafion в 2.0 М LiOH при 60 °C в течение 120 мин."),
)


def run(prior_folder: Path, output: Path) -> dict[str, Any]:
    import fitz

    if output.exists():
        raise FileExistsError(output)
    files.verify_manifest(prior_folder)
    prior = json.loads((prior_folder / "report.json").read_bytes())
    files.verify(prior["bindings"])
    bindings = {**prior["bindings"], **files.bindings([
        Path(__file__), Path(operation.__file__), Path(mapping.__file__), PROTOCOL,
        ROOT / "tests/unit/test_lithiation_operation_audit.py", prior_folder / "report.json",
        prior_folder / "manifest.json",
    ])}
    pages = list(prior["fresh_pages"])
    for page in pages:
        original, layer = Path(page["original_pdf_path"]), Path(page["layer_pdf_path"])
        if files.sha(original.read_bytes()) != page["original_pdf_sha256"]:
            raise ValueError("Original PDF drift")
        if files.sha(layer.read_bytes()) != page["layer_pdf_sha256"]:
            raise ValueError("Layer PDF drift")
        with fitz.open(layer) as pdf:
            text = pdf[page["page_number"] - 1].get_text()
        if text != page["page_text"] or files.sha(text.encode()) != page["page_text_sha256"]:
            raise ValueError("Fresh page extraction drift")
    q3, = [case for case in prior["cases"] if case["id"] == "q3_lithiation_methods"]
    dissertation_id = q3["evidence"][0]["article_id"]
    exemplar = next(page for page in pages if page["article_id"] == dissertation_id and page["page_number"] == 51)
    with fitz.open(exemplar["original_pdf_path"]) as pdf:
        extra = pdf[51].get_text()
    posthoc = {"article_id": dissertation_id, "page_number": 52,
               "original_pdf_path": exemplar["original_pdf_path"],
               "original_pdf_sha256": exemplar["original_pdf_sha256"], "text_layer": "original",
               "page_text": extra, "page_text_sha256": files.sha(extra.encode()),
               "origin": "assistant_posthoc_original_page_not_supplied_to_q3",
               "q3_model_call": False}
    rows = []
    for case in prior["cases"]:
        for evidence in case["evidence"]:
            rows.append({"id": case["id"] + ":" + evidence["citation_id"], "text": evidence["text"],
                         "origin": "frozen_original_answer_evidence", "source": evidence,
                         "analysis": operation.audit(evidence["text"])})
    rows.append({"id": "posthoc_dissertation_p52", "text": extra, "origin": posthoc["origin"],
                 "source": posthoc, "analysis": operation.audit(extra)})
    for control in prior["controls"]:
        for index, text in enumerate(control["texts"]):
            rows.append({"id": control["id"] + ":" + str(index), "text": text,
                         "origin": "assistant_constructed_previous_control_not_gold", "source": None,
                         "analysis": operation.audit(text)})
    for case_id, text in EXTRA_CONTROLS:
        rows.append({"id": case_id, "text": text, "source": None,
                     "origin": "assistant_constructed_new_control_not_gold", "analysis": operation.audit(text)})
    for row in rows:
        validate_spans(row["text"], row["analysis"])
    totals = Counter(item["state"] for row in rows for item in row["analysis"]["operations"])
    q3_rows = [row for row in rows if row["id"].startswith("q3_lithiation_methods:")]
    real_q3 = Counter(item["state"] for row in q3_rows for item in row["analysis"]["operations"])
    summary = {"source_rows": sum(row["source"] is not None for row in rows),
               "constructed_texts": sum(row["source"] is None for row in rows),
               "operation_states_all_rows": dict(totals), "q3_original_operation_states": dict(real_q3),
               "q3_original_field_rows": sum(len(item["fields"]) for row in q3_rows for item in row["analysis"]["operations"]),
               "q3_original_unassigned_fields": sum(len(row["analysis"]["unassigned_fields"]) for row in q3_rows),
               "fresh_original_pages": len({(p["article_id"], p["page_number"]) for p in [*pages, posthoc]}),
               "tac_works": len(prior["articles"]), "scientific_confirmations": 0,
               "runtime_changes": False, "new_model_oauth_db_calls": 0, "requests_or_slots_created": 0,
               "independent_accuracy": None, "catalogue_completeness": "not_established"}
    report = {"version": operation.VERSION, "bindings": bindings, "rows": rows,
              "articles": prior["articles"], "article_case_membership": prior["article_case_membership"],
              "posthoc_page": posthoc, "original_gate_metadata": [c["frozen_adequacy"] for c in prior["cases"]],
              "summary": summary, "annotation_policy": "assistant_development_controls_not_independent_gold"}
    files.verify(bindings)
    output.mkdir(parents=True)
    files.write(output / "report.json", report)
    render(report, output)
    (output / "source_snapshot").mkdir()
    for path in (Path(__file__), Path(operation.__file__), Path(mapping.__file__), PROTOCOL,
                 ROOT / "tests/unit/test_lithiation_operation_audit.py"):
        files.save(output / "source_snapshot" / path.name, path.read_bytes())
    files.manifest(output)
    return summary


def validate_spans(text: str, value: Any) -> None:
    if isinstance(value, dict):
        if {"start", "end", "text"} <= value.keys():
            if text[value["start"]:value["end"]] != value["text"]:
                raise ValueError("Exact source span drift")
        for child in value.values():
            validate_spans(text, child)
    elif isinstance(value, list):
        for child in value:
            validate_spans(text, child)


def render(report: dict[str, Any], output: Path) -> None:
    def esc(value: Any) -> str:
        return html.escape(str(value), quote=True)

    def detail(label: str, value: Any) -> str:
        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)
        return '<details><summary>' + esc(label) + '</summary><pre>' + esc(text) + '</pre></details>'

    body = ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>ARIADNE — операции литирования</title>'
            '<style>body{font:16px system-ui;color:#18333f;margin:24px}table{border-collapse:collapse;width:100%}'
            'td,th{border:1px solid #abc;padding:8px;vertical-align:top}pre{white-space:pre-wrap;overflow-wrap:anywhere}'
            '[hidden]{display:none!important}</style><h1>Литирование: операция, статус, материал и условия</h1>'
            '<p>Версия ' + esc(report["version"]) + '. Отдельный finite sidecar; рабочий /answer не изменён. '
            'Положительный шаблон — candidate_unverified, не подтверждение опыта/владельца условий. '
            'Отрицания, будущее, заголовки, чужой материал, смешанные операции и ссылки остаются blocked/unresolved.</p>'
            '<p>Источник всех rows указан отдельно. Страница52 — post-hoc проверка; она не передавалась '
            'исходному q3. По q3 модели не вызывали. Искусственные controls не являются независимым gold. '
            'Никакая полнота методик не установлена.</p>')
    for row in report["rows"]:
        body += '<h2>' + esc(row["id"]) + '</h2><p>' + esc(row["origin"]) + '</p>'
        source = row["source"]
        if source:
            article = report["articles"][source["article_id"]]
            page = source.get("page_start", source.get("page_number"))
            body += ('<a href="' + esc(Path(article["original_pdf_path"]).as_uri() + '#page=' + str(page))
                     + '">' + esc(article["title"]) + ' — с.' + str(page) + '</a>')
        body += detail("Полный точный source text", row["text"])
        body += ('<table><tr><th>Операция / регион</th><th>Статус</th><th>Связь с Nafion</th>'
                 '<th>Решение</th><th>Поля / диагностика</th></tr>')
        for item in row["analysis"]["operations"]:
            body += ('<tr><td>' + detail("Точные spans", {"region": item["region"], "operations": item["operation_spans"]})
                     + '</td><td>' + esc(item["status"]) + detail("Status cues", item["status_cues"])
                     + '</td><td>' + detail("Local templates, не proof", item["target_links"])
                     + '</td><td>' + esc(item["state"]) + '</td><td>'
                     + detail("Поля без установления владельца", item["fields"]) + detail("Диагностика", item["diagnostics"])
                     + '</td></tr>')
        body += '</table>' + detail("Все поля вне распознанных регионов", row["analysis"]["unassigned_fields"])
        body += detail("Полный результат и ограничения", row["analysis"])
    body += ('<h2>TAC: все пять работ</h2><p>Frozen metadata; неизвестные поля сохранены.</p>'
             '<label>Поиск <input id="q" type="search"></label><table id="tac"><thead><tr>'
             + ''.join('<th>' + h + '</th>' for h in ('Title', 'Authors', 'Journal', 'Year', 'Abstract', 'Conclusions',
                                                    'Terms', 'hyperlink to original file')) + '</tr></thead><tbody>')
    for article in report["articles"].values():
        body += '<tr>'
        for key in ('title', 'authors', 'journal', 'year', 'abstract', 'conclusions', 'terms'):
            value = article.get(key)
            body += '<td>' + (detail("Полный текст / metadata", value) if value is not None else 'Неизвестно / не собрано') + '</td>'
        body += ('<td><a href="' + esc(Path(article["original_pdf_path"]).as_uri()) + '">Оригинальный PDF</a>'
                 + detail("Provenance", article) + '</td></tr>')
    body += ('</tbody></table>' + detail("Итог / bindings", {"summary": report["summary"], "bindings": report["bindings"]})
             + '<script>document.getElementById("q").addEventListener("input",e=>{const s=e.target.value.toLowerCase();'
             'document.querySelectorAll("#tac tbody tr").forEach(r=>r.hidden=!r.textContent.toLowerCase().includes(s))});'
             '</script></html>')
    files.save(output / "review.html", body.encode())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prior", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    policy = files.NetworkPolicy()
    sys.addaudithook(policy)
    summary = run(args.prior, args.output)
    if policy.denied:
        raise ValueError("Unexpected network attempt")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
