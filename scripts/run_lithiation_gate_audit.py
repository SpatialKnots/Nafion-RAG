"""Source-bound offline gate counterexamples; no provider, DB or API calls."""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.generation import evidence_adequacy as gate  # noqa: E402
from app.retrieval.cross_lingual import glossary_terms_for_concepts  # noqa: E402
from scripts import gigachat_answer_smoke as files  # noqa: E402
from scripts import lithiation_gate_audit as audit  # noqa: E402

PROTOCOL = ROOT / "docs/records/lithiation_gate_audit_protocol_v0.1.md"


def run(prepared: Path, output: Path) -> dict[str, Any]:
    import fitz

    if output.exists():
        raise FileExistsError(output)
    bindings = files.bindings([
        Path(__file__), Path(audit.__file__), Path(gate.__file__), PROTOCOL,
        ROOT / "app/generation/evidence_selection.py", ROOT / "docs/cross_lingual_glossary.yaml",
        ROOT / "app/generation/required_concepts.py", ROOT / "app/generation/relation_requirements.py",
        ROOT / "tests/unit/test_lithiation_gate_audit.py",
    ])
    cases, pages, articles, article_cases = [], {}, {}, {}
    for case_id in ("q1_swelling_forms", "q2_best_mixture", "q3_lithiation_methods"):
        folder = prepared / case_id / "prepared"
        files.verify_manifest(folder)
        bindings.update(files.bindings([p for p in folder.iterdir() if p.is_file()]))
        trace = json.loads((folder / "trace.json").read_bytes())
        request = json.loads((folder / "api_request.json").read_bytes())
        sources = json.loads((folder / "sources.json").read_bytes())
        before = trace["metadata"]["evidence_adequacy"]
        terms = glossary_terms_for_concepts(list(before["concept_coverage"]["details"]))
        texts = [e["text"] for e in trace["evidence"]]
        variants = {name: audit.probe(request["question"], texts, name, concept_terms=terms) for name in audit.VARIANTS}
        if {key: variants["baseline"][key] for key in before} != before:
            raise ValueError(f"Frozen/current gate mismatch: {case_id}")
        cases.append({"id": case_id, "question": request["question"], "frozen_adequacy": before,
                      "baseline_identical": True, "variants": variants, "evidence": trace["evidence"],
                      "occurrences": [{"citation_id": e["citation_id"], "chunk_id": e["chunk_id"],
                                       **item} for e in trace["evidence"] for item in audit.source_occurrences(e["text"])]})
        for page in sources["pages"].values():
            key = (page["article_id"], page["page_number"])
            if key not in pages:
                original = Path(page["original_pdf_path"])
                layer = Path(page["layer_pdf_path"])
                if files.sha(original.read_bytes()) != page["original_pdf_sha256"]:
                    raise ValueError(f"Original PDF changed: {original}")
                if files.sha(layer.read_bytes()) != page["layer_pdf_sha256"]:
                    raise ValueError(f"Selected layer changed: {layer}")
                with fitz.open(layer) as document:
                    text = document[page["page_number"] - 1].get_text()
                if text != page["page_text"] or files.sha(text.encode()) != page["page_text_sha256"]:
                    raise ValueError(f"Fresh extraction mismatch: {key}")
                pages[key] = page
                bindings.update(files.bindings([original, layer]))
        selected_ids = {e["article_id"] for e in trace["evidence"]}
        values = json.loads((folder / "articles.json").read_bytes())
        for value in values:
            article_id = value["article_id"]
            if article_id in selected_ids:
                if article_id in articles and articles[article_id] != value:
                    raise ValueError(f"Frozen article metadata mismatch: {article_id}")
                articles[article_id] = value
                article_cases.setdefault(article_id, []).append(case_id)
    controls = audit.constructed_controls()
    by_id = {row["id"]: row for row in controls}
    if not by_id["negated_other_form"]["variants"]["noun_alias_only"]["adequate"]:
        raise ValueError("Expected lexical workaround counterexample did not reproduce")
    if not by_id["no_operation"]["variants"]["drop_question_words_only"]["adequate"]:
        raise ValueError("Expected stopword workaround counterexample did not reproduce")
    if any(c["variants"][name] != c["variants"]["baseline"] for c in cases[:2] for name in audit.VARIANTS):
        raise ValueError("Unrelated frozen gate control changed")
    if len(articles) != 5:
        raise ValueError("Expected all five selected works across target and controls")
    report = {"version": audit.VERSION, "bindings": bindings, "cases": cases, "controls": controls,
              "articles": articles, "article_case_membership": article_cases, "fresh_pages": list(pages.values()),
              "diagnostic_scope": "frozen_evidence_lexical_gate_only_not_selection_or_scientific_validation",
              "variant_policy": {"noun_alias": audit.NOUN_ALIAS, "drop_words": sorted(audit.DROP_WORDS)},
              "summary": {"original_gate_metadata_reproduced": 3, "fresh_pdf_pages": len(pages),
                          "source_works": len({k[0] for k in pages}), "constructed_controls": len(controls),
                          "tac_works": len(articles),
                          "tac_works_q3": sum("q3_lithiation_methods" in ids for ids in article_cases.values()),
                          "new_model_oauth_db_calls": 0,
                          "native_requests_created": 0, "slot_reservations": 0,
                          "runtime_changes": False, "candidate_verdict": "do_not_promote_lexical_shortcuts",
                          "independent_accuracy": None, "scientific_acceptance": "not_established"}}
    files.verify(bindings)
    output.mkdir(parents=True)
    files.write(output / "report.json", report)
    render(report, output)
    (output / "source_snapshot").mkdir()
    for path in (Path(__file__), Path(audit.__file__), PROTOCOL, ROOT / "tests/unit/test_lithiation_gate_audit.py"):
        files.save(output / "source_snapshot" / path.name, path.read_bytes())
    files.manifest(output)
    return report["summary"]


