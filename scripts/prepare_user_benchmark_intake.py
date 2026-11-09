"""Build a local source-only receipt; never import the answer route or provider."""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from html import escape
from pathlib import Path
from typing import Any

import fitz

from scripts import gigachat_answer_smoke as files
from scripts.user_benchmark_intake import VERSION, parse_document, quote_match, registered_pdf

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "output/user_benchmark_20261103"
ORIGINAL = ROOT / "docs/records/Nafion_RAG_Benchmark_v1.0_original.md"
DRAW = ROOT / "output/evaluation_article_draw_20261103/selection_v01.json"
CATALOG = ROOT / "output/particle_attachment_20261103/review_v01/report.json"
PROTOCOL = ROOT / "docs/records/user_benchmark_intake_protocol_v0.1.md"
NOTES = [
    ("Q01", 1, "we have also added", " to further stabilize",
     "Автоматическое несовпадение: PDF содержит ﬁlm-\\nforming; старый view убирает дефис переноса, "
     "а эталон сохраняет film-forming. Значение 0.15 M видно в исходном фрагменте. Эталон не изменён."),
    ("Q02", 2, "After treatment (1", "2.2. Electrochemical Measurements",
     "Общий метод допускает 1–24 часа; раздел 3.1 отдельно описывает серию по 1 часу. "
     "Нельзя распространять 1 час на все упомянутые в статье образцы."),
    ("Q03", 2, "Согласно данным производителя", "Водные растворы этанола",
     "Источник прямо указывает остаточную воду в растворителях и отсутствие специального обезвоживания. "
     "Название «индивидуальный растворитель» не означает абсолютную безводность."),
    ("Q03", 3, "Таблица 1.", None,
     "Таблица 1 визуально проверена: НМП 137%/−65.0 Дж/г; ДМФА 115/−57.8; "
     "этанол 133/−34.1; 2-пропанол 49/−30.1; вода 35/−8.9. "
     "Заголовок: сухие образцы Li-Nafion при 25 °C. Это проверка данной таблицы, не всего gold."),
    ("Q04", 6, "At the end of measurements", "The observed hysteresis",
     "60 суток при 40 °C не изменили W; авторы оставляют альтернативы: близость к равновесию "
     "или очень медленный синерезис. Необратимость обозначена гипотезой."),
    ("Q04", 12, "While the introduction", "The obtained results",
     "Автоматическое несовпадение: извлечённый символ ◦C отличается от °C в эталоне. "
     "Отдельное терминологическое замечание: в заключении статьи написано chemical crosslinking elements, "
     "в эталоне — физические узлы сшивки. Это интерпретация, а не дословное совпадение. "
     "Научное разрешение этой терминологии не выполнялось."),
    ("Q05", 7, "Tab. 5.", "Fig. 13.",
     "Таблица 5 визуально проверена: единицы S·cm⁻¹ без масштабного множителя; "
     "NCD 0.034/15%, a1 0.0095/10%, a2 0.028/30%, b1 0.228/19%. "
     "Сноска у a2 и b1: макроскопическое набухание. 0.228/0.034≈6.706 — арифметическое "
     "отношение этих значений, а не эффект при одинаковой гидратации/EW."),
]


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def pre(value: Any) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)
    return "<pre>" + escape(text) + "</pre>"


