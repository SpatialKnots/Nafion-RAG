"""Export the current TAC proposals as an escaped, source-linked local review table."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path
from typing import Any

from scripts.tac_experiment import validate_profiles
from scripts.tac_metadata import validate_metadata

HEADERS = ("Title", "Authors", "Journal", "Year", "Abstract", "Conclusions", "Terms", "hyperlink to original file")
MISSING = "Не заполнено"
UNDETECTED = "Не распознано текущим TAC"


def visible_text(value: str) -> str:
    return "".join(f"⟦U+{ord(char):04X}⟧" if ord(char) < 32 and char not in "\n\r\t" else char for char in value)


def esc(value: Any) -> str:
    return html.escape(visible_text(str(value)), quote=True)


def section_cell(text: str) -> str:
    if not text:
        return f'<span class="missing">{UNDETECTED}</span>'
    preview = " ".join(text.split())[:160]
    return f"<details><summary>{esc(preview)}…</summary><pre>{esc(text)}</pre></details>"


def metadata_cell(field: str, stored: dict[str, Any], url: str) -> str:
    value = stored.get(field)
    result = stored.get("fields", {}).get(field)
    display = "; ".join(value) if isinstance(value, list) else str(value) if value is not None else MISSING
    if result is None:
        return esc(display)
    labels = {"not_found": "Не распознано в PDF", "ambiguous": "Неоднозначно", "not_applicable": "Не применимо"}
    if value is None:
        display = labels.get(result["status"], MISSING)
    preview = display if field != "authors" or value is None else "; ".join(value[:2]) + f" — авторов: {len(value)}"
    sources = []
    for c in result["candidates"]:
        e = c["evidence"]
        candidate_value = "; ".join(c["value"]) if isinstance(c["value"], list) else str(c["value"])
        sources.append(
            f"<details><summary>{esc(c['method'])}: PDF page {e['page']}</summary>"
            f'<p>{esc(candidate_value)}</p><a href="{esc(url)}#page={e["page"]}">Открыть страницу</a>'
            f"<pre>{esc(e['quote'])}</pre><p>{esc(e['layer'])}, offsets [{e['start']}, {e['end']}), "
            f"SHA-256 {esc(e['page_text_sha256'])}</p></details>"
        )
    content = "\n".join(value) if isinstance(value, list) else display
    return (
        f'<details class="metadata"><summary>{esc(preview)}</summary><pre class="metadata-value">{esc(content)}</pre>'
        f"<p>Статус: {esc(result['status'])}. {esc('; '.join(result['diagnostics']))}</p>{''.join(sources)}</details>"
    )


def render_table(
    snapshot: dict[str, Any],
    profiles: dict[str, Any],
    metadata: dict[str, Any],
    source_root: Path,
    profiles_sha256: str,
    metadata_sha256: str = "не указан",
    previous_profiles: dict[str, Any] | None = None,
) -> str:
    previous = {}
    if previous_profiles is not None:
        validate_profiles(snapshot, previous_profiles, profiles["snapshot_sha256"])
        previous = {p["article_id"]: p for p in previous_profiles["profiles"]}
    if metadata.get("schema"):
        validate_metadata(snapshot, metadata, profiles["snapshot_sha256"])
        if metadata["profiles_sha256"] != profiles_sha256:
            raise ValueError("Metadata TAC profiles mismatch")
    articles = {article["article_id"]: article for article in snapshot["articles"]}
    meta = {item["article_id"]: item for item in metadata["articles"]}
    if len(meta) != len(metadata["articles"]) or set(meta) != set(articles):
        raise ValueError("Metadata inventory differs from TAC snapshot")
    rows = []
    count = len(profiles["profiles"])
    for profile in profiles["profiles"]:
        article, stored = articles[profile["article_id"]], meta[profile["article_id"]]
        if stored["checksum_sha256"] != article["original_pdf_sha256"]:
            raise ValueError("Metadata source checksum mismatch")
        pdf = (source_root / article["original_pdf_path"]).resolve()
        if not pdf.is_file():
            raise FileNotFoundError(pdf)
        url = pdf.as_uri()
        sections = profile["sections"]
        title = "\n\n".join(s["quote"] for s in sections if s["kind"] == "T")
        abstract = "\n\n".join(s["quote"] for s in sections if s["kind"] == "A")
        conclusion = "\n\n".join(s["quote"] for s in sections if s["kind"] == "C")
        changed = {}
        old_texts = {}
        if previous:
            for kind in ("T", "A", "C"):
                old = [s for s in previous[profile["article_id"]]["sections"] if s["kind"] == kind]
                current = [s for s in sections if s["kind"] == kind]
                changed[kind] = [(s["page"], s["quote"]) for s in old] != [(s["page"], s["quote"]) for s in current]
                old_texts[kind] = "\n\n".join(s["quote"] for s in old)
        tags = {k: '<span class="change">Изменено</span>' if changed.get(k) else "" for k in ("T", "A", "C")}
        old_details = "".join(
            f"<details><summary>Прежнее {k}</summary><pre>{esc(old_texts[k] or UNDETECTED)}</pre></details>"
            for k in old_texts
            if changed[k]
        )
        abstract_cell = section_cell(abstract)
        if not abstract and profile.get("section_status", {}).get("A") == "not_separately_delimited":
            abstract_cell = '<span class="missing">Конференционный abstract: отдельная A не выделена</span>'
        conclusion_cell = section_cell(conclusion)
        if profile.get('conclusion_kind') == 'summary_passages':
            conclusion_cell = '<p class="missing">Итоговые фрагменты; отдельный раздел Conclusions не найден</p>' + conclusion_cell
        evidence = "".join(
            f'<p><a href="{esc(url)}#page={s["page"]}">{s["kind"]}: PDF page {s["page"]}</a>, '
            f"{esc(s['layer'])}, offsets [{s['start']}, {s['end']}), {esc(s['method'])}</p>"
            for s in sections
        )
        warnings = "".join(f"<p>PDF page {w['page']}: {esc(w['messages'])}</p>" for w in profile.get("layout_warnings", []))
        rows.append(
            f'<tr data-id="{esc(profile["article_id"])}"><td>{tags["T"]}<strong>{esc(title or UNDETECTED)}</strong></td>'
            f"<td>{metadata_cell('authors', stored, url)}</td><td>{metadata_cell('journal', stored, url)}</td>"
            f"<td>{metadata_cell('year', stored, url)}</td>"
            f"<td>{tags['A']}{abstract_cell}</td><td>{tags['C']}{conclusion_cell}</td>"
            '<td class="missing">Извлечение Terms не реализовано</td>'
            f'<td><a class="original" href="{esc(url)}">Открыть оригинальный PDF</a>'
            '<details class="provenance"><summary>Источник и диагностика</summary>'
            f"<p>{esc(profile['metadata_title'])}</p><p>Article UUID: {esc(profile['article_id'])}</p>"
            f"<p>PDF SHA-256: {esc(article['original_pdf_sha256'])}</p>"
            f"{evidence}<p>{esc('; '.join(profile['diagnostics']))}</p>"
            f"<p>Страница начала статьи: {esc(profile.get('front_page', 'не определена'))}.</p>{old_details}"
            f"<details><summary>Предупреждения PDF: {len(profile.get('layout_warnings', []))} страниц</summary>{warnings}</details>"
            "</details></td></tr>"
        )
    header = "".join(f"<th>{esc(name)}</th>" for name in HEADERS)
    return f"""<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>ARIADNE — TAC {esc(profiles["schema"])}</title>