def render(report: dict[str, Any], output: Path) -> None:
    def esc(value: Any) -> str:
        return html.escape(str(value), quote=True)

    def detail(label: str, value: Any) -> str:
        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)
        return '<details><summary>' + esc(label) + '</summary><pre>' + esc(text) + '</pre></details>'

    body = ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>ARIADNE — отказ и контрпримеры</title>'
            '<style>body{font:16px system-ui;margin:24px;color:#18333f}table{border-collapse:collapse;width:100%}'
            'td,th{border:1px solid #abc;padding:8px;vertical-align:top}pre{white-space:pre-wrap;overflow-wrap:anywhere}'
            '[hidden]{display:none!important}</style><h1>Литирование: почему lexical shortcut недостаточен</h1>'
            '<p>Версия ' + esc(report["version"]) + '. Исходные три gate metadata воспроизведены без изменений. '
            'Рассматривается фиксированный evidence, не новый поиск. Ни один вариант не установлен в runtime.</p>'
            '<p>«Допуск» ниже — решение лексической эвристики, не подтверждение опыта или полноты ответа. '
            'Словоформа исправляет исходный отказ, но допускает отрицание, заголовок, будущее действие и '
            'операцию над другим материалом. Удаление общих слов допускает одно упоминание Nafion.</p>')
    for row in [*report["cases"], *report["controls"]]:
        body += '<h2>' + esc(row["id"]) + '</h2><p>' + esc(row["question"]) + '</p>'
        if "constructed_intent" in row:
            body += '<p>Искусственный контроль ассистента; independent gold отсутствует: ' + esc(row["constructed_intent"]) + '</p>'
        body += '<table><tr><th>Вариант</th><th>Допуск</th><th>Matched terms</th><th>Coverage/top</th><th>Диагностика</th></tr>'
        for name, result in row["variants"].items():
            body += ('<tr><td>' + esc(name) + '</td><td>' + esc(result["adequate"]) + '</td><td>'
                     + esc(result["matched_terms"]) + '</td><td>' + esc([result["coverage"], result["top_coverage"]])
                     + '</td><td>' + detail("Все поля без исправлений", result) + '</td></tr>')
        body += '</table>'
        for item in row.get("evidence", []):
            body += detail(item["citation_id"] + ': ' + item["title"] + ' с.'
                           + str(item["page_start"]) + '–' + str(item["page_end"]), item)
        if "occurrences" in row:
            body += detail("Точные source surfaces и offsets внутри chunks", row["occurrences"])
        if "texts" in row:
            body += detail("Точные искусственные тексты", row["texts"])
    body += ('<h2>TAC: все пять работ целевого вопроса и контролей</h2><p>Metadata из frozen input; '
             'несобранные поля явно неизвестны.</p><label>Поиск <input id="q" type="search"></label>'
             '<table id="tac"><thead><tr>' + ''.join('<th>' + h + '</th>' for h in
             ('Title', 'Authors', 'Journal', 'Year', 'Abstract', 'Conclusions', 'Terms', 'hyperlink to original file'))
             + '</tr></thead><tbody>')
    for article in report["articles"].values():
        body += '<tr>'
        for key in ('title', 'authors', 'journal', 'year', 'abstract', 'conclusions', 'terms'):
            value = article.get(key)
            body += '<td>' + (detail("Полный текст / metadata", value) if value is not None else 'Неизвестно / не собрано') + '</td>'
        body += ('<td><a href="' + esc(Path(article["original_pdf_path"]).as_uri()) + '">Оригинальный PDF</a>'
                 + detail("Вопросы в этой стадии", report["article_case_membership"][article["article_id"]])
                 + detail("Provenance", article) + '</td></tr>')
    body += ('</tbody></table>' + detail("Итог и ограничения", report["summary"])
             + '<script>document.getElementById("q").addEventListener("input",e=>{const s=e.target.value.toLowerCase();'
             'document.querySelectorAll("#tac tbody tr").forEach(r=>r.hidden=!r.textContent.toLowerCase().includes(s))});'
             '</script></html>')
    files.save(output / "review.html", body.encode())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    policy = files.NetworkPolicy()
    sys.addaudithook(policy)
    result = run(args.prepared, args.output)
    if policy.denied:
        raise ValueError("Unexpected network attempt")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
