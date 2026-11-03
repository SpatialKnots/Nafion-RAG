"""Offline explicit subject links with raw-to-original-page anchors."""

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

from scripts import gigachat_answer_smoke as files  # noqa: E402
from scripts import lithiation_subject_context_audit as subject  # noqa: E402
from scripts.run_lithiation_operation_audit import validate_spans  # noqa: E402

PROTOCOL = ROOT / "docs/records/lithiation_subject_context_protocol_v0.1.md"
CONTROLS = ROOT / "docs/records/lithiation_subject_context_controls_v0.1.json"


def anchors(text: str, article_id: str, analysis: dict[str, Any], pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    values = []
    for attempt in analysis["attempts"]:
        for index, link in enumerate(attempt["links"]):
            selected = {"operation": link["operation_span"]}
            if link.get("subject_heading"):
                selected["heading"] = link["subject_heading"]["span"]
            for key in ("caption", "subpanel"):
                if link.get(key):
                    selected[key] = link[key]["span"]
            if link.get("reference_span"):
                selected["reference"] = link["reference_span"]
            for name, span in selected.items():
                if text[span["start"]:span["end"]] != span["text"]:
                    raise ValueError("Context span drift")
                matches = []
                for page in pages:
                    if page["article_id"] != article_id:
                        continue
                    offset = page["page_text"].find(span["text"])
                    while offset >= 0:
                        matches.append({"article_id": article_id, "page_number": page["page_number"],
                                        "original_pdf_path": page["original_pdf_path"],
                                        "text_layer": page["text_layer"], "start": offset,
                                        "end": offset + len(span["text"]), "exact_text": span["text"]})
                        offset = page["page_text"].find(span["text"], offset + 1)
                values.append({"operation_index": attempt["operation_index"], "link_index": index, "kind": name,
                               "chunk_span": span, "original_page_matches": matches,
                               "anchor_state": "unique_exact" if len(matches) == 1 else "missing_or_ambiguous"})
    return values


def run(prior_folder: Path, gate_folder: Path, output: Path) -> dict[str, Any]:
    import fitz

    if output.exists():
        raise FileExistsError(output)
    files.verify_manifest(prior_folder)
    prior = json.loads((prior_folder / "report.json").read_bytes())
    files.verify(prior["bindings"])
    gate_file = (gate_folder / "report.json").resolve()
    if str(gate_file) not in prior["bindings"]:
        raise ValueError("Gate report must be a bound prior-stage input")
    gate = json.loads(gate_file.read_bytes())
    pages = [*gate["fresh_pages"], prior["posthoc_page"]]
    unique_pages = {(p["article_id"], p["page_number"]): p for p in pages}
    for page in unique_pages.values():
        original = Path(page["original_pdf_path"])
        layer = Path(page.get("layer_pdf_path", original))
        if files.sha(original.read_bytes()) != page["original_pdf_sha256"]:
            raise ValueError("Original PDF drift")
        with fitz.open(layer) as pdf:
            text = pdf[page["page_number"] - 1].get_text()
        if text != page["page_text"]:
            raise ValueError("Original selected-page extraction drift")
    bindings = {**prior["bindings"], **files.bindings([
        Path(__file__), Path(subject.__file__), PROTOCOL, CONTROLS,
        ROOT / "tests/unit/test_lithiation_subject_context_audit.py", prior_folder / "report.json",
        prior_folder / "manifest.json",
    ])}
    rows = []
    for old in prior["rows"]:
        analysis = subject.audit(old["text"])
        if analysis["baseline"] != old["analysis"]:
            raise ValueError("Frozen operation/field baseline changed")
        rows.append({**old, "subject_context": analysis, "baseline_identical": True,
                     "original_page_anchors": anchors(old["text"], old["source"]["article_id"], analysis,
                                                      list(unique_pages.values())) if old["source"] else []})
    controls = json.loads(CONTROLS.read_bytes())
    for control in controls["cases"]:
        rows.append({"id": control["id"], "text": control["text"], "source": None,
                     "origin": controls["origin"], "subject_context": subject.audit(control["text"]),
                     "original_page_anchors": []})
    for row in rows:
        validate_spans(row["text"], row["subject_context"])
    source_states = Counter(a["state"] for row in rows if row["source"] for a in row["subject_context"]["attempts"])
    control_states = Counter(a["state"] for row in rows if not row["source"] for a in row["subject_context"]["attempts"])
    exact = Counter(anchor["anchor_state"] for row in rows for anchor in row["original_page_anchors"])
    summary = {"baseline_rows_identical": len(prior["rows"]), "source_rows": sum(bool(r["source"]) for r in rows),
               "constructed_texts": sum(not r["source"] for r in rows), "source_context_states": dict(source_states),
               "constructed_context_states": dict(control_states), "original_page_anchor_states": dict(exact),
               "fresh_original_pages": len(unique_pages), "tac_works": len(prior["articles"]),
               "performed_or_owner_confirmations": 0, "runtime_changes": False,
               "new_model_oauth_db_calls": 0, "new_requests_or_slots": 0, "independent_accuracy": None}
    report = {"version": subject.VERSION, "bindings": bindings, "rows": rows, "summary": summary,
              "articles": prior["articles"], "original_gate_metadata": prior["original_gate_metadata"],
              "annotation_policy": controls["origin"], "registered_pages": list(unique_pages.values())}
    files.verify(bindings)
    output.mkdir(parents=True)
    files.write(output / "report.json", report)
    render(report, output)
    (output / "source_snapshot").mkdir()
    for path in (Path(__file__), Path(subject.__file__), PROTOCOL, CONTROLS,
                 ROOT / "tests/unit/test_lithiation_subject_context_audit.py"):
        files.save(output / "source_snapshot" / path.name, path.read_bytes())
    files.manifest(output)
    return summary


def render(report: dict[str, Any], output: Path) -> None:
    def esc(value: Any) -> str:
        return html.escape(str(value), quote=True)

    def detail(label: str, value: Any) -> str:
        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)
        return '<details><summary>' + esc(label) + '</summary><pre>' + esc(text) + '</pre></details>'

    body = ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>ARIADNE — субъект операции</title>'
            '<style>body{font:16px system-ui;margin:24px;color:#18333f}table{border-collapse:collapse;width:100%}'
            'td,th{border:1px solid #abc;padding:8px;vertical-align:top}pre{white-space:pre-wrap;overflow-wrap:anywhere}'
            '[hidden]{display:none!important}</style><h1>Субъект раздела и явная ссылка на подрисунок</h1><p>'
            + esc(report["version"]) + '. Новый sidecar; baseline операции/поля и исходные gate metadata сохранены. '
            'Context candidate не подтверждает выполнение, владельца материала или условий; runtime не изменён. '
            'Страница52 остаётся post-hoc, не original q3 input. Искусственные controls не independent gold.</p>')
    for row in report["rows"]:
        body += '<h2>' + esc(row["id"]) + '</h2><p>' + esc(row["origin"]) + '</p>'
        body += detail("Точный source text", row["text"])
        body += '<table><tr><th>Операция</th><th>Контекстное решение</th><th>Все попытки / причины</th></tr>'
        for attempt in row["subject_context"]["attempts"]:
            operation = row["subject_context"]["baseline"]["operations"][attempt["operation_index"]]
            body += ('<tr><td>' + detail("Исходная операция без изменения", operation) + '</td><td>'
                     + esc(attempt["state"]) + '</td><td>' + detail("Links и точные spans", attempt) + '</td></tr>')
        body += '</table>'
        for anchor in row["original_page_anchors"]:
            body += '<p>' + esc(anchor["kind"]) + ': ' + esc(anchor["anchor_state"])
            for match in anchor["original_page_matches"]:
                url = Path(match["original_pdf_path"]).as_uri() + '#page=' + str(match["page_number"])
                body += ' <a href="' + esc(url) + '">Оригинал с.' + str(match["page_number"]) + '</a>'
            body += '</p>' + detail("Exact raw/page anchors", anchor)
        body += detail("Полный sidecar и ограничения", row["subject_context"])
    body += ('<h2>TAC: все пять работ</h2><p>Frozen metadata; неизвестные поля не заполнены.</p>'
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
    body += ('</tbody></table>' + detail("Итоги / bindings", {"summary": report["summary"], "bindings": report["bindings"]})
             + '<script>document.getElementById("q").addEventListener("input",e=>{const s=e.target.value.toLowerCase();'
             'document.querySelectorAll("#tac tbody tr").forEach(r=>r.hidden=!r.textContent.toLowerCase().includes(s))});'
             '</script></html>')
    files.save(output / "review.html", body.encode())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prior", type=Path, required=True)
    parser.add_argument("--gate-review", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    policy = files.NetworkPolicy()
    sys.addaudithook(policy)
    summary = run(args.prior, args.gate_review, args.output)
    if policy.denied:
        raise ValueError("Unexpected network attempt")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
