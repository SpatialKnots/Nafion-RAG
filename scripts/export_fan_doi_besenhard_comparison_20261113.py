"""Read-only side-by-side table of full delivered answers and original references."""

from __future__ import annotations

import html
import json
import re
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse

from markdown_it import MarkdownIt

from scripts import run_fan_doi_besenhard_answers_20261113 as run

f = run.f
LABELS = {
    "core_supported": "Основное содержание подтверждается",
    "partial_or_wording_issue": "Неполнота / формулировка",
    "substantive_discrepancy": "Существенное расхождение",
    "provider_abstained": "Отказ модели",
    "rewrite_rejected": "Ответ не запрашивался",
    "withheld_by_guard": "Ответ удержан проверкой",
}


class Inspector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids, self.links, self.capture, self.raw = [], [], False, []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "tr" and "data-case" in values:
            self.ids.append(values["data-case"])
        if tag == "a" and "href" in values:
            self.links.append(values["href"])
        if tag == "script" and values.get("id") == "comparison-data":
            self.capture = True

    def handle_endtag(self, tag):
        if tag == "script":
            self.capture = False

    def handle_data(self, data):
        if self.capture:
            self.raw.append(data)


def main():
    for name in ("review_v01", "assessment_v01", "final_verification_v01"):
        f.verify_manifest(run.BASE / name)
    original = run.read(run.BASE / "review_v01/report.json")
    assessments = {r["id"]: r for r in run.read(run.BASE / "assessment_v01/assessment.json")["cases"]}
    md = MarkdownIt("commonmark", {"html": False, "breaks": True}).enable("table")
    rows = []
    for source in original["cases"]:
        cid = source["id"]
        body = source.get("api", {}).get("body", {})
        delivered = body.get("answer", {}).get("answer")
        judgment = assessments[cid]
        review = body.get("review") or {}
        native = review.get("native_result") or {}
        rows.append({"id": cid, "article": source["case"]["label"],
            "question": source["question_original"], "answer_delivered": delivered,
            "reference_original": source["reference_answer_verbatim"],
            "reference_source_original": source["reference_source_declaration_verbatim"],
            "category": judgment["category"], "category_label": LABELS[judgment["category"]],
            "review_note": judgment["note"],
            "withheld_native_claims": [c["text"] for c in native.get("claims", [])] if review.get("withheld") else [],
            "original_pdf_path": source["case"]["original_pdf_path"]})
    run.require([r["id"] for r in rows] == run.profile.baseline.IDS, "Expected all thirty original cases")
    output = run.BASE / "comparison_table_v01"
    output.mkdir(exist_ok=False)
    esc = html.escape
    parts = ['<!doctype html><html lang="ru"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1">',
        '<title>ARIADNE — ответы и эталоны, 30 вопросов</title><style>',
        'body{font:15px/1.5 system-ui,sans-serif;color:#172333;background:#f7f8fb;margin:0;padding:24px}',
        'h1{font-size:27px;margin:0 0 8px}.intro{max-width:1100px}.controls{display:flex;gap:12px;flex-wrap:wrap;margin:20px 0}',
        'input,select,button{font:inherit;padding:9px;border:1px solid #b9c5d6;border-radius:6px;background:white}',
        'input{min-width:280px;flex:1}a{color:#165cb0}.scroll{overflow:auto;background:white;border:1px solid #cdd5e0}',
        '.main-table{border-collapse:collapse;table-layout:fixed;width:100%;min-width:1250px}',
        '.main-table>thead>tr>th{position:sticky;top:0;background:#e8eef6;z-index:1;text-align:left}',
        '.main-table>thead>tr>th,.main-table>tbody>tr>td{border:1px solid #d3dae4;padding:12px;vertical-align:top}',
        'th.id{width:4%}th.question{width:17%}th.answer,th.gold{width:27%}th.note{width:25%}',
        'td{overflow-wrap:anywhere}td p:first-child{margin-top:0}td p:last-child{margin-bottom:0}',
        '.status{display:inline-block;font-size:12px;font-weight:650;padding:3px 7px;border-radius:5px;background:#edf1f7}',
        '.substantive_discrepancy .status{background:#ffe5e3;color:#9e2823}',
        '.core_supported .status{background:#e4f2e9;color:#235c38}',
        '.partial_or_wording_issue .status{background:#fff0d5;color:#855615}',
        'details{margin-top:10px}summary{cursor:pointer}.absent{color:#6a4450;font-style:italic}',
        '.gold table{border-collapse:collapse;font-size:13px;width:100%}.gold th,.gold td{border:1px solid #cdd5e0;padding:5px}',
        '.source{font-size:12px;color:#596577;margin-top:12px}.note-text{font-size:13px}',
        '@media print{body{padding:0;background:white}.controls{display:none}.scroll{overflow:visible;border:0}',
        '.main-table{min-width:0;font-size:9px}.main-table>thead>tr>th{position:static}a{color:inherit}}',
        '</style></head><body><h1>Ответы ARIADNE в сравнении с эталонами</h1>',
        '<div class="intro"><p>30 вопросов · Fan, Doi, Besenhard · 13 ноября 2026</p>',
        '<p><b>22 ответа выданы, 3 отказа модели, 1 ответ удержан проверкой, 4 вопроса не отправлялись после rewriting.</b> '
        'Ответы и эталоны приведены полностью. Текст модели не исправлялся. Замечания — предварительная оценка ассистента.</p></div>',
        '<div class="controls"><input id="search" type="search" placeholder="Поиск по вопросам и ответам" aria-label="Поиск">',
        '<select id="article" aria-label="Статья"><option value="">Все статьи</option><option>Fan</option><option>Doi</option>',
        '<option>Besenhard</option></select><select id="category" aria-label="Результат"><option value="">Все результаты</option>']
    parts += ['<option value="' + key + '">' + esc(label) + '</option>' for key, label in LABELS.items()]
    parts += ['</select><button onclick="window.print()">Печать</button></div><p id="count">Показано 30 из 30</p>',
        '<div class="scroll"><table class="main-table" id="comparison"><thead><tr><th class="id">ID</th>',
        '<th class="question">Вопрос</th><th class="answer">Ответ ARIADNE</th>',
        '<th class="gold">Эталонный ответ</th><th class="note">Результат сверки</th></tr></thead><tbody>']
    for row in rows:
        parts.append('<tr data-case="' + row["id"] + '" data-article="' + row["article"] + '" data-category="'
            + row["category"] + '" class="' + row["category"] + '"><td><b>' + row["id"] + '</b></td><td>'
            + esc(row["question"]) + '</td><td class="answer">')
        if row["answer_delivered"] is not None:
            parts.append(md.render(row["answer_delivered"]))
        else:
            messages = {"provider_abstained": "Модель отказалась отвечать.",
                "rewrite_rejected": "Ответ не запрашивался: перевод отклонён.",
                "withheld_by_guard": "Ответ пользователю не выдан: удержан проверкой."}
            parts.append('<p class="absent">' + esc(messages[row["category"]]) + '</p>')
        if row["withheld_native_claims"]:
            parts.append('<details><summary>Исходный ответ модели — не выдан пользователю</summary>'
                         + md.render('\n\n'.join(row["withheld_native_claims"])) + '</details>')
        parts.append('</td><td class="gold">' + md.render(row["reference_original"])
            + '<div class="source">' + md.render(row["reference_source_original"]) + '<a href="'
            + Path(row["original_pdf_path"]).as_uri() + '">Оригинальный PDF</a></div></td><td><span class="status">'
            + esc(row["category_label"]) + '</span><p class="note-text">' + esc(row["review_note"]) + '</p></td></tr>')
    parts.append('</tbody></table></div><p>Основное содержание подтверждается — не утверждение о полной научной корректности '
        'или независимой экспертной приёмке. Эталоны сохранены как предоставлены.</p><p><a href="'
        + (run.BASE / 'assessment_v01/review.html').as_uri() + '">Сверка с исходниками и PDF-страницами</a></p>')
    payload = json.dumps(rows, ensure_ascii=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    parts.append('<script type="application/json" id="comparison-data">' + payload + '</script>')
    parts.append('<script>const controls=["search","article","category"].map(id=>document.getElementById(id));'
        'function filter(){const[q,a,c]=controls.map(x=>x.value.toLowerCase());let n=0;'
        'document.querySelectorAll("#comparison > tbody > tr").forEach(r=>{const ok=(!q||r.textContent.toLowerCase().includes(q))'
        '&&(!a||r.dataset.article.toLowerCase()===a)&&(!c||r.dataset.category===c);r.hidden=!ok;if(ok)n++;});'
        'document.getElementById("count").textContent=`Показано ${n} из 30`;}controls.forEach(x=>x.addEventListener("input",filter));'
        '</script></body></html>')
    page = ''.join(parts)
    inspector = Inspector()
    inspector.feed(page)
    run.require(inspector.ids == run.profile.baseline.IDS, "Table lost or duplicated cases")
    run.require(json.loads(''.join(inspector.raw)) == rows, "Embedded exact text differs")
    for row, source in zip(rows, original["cases"], strict=True):
        run.require(row["answer_delivered"] == source.get("api", {}).get("body", {}).get("answer", {}).get("answer")
            and row["reference_original"] == source["reference_answer_verbatim"], "Answer/reference text changed")
    for link in inspector.links:
        parsed = urlparse(link)
        path = unquote(parsed.path)
        if re.match(r"^/[A-Za-z]:/", path):
            path = path[1:]
        run.require(parsed.scheme == "file" and Path(path).is_file(), "Broken local source link")
    f.save(output / "comparison.html", page.encode())
    f.write(output / "comparison.json", {"cases": rows, "answers_and_references_unabridged": True})
    verification = {"rows": len(rows), "exact_answer_reference_pairs": len(rows), "local_links": len(inspector.links),
        "categories": dict(Counter(row["category"] for row in rows)), "withheld_native_separately_labelled": 1,
        "new_model_calls": 0, "new_oauth_calls": 0, "browser_checked": False}
    f.write(output / "verification.json", verification)
    f.write(output / "bindings.json", f.bindings([Path(__file__), run.BASE / "review_v01/manifest.json",
        run.BASE / "assessment_v01/manifest.json", run.BASE / "final_verification_v01/manifest.json"]))
    f.save(output / "executed_script.py", Path(__file__).read_bytes())
    f.manifest(output)
    print(json.dumps(verification, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