def render(report: dict[str, Any], original: str) -> str:
    parts = ["""<!doctype html><html lang="ru"><meta charset="utf-8">
<title>ARIADNE — пользовательский benchmark v1.0</title>
<style>body{font:16px/1.5 system-ui;max-width:1400px;margin:32px auto;padding:0 24px;color:#172333}
pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f1f4f8;padding:16px;border-radius:6px}
table{border-collapse:collapse;width:100%}td,th{padding:10px;border:1px solid #ccd4df;vertical-align:top}
td{max-width:300px}details{margin:10px 0}summary{cursor:pointer}section{border-top:2px solid #b6c7db;margin-top:32px}
.scroll{overflow:auto}input{padding:10px;width:60%}</style><body>
<h1>Приёмка пользовательского benchmark v1.0</h1>
<p>5 вопросов / 5 статей. Оригинал сохранён без правок. Ответов модели и научных оценок нет.
Проверка цитат и таблиц — отдельные замечания ассистента, не редактирование эталонов.</p>
<p>Авторство вопросов и отсутствие просмотра ответов заявлены пользователем.
Участие LLM в ответах и отдельная экспертная проверка не указаны.
Независимость от всей предыдущей разработки не подтверждена. План качества: 75% работ.</p>"""]
    parts += ["<details><summary>Паспорт и пределы проверки</summary>" + pre(report["receipt"]) + pre(report["limitations"]) + "</details>",
              "<details><summary>Полный оригинал пользователя</summary>" + pre(original) + "</details>",
              "<h2>Статьи — TAC</h2><label>Поиск <input id='q' type='search'></label><div class='scroll'><table id='tac'><thead><tr>"]
    parts += ["<th>" + x + "</th>" for x in ("Title", "Authors", "Journal", "Year", "Abstract", "Conclusions", "Terms", "PDF")]
    parts.append("</tr></thead><tbody>")
    for article in report["articles"]:
        parts.append("<tr>")
        for key in ("title", "authors", "journal", "year", "abstract", "conclusions", "terms"):
            value = article.get(key)
            visible = value if value is not None else "Не собрано"
            preview = visible if isinstance(visible, str) else json.dumps(visible, ensure_ascii=False)
            parts.append("<td><details><summary>" + escape(preview[:100]) + "</summary>" + pre(visible) + "</details></td>")
        parts.append("<td><a href='" + escape(Path(article["original_pdf_path"]).as_uri(), quote=True) + "'>Оригинал PDF</a></td></tr>")
    parts.append("</tbody></table></div>")
    for case in report["cases"]:
        parts.append("<section id='" + case["id"] + "'><h2>" + case["id"] + "</h2><h3>Вопрос</h3>" + pre(case["question"]))
        parts.append("<details><summary>Эталон пользователя и условия — без правок</summary>"
                     + pre(case["case_markdown_verbatim"]) + "</details>")
        parts.append("<h3>Цитаты: сопоставление с исходным PDF</h3>")
        for quote in case["quotes"]:
            url = Path(case["source_pdf_path_verbatim"]).as_uri() + "#page=" + str(quote["pdf_page"])
            parts.append("<details><summary>" + escape(quote["state"]) + ": PDF стр. " + str(quote["pdf_page"])
                         + "</summary><a href='" + escape(url, quote=True) + "'>Страница PDF</a>" + pre(quote) + "</details>")
        parts.append("<h3>Отдельные замечания ассистента</h3>")
        for note in report["source_notes"]:
            if note["case_id"] == case["id"]:
                parts.append("<details><summary>PDF стр. " + str(note["pdf_page"]) + "</summary>" + pre(note) + "</details>")
        parts.append("</section>")
    parts.append("""<script>document.querySelector('#q').addEventListener('input',e=>{
const q=e.target.value.toLocaleLowerCase();document.querySelectorAll('#tac tbody tr').forEach(
r=>r.hidden=!r.textContent.toLocaleLowerCase().includes(q));});</script></body></html>""")
    return "".join(parts)