<style>body{{font:14px Arial,sans-serif;color:#24323f;margin:24px;background:#f5f7f9}}h1{{font-size:25px}}
p{{max-width:1150px;line-height:1.5}}.toolbar{{display:flex;gap:12px;align-items:center;margin:20px 0;flex-wrap:wrap}}
input{{padding:10px;width:400px;border:1px solid #b5c3cd;border-radius:5px}}
button{{padding:10px;background:#24323f;color:white;border:0;border-radius:5px;cursor:pointer}}
.scroll{{overflow:auto;background:white;border:1px solid #c9d2da;max-height:78vh}}
table{{border-collapse:collapse;min-width:2000px;width:100%;table-layout:fixed}}
th{{background:#24323f;color:white;padding:14px;position:sticky;top:0;text-align:left;z-index:1}}
td{{padding:14px;border-bottom:1px solid #dce3e8;vertical-align:top;overflow-wrap:anywhere}}tbody tr:nth-child(even){{background:#f2f5f7}}
th:first-child{{width:280px}}th:nth-child(2){{width:240px}}th:nth-child(3){{width:190px}}th:nth-child(4){{width:100px}}
th:nth-child(5),th:nth-child(6){{width:440px}}th:nth-child(7){{width:180px}}th:nth-child(8){{width:210px}}
pre{{white-space:pre-wrap;font:inherit;line-height:1.5;margin:14px 0}}summary{{cursor:pointer;line-height:1.5}}
.missing{{color:#79532c}}a{{color:#087c83}}.provenance{{font-size:12px;margin-top:16px}}.provenance p{{margin:8px 0}}
.identity{{font-size:12px;color:#536273;overflow-wrap:anywhere}}
.change{{display:block;font-size:11px;color:#79532c;background:#fff0bc;width:max-content;padding:3px 6px;margin-bottom:7px}}
</style></head><body>
<h1>ARIADNE — TAC для проверки</h1>
<p>{count} документов. Сохранённые предложения алгоритма без ручных исправлений. Границы требуют проверки.
Authors, Journal и Year — сохранённые метаданные или предложения локального PDF-алгоритма.
Раскройте ячейку метаданных для списка авторов, цитат и диагностики. Terms ещё не извлекаются.</p>
<p class="identity">Версия: {esc(profiles["schema"])}. Snapshot SHA-256: {esc(profiles["snapshot_sha256"])}.
Profiles SHA-256: {esc(profiles_sha256)}. Снимок корпуса: {esc(snapshot.get("created_at", "не указан"))}.</p>
<p class="identity">Метаданные: {esc(metadata.get("schema", "existing database metadata"))}.
Metadata SHA-256: {esc(metadata_sha256)}. Источник: {esc(metadata.get("source", "не указан"))}.</p>
<p>Сравнение: {esc(previous_profiles["schema"] if previous_profiles else "не задано")}.
Метка «Изменено» показывает отличия текста или страницы T/A/C. Прежний текст доступен в диагностике источника.</p>
<p>Нажмите на Abstract или Conclusions для полного текста. Исходные переносы сохранены.
Управляющие символы отображаются как ⟦U+XXXX⟧. PDF-ссылки рассчитаны на этот компьютер.</p>
<div class="toolbar"><input id="query" aria-label="Поиск по таблице" placeholder="Поиск по полному тексту таблицы">
<button id="expand">Раскрыть все тексты</button><span id="count">{count} / {count}</span></div>
<div class="scroll"><table><thead><tr>{header}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>
<script>const total={count};document.querySelector('#query').addEventListener('input',e=>{{
const q=e.target.value.toLocaleLowerCase();let count=0;for(const row of document.querySelectorAll('tbody tr')){{
row.hidden=!row.textContent.toLocaleLowerCase().includes(q);if(!row.hidden)count++;}}
document.querySelector('#count').textContent=count+' / '+total;}});let expanded=false;
document.querySelector('#expand').addEventListener('click',e=>{{expanded=!expanded;
for(const d of document.querySelectorAll('td:nth-child(5) details,td:nth-child(6) details'))d.open=expanded;
e.target.textContent=expanded?'Свернуть тексты':'Раскрыть все тексты';}});</script></body></html>"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--profiles", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, default=Path("."))
    parser.add_argument("--previous-profiles", type=Path)
    args = parser.parse_args()
    snapshot_raw, profiles_raw = args.snapshot.read_bytes(), args.profiles.read_bytes()
    snapshot, profiles = json.loads(snapshot_raw), json.loads(profiles_raw)
    validate_profiles(snapshot, profiles, hashlib.sha256(snapshot_raw).hexdigest())
    metadata_raw = args.metadata.read_bytes()
    result = render_table(
        snapshot,
        profiles,
        json.loads(metadata_raw),
        args.source_root.resolve(),
        hashlib.sha256(profiles_raw).hexdigest(),
        hashlib.sha256(metadata_raw).hexdigest(),
        json.loads(args.previous_profiles.read_bytes()) if args.previous_profiles else None,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        stream.write(result)
    print(json.dumps({"output": str(args.output), "documents": len(profiles["profiles"]), "version": profiles["schema"]}))


if __name__ == "__main__":
    main()