def main() -> None:
    sys.addaudithook(files.NetworkPolicy())
    raw = ORIGINAL.read_bytes()
    receipt = read(BASE / "intake_v01/receipt.json")
    if files.sha(raw) != receipt["sha256"] or len(raw) != receipt["bytes"]:
        raise ValueError("Original benchmark receipt drift")
    if raw != (BASE / "intake_v01/Nafion_RAG_Benchmark_v1.0_original.md").read_bytes():
        raise ValueError("Original copies differ")
    cases = parse_document(raw.decode("utf-8"))
    selected = read(DRAW)["selected"]
    if len({registered_pdf(c["source_pdf_path_verbatim"], selected)["article_id"] for c in cases}) != 5:
        raise ValueError("Expected five distinct drawn PDFs")
    folder = BASE / "review_v01"
    folder.mkdir(exist_ok=False)
    pages: dict[tuple[str, int], str] = {}
    page_records = []
    for case in cases:
        needed = {q["pdf_page"] for q in case["quotes"]}
        needed.update(int(x) for x in re.findall(r"страница\s+PDF\W+(\d+)", case["reference_source_section_verbatim"], re.I))
        needed.update(n[1] for n in NOTES if n[0] == case["id"])
        with fitz.open(case["source_pdf_path_verbatim"]) as pdf:
            for page in sorted(needed):
                if not 1 <= page <= len(pdf):
                    raise ValueError("Physical PDF page outside registered document")
                text = pdf[page - 1].get_text()
                pages[case["id"], page] = text
                dest = folder / f'{case["id"]}_p{page:02d}.txt'
                files.save(dest, text.encode("utf-8"))
                page_records.append({"case_id": case["id"], "pdf_page": page,
                                     "raw_text_file": dest.name, "sha256": files.sha(text.encode("utf-8"))})
        for quote in case["quotes"]:
            quote.update(quote_match(pages[case["id"], quote["pdf_page"]], quote["matching_quote"]))
    source_notes = []
    for case_id, page, first, stop, note in NOTES:
        text = pages[case_id, page]
        start = text.index(first)
        end = text.index(stop, start) if stop else len(text)
        source_notes.append({"case_id": case_id, "pdf_page": page, "origin": "assistant_posthoc_source_observation",
                             "note": note, "raw_span": {"start": start, "end": end, "text": text[start:end]},
                             "scientific_score": None})
    all_articles = read(CATALOG)["articles"]
    articles = [next(a for a in all_articles if a["article_id"] == s["article_id"]) for s in selected]
    report = {"version": VERSION, "receipt": receipt, "cases": cases, "articles": articles,
              "source_pages": page_records, "source_notes": source_notes,
              "quote_counts": dict(Counter(q["state"] for c in cases for q in c["quotes"])),
              "model_calls": 0, "oauth_calls": 0, "db_calls": 0, "scientific_scores": None,
              "limitations": ["Mapped match is not byte-exact quotation or scientific entailment.",
                              "Casefold/dash/NFKC/dehyphenation are text recognition only; no unit or condition equivalence.",
                              "Only declared quotes, two tables and selected context checked; not every reference claim.",
                              "Two table pages visually checked using Poppler; other PDF pages text-only.",
                              "No system predictions, benchmark scoring, runtime tuning or live-call authorization.",
                              "LLM assistance for answers and separate expert verification undeclared.",
                              "Corpus/topics exposed during development; statistical independence unverified.",
                              "HTML browser execution, full suite and mypy untested."]}
    files.write(folder / "report.json", report)
    files.save(folder / "review.html", render(report, raw.decode("utf-8")).encode("utf-8"))
    files.save(folder / "original.md", raw)
    files.write(folder / "questions_only.json", {"version": VERSION, "reference_document_sha256": receipt["sha256"],
                "cases": [{"id": c["id"], "question": c["question"]} for c in cases], "live_authorization": False})
    inputs = [ORIGINAL, DRAW, CATALOG, PROTOCOL, BASE / "intake_v01/receipt.json", Path(__file__),
              ROOT / "scripts/user_benchmark_intake.py", ROOT / "tests/test_user_benchmark_intake.py"]
    inputs += [Path(s["original_pdf_path"]) for s in selected]
    inputs += list((BASE / "visual_v01").glob("*"))
    inputs += [ROOT / "scripts" / name for name in (
        "gigachat_answer_smoke.py", "cross_lingual_relation_audit.py", "event_value_ownership_audit.py", "retrieval_ablation.py")]
    files.write(folder / "bindings.json", files.bindings(inputs))
    files.write(folder / "manifest.json", {"version": VERSION, "outputs": {
        p.relative_to(folder).as_posix(): files.sha(p.read_bytes()) for p in sorted(folder.rglob("*")) if p.is_file()}})
    print(json.dumps({"folder": str(folder), "cases": len(cases), "source_pages": len(page_records), "quotes": report["quote_counts"]}))


if __name__ == "__main__":
    main()
