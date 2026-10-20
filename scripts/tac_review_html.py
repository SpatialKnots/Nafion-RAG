"""Export the current TAC proposals as an escaped, source-linked local review table."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path
from typing import Any

from scripts.tac_boundary_review import KINDS, LABELS, review_counts, validate_review
from scripts.tac_experiment import validate_profiles
from scripts.tac_metadata import validate_metadata
from scripts.tac_term_classification import validate_classification
from scripts.tac_term_contexts import validate_contexts
from scripts.tac_terms import validate_terms

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


def boundary_badge(record: dict[str, Any], kind: str, source_root: Path) -> str:
    assessment = record["assessments"][kind]
    status = assessment["status"]
    links = " ".join(
        f'<a href="{esc((source_root / p["image"]).resolve().as_uri())}">PDF page {p["page"]}: изображение</a>'
        for p in record["reviewed_pages"]
    )
    return (
        f'<details class="boundary-review {status}" data-kind="{kind}" data-status="{status}">'
        f'<summary>{esc(LABELS[status])}</summary><p>{esc(assessment["note"])}</p>'
        f'<p>Оценка агента; подтверждение человеком ожидается. {links}</p></details>'
    )


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


def classification_markup(assignments: list[dict[str, Any]], taxonomy: dict[str, Any]) -> str:
    axis_labels = {"type": "Тип", "role": "Роль", "origin": "Происхождение"}
    state_labels = {"proposed": "Предложено", "unclassified": "Не определено", "unresolved": "Конфликт"}
    items = []
    for assignment in assignments:
        proposals = "".join(
            f'<p>{esc(taxonomy["categories"][assignment["axis"]][p["category"]])}; {esc(p["producer"])}; '
            f'{esc(p["declared_reviewer"] or "policy")}</p>' + "".join(
                f'<p>{esc(b["rule_id"])}: [{b["start"]}, {b["end"]}); region {esc(b["source_region_id"])}.</p>'
                f'<pre class="classification-quote">{esc(b["quote"])}</pre><p>{esc(b["rationale"])}</p>' for b in p["basis"])
            for p in assignment["proposals"])
        items.append(
            f'<details class="classification" data-assignment-id="{esc(assignment["assignment_id"])}" '
            f'data-use-id="{esc(assignment["use_id"])}" data-axis="{esc(assignment["axis"])}" data-state="{esc(assignment["state"])}">'
            f'<summary>{axis_labels[assignment["axis"]]}: {state_labels[assignment["state"]]}</summary>'
            f'{proposals}<p>{esc("; ".join(assignment["diagnostics"]))}</p></details>')
    return ''.join(items)


def context_cards(article: dict[str, Any], classification: dict[str, Any] | None = None,
                  taxonomy: dict[str, Any] | None = None) -> dict[str, str]:
    contexts = {c["context_id"]: c for c in article["contexts"]}
    mentions = {m["mention_id"]: m["source"] for m in article["mentions"]}
    uses = {u["use_id"]: u for u in article["uses"]}
    terms = {t["term_id"]: t for t in article["terms"]}
    assigned: dict[str, list[dict[str, Any]]] = {}
    if classification is not None:
        if taxonomy is None:
            raise ValueError("Classification cards require taxonomy")
        for item in classification["assignments"]:
            assigned.setdefault(item["use_id"], []).append(item)
    relations: dict[str, list[tuple[str, str, str]]] = {}
    for r in article["containment"]:
        outer, inner = uses[r["outer_use_id"]], uses[r["inner_use_id"]]
        a, b = mentions[outer["mention_id"]], mentions[inner["mention_id"]]
        description = (f"{terms[outer['term_id']]['label']} [{a['start']}, {a['end']}) ⊃ "
                       f"{terms[inner['term_id']]['label']} [{b['start']}, {b['end']}); PDF page {a['page_number']}")
        for u in (outer, inner):
            relations.setdefault(u["use_id"], []).append((description, outer["use_id"], inner["use_id"]))
    result = {}
    for term in article["terms"]:
        grouped: dict[str, list[str]] = {}
        for identifier in term["use_ids"]:
            u = uses[identifier]
            source = mentions[u["mention_id"]]
            links = "".join(
                f'<li class="lexical-containment" data-outer-use-id="{esc(outer)}" data-inner-use-id="{esc(inner)}">{esc(s)}</li>'
                for s, outer, inner in relations.get(identifier, []))
            grouped.setdefault(u["context_id"], []).append(
                f'<li class="term-use" data-use-id="{esc(identifier)}" data-mention-id="{esc(u["mention_id"])}">'
                f'Упоминание [{source["start"]}, {source["end"]}): <q class="mention-quote">{esc(source["quote"])}</q>'
                f'{classification_markup(assigned[identifier], taxonomy) if taxonomy is not None else ""}'
                f'{"<details><summary>Лексические вложения этого упоминания</summary><ul>" + links + "</ul></details>" if links else ""}'
                '</li>')
        groups = []
        for identifier, items in grouped.items():
            c = contexts[identifier]
            s = c["source"]
            groups.append(
                f'<details class="term-context" data-context-id="{esc(identifier)}">'
                f'<summary>{esc(c["kind"])}: PDF page {s["page_number"]}, контекст [{s["start"]}, {s["end"]})</summary>'
                f'<ul>{"".join(items)}</ul><div class="context-text"></div></details>')
        result[term["term_id"]] = (
            f'<details class="term-contexts"><summary>Упоминания: {len(term["use_ids"])}; контексты: {len(grouped)}</summary>'
            '<p>Точные фрагменты TAC. Лексическое вложение не подтверждает синонимию или научную связь.</p>'
            f'{"".join(groups)}</details>')
    return result


def term_item(term: dict[str, Any], url: str, decision: dict[str, Any] | None = None,
              labels: dict[str, str] | None = None, context_html: str = "") -> str:
    sources = "".join(
        f'<p><a href="{esc(url)}#page={e["page"]}">{esc(e["kind"])}: PDF page {e["page"]}</a>, '
        f'{esc(e["layer"])}, offsets [{e["start"]}, {e["end"]}), '
        f'границы TAC: {esc(e["tac_boundary_status"])}.</p><pre class="term-quote">{esc(e["quote"])}</pre>'
        for e in term["evidence"]
    )
    explanation = ""
    if decision:
        state = decision["state"]
        if state == "nested_surface_suppressed":
            against = "; ".join((labels or {})[identifier] for identifier in decision["against_candidate_ids"])
            explanation = f"Вне превью: вложенная или включающая фраза относительно {against}. Это не установленная синонимия."
        elif state == "preview_limit":
            explanation = "Вне превью: достигнут лимит показа. Кандидат и все его цитаты сохранены."
        else:
            explanation = "Включён в превью."
        f = term["rank_features"]
        explanation += (f" Позиция полного списка: {term['rank']}. Компоненты ранга: "
                        f"взвешенные повторы {f['weighted_capped_occurrences']}, токены {f['token_count']}, "
                        f"совпадение со словарём {int(f['seed_match'])}.")
    identifier = f' data-candidate-id="{esc(term["candidate_id"])}"' if "candidate_id" in term else ""
    return (
        f'<details class="term" data-term="{esc(term["term"])}"{identifier}><summary>{esc(term["label"])}</summary>'
        f'<p>Предложение; методов: {esc(", ".join(term["methods"]))}. '
        f'Ранг: {esc(term["score"])}; вхождений: {term["occurrences"]}.</p>'
        f'<p>Совпадения со словарём: {esc(", ".join(term["seed_concepts"]) or "нет")}.</p>'
        f'{"<p>" + esc(explanation) + "</p>" if explanation else ""}{sources}{context_html}</details>'
    )


def terms_cell(record: dict[str, Any] | None, url: str, contexts: dict[str, str] | None = None,
               classification: dict[str, Any] | None = None) -> str:
    if record is None:
        return '<span class="missing">Извлечение Terms не реализовано</span>'
    terms = record.get("inventory", record.get("terms", []))
    if not terms:
        return '<span class="missing">Кандидаты Terms не найдены в TAC</span>'
    items = "".join(term_item(term, url) for term in terms) if "inventory" not in record else ""
    description = f"Кандидаты ({len(terms)})"
    attributes = ""
    preview_terms = terms
    if "inventory" in record:
        by_id = {t["candidate_id"]: t for t in terms}
        labels = {identifier: t["label"] for identifier, t in by_id.items()}
        decisions = {d["candidate_id"]: d for d in record["preview"]["decisions"]}
        selected = set(record["preview"]["candidate_ids"])
        preview_terms = [by_id[identifier] for identifier in record["preview"]["candidate_ids"]]
        remaining = [t for t in terms if t["candidate_id"] not in selected]
        def card(term: dict[str, Any]) -> str:
            return term_item(term, url, decisions[term["candidate_id"]], labels, (contexts or {}).get(term["candidate_id"], ""))
        items = "".join(card(t) for t in preview_terms)
        pages = "".join(
            f'<details class="terms-page"><summary>Остальные: {begin + 1}–{min(begin + 50, len(remaining))}</summary>'
            f'<template>{"".join(card(t) for t in remaining[begin:begin + 50])}</template></details>'
            for begin in range(0, len(remaining), 50)
        )
        if remaining:
            items += f'<details class="terms-more"><summary>Показать остальные ({len(remaining)})</summary>{pages}</details>'
        description = f"Все кандидаты: {len(terms)}; превью: {len(preview_terms)}"
        search_text = " ".join(t["label"] + " " + t["term"] for t in terms)
        attributes = (f' data-search="{esc(search_text)}" data-inventory-count="{len(terms)}" '
                      f'data-preview-count="{len(preview_terms)}"')
    preview = "; ".join(t["label"] for t in preview_terms[:5])
    subsets = ""
    if classification is not None:
        lines = "".join(f'<li data-axis="{esc(axis)}" data-category="{esc(g["category"])}" data-count="{g["count"]}">'
                        f'{esc(g["label"])}: {g["count"]} уникальных Terms</li>'
                        for axis, groups in classification["groups"].items() for g in groups)
        subsets = ('<details class="classification-subsets"><summary>Пересекающиеся subsets по типу, роли и происхождению</summary>'
                   '<p>Черновая таксономия; предложения и конфликты, без научной приёмки. '
                   'Один term может входить в несколько групп по разным употреблениям.</p>' + f'<ul>{lines}</ul></details>')
    return (
        f'<details class="terms"{attributes}><summary>{esc(description)}: {esc(preview)}</summary>'
        '<p>Автоматический набор из TAC; научное подтверждение не выполнено. '
        'Ранг — эвристика, не вероятность корректности. Переводы и раскрытия сокращений не добавляются.</p>'
        f'{subsets}{items}<p>{esc("; ".join(record["diagnostics"]))}</p></details>'
    )


def render_table(
    snapshot: dict[str, Any],
    profiles: dict[str, Any],
    metadata: dict[str, Any],
    source_root: Path,
    profiles_sha256: str,
    metadata_sha256: str = "не указан",
    previous_profiles: dict[str, Any] | None = None,
    boundary_review: dict[str, Any] | None = None,
    boundary_review_sha256: str = "не указан",
    terms: dict[str, Any] | None = None,
    terms_sha256: str = "не указан",
    term_contexts: dict[str, Any] | None = None,
    term_contexts_sha256: str = "не указан",
    classification: dict[str, Any] | None = None,
    classification_sha256: str = "не указан",
) -> str:
    if terms is not None:
        validate_terms(snapshot, profiles, terms, profiles_sha256)
    term_records = {a["article_id"]: a for a in terms["articles"]} if terms else {}
    context_records = {}
    if term_contexts is not None:
        if terms is None:
            raise ValueError("Terms contexts require an inventory input")
        context_records = validate_contexts(snapshot, profiles, terms, term_contexts, terms_sha256)
    context_templates = []
    classification_records = {}
    if classification is not None:
        if term_contexts is None:
            raise ValueError("Terms classifications require source contexts")
        classification_records = validate_classification(term_contexts, classification, term_contexts_sha256)
    for record in context_records.values():
        for context in record["contexts"]:
            s = context["source"]
            url = (source_root / s["original_pdf_path"]).resolve().as_uri()
            context_templates.append(
                f'<template id="context-{esc(context["context_id"])}"><p><a href="{esc(url)}#page={s["page_number"]}">'
                f'Точный контекст: PDF page {s["page_number"]}</a>; {esc(s["text_layer"])}; '
                f'границы TAC: {esc(context["boundary_status"])}.</p><pre class="context-quote">{esc(s["quote"])}</pre></template>')
    terms_description = (
        "Terms — автоматические кандидаты из TAC; раскрытие показывает весь список и исходные фрагменты."
        if terms else "Terms ещё не извлекаются."
    )
    if terms and terms["schema"] in {"tac_term_inventory_v0.1", "tac_term_inventory_v0.2"}:
        terms_description = ("Terms — полный выход текущего распознавателя по TAC, включая вложенные фразы. "
                             "Превью ограничивает только показ; остальные кандидаты раскрываются группами по 50. "
                             "Поиск охватывает весь инвентарь. Научная приёмка и научные связи не установлены.")
    terms_identity = (
        f'<p class="identity">Terms: {esc(terms["schema"])}. SHA-256: {esc(terms_sha256)}. '
        f'Словарь: {esc(terms["glossary_sha256"])}.</p>' if terms else ""
    )
    if term_contexts:
        terms_identity += (f'<p class="identity">Контексты: {esc(term_contexts["schema"])}. SHA-256: {esc(term_contexts_sha256)}. '
                           'Страницы сохраняются отдельно; непрерывность текста не установлена.</p>')
    if classification:
        terms_identity += (f'<p class="identity">Классификация: {esc(classification["schema"])}. SHA-256: {esc(classification_sha256)}. '
                           f'Taxonomy SHA-256: {esc(classification["taxonomy_sha256"])}. Черновая таксономия; '
                           'состояния proposed / unclassified / unresolved. Научное подтверждение отсутствует.</p>')
    reviewed = validate_review(snapshot, profiles, boundary_review, profiles_sha256) if boundary_review is not None else {}
    audit_summary = ""
    if boundary_review is not None:
        counts = review_counts(boundary_review)
        totals = "; ".join(f"{LABELS[k]}: {counts['total'].get(k, 0)}" for k in LABELS)
        audit_summary = (
            f'<div class="audit-summary"><p><strong>Аудит границ: {counts["slots"]} ячеек.</strong> {esc(totals)}.</p>'
            f'<p>Применимые ячейки: {counts["applicable_slots"]}; исключения показаны отдельно. '
            'Это оценка агента на development корпусе, не независимая точность. '
            'Проверены выбранные страницы разделов, не все страницы документов. '
            'Статус без замечаний не подтверждает точность символов, научных значений или полноту всей статьи.</p>'
            f'<p class="identity">Аудит: {esc(boundary_review["schema"])}. SHA-256: {esc(boundary_review_sha256)}.</p></div>'
        )
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
        review = reviewed.get(profile["article_id"])
        badges = {k: boundary_badge(review, k, source_root) if review else "" for k in KINDS}
        problems = bool(review and any(review["assessments"][k]["status"] in {"boundary_error", "missed", "unresolved"} for k in KINDS))
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
        classified = classification_records.get(profile["article_id"])
        cards = (context_cards(context_records[profile["article_id"]], classified,
                               classification["taxonomy"] if classification else None) if context_records else None)
        rows.append(
            f'<tr data-id="{esc(profile["article_id"])}" data-problems="{str(problems).lower()}">'
            f'<td>{badges["T"]}{tags["T"]}<strong>{esc(title or UNDETECTED)}</strong></td>'
            f"<td>{metadata_cell('authors', stored, url)}</td><td>{metadata_cell('journal', stored, url)}</td>"
            f"<td>{metadata_cell('year', stored, url)}</td>"
            f"<td>{badges['A']}{tags['A']}{abstract_cell}</td><td>{badges['C']}{tags['C']}{conclusion_cell}</td>"
            f'<td>{terms_cell(term_records.get(profile["article_id"]), url, cards, classified)}</td>'
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
.boundary-review{{padding:8px;margin-bottom:12px;border-left:4px solid #6d7b85;background:#eef1f3}}
.boundary-review.pass{{border-color:#25764e}}.boundary_error,.missed{{border-color:#ac3636;background:#fff0ed}}
.audit-summary{{padding:8px 18px;border:1px solid #c9d2da;background:white}}
</style></head><body>
<h1>ARIADNE — TAC для проверки</h1>
{audit_summary}
<p>{count} документов. Сохранённые предложения алгоритма без ручных исправлений. Границы требуют проверки.
Authors, Journal и Year — сохранённые метаданные или предложения локального PDF-алгоритма.
Раскройте ячейку метаданных для списка авторов, цитат и диагностики.
{terms_description}</p>
<p class="identity">Версия: {esc(profiles["schema"])}. Snapshot SHA-256: {esc(profiles["snapshot_sha256"])}.
Profiles SHA-256: {esc(profiles_sha256)}. Снимок корпуса: {esc(snapshot.get("created_at", "не указан"))}.</p>
<p class="identity">Метаданные: {esc(metadata.get("schema", "existing database metadata"))}.
Metadata SHA-256: {esc(metadata_sha256)}. Источник: {esc(metadata.get("source", "не указан"))}.</p>
{terms_identity}
<p>Сравнение: {esc(previous_profiles["schema"] if previous_profiles else "не задано")}.
Метка «Изменено» показывает отличия текста или страницы T/A/C. Прежний текст доступен в диагностике источника.</p>
<p>Нажмите на Abstract или Conclusions для полного текста. Исходные переносы сохранены.
Управляющие символы отображаются как ⟦U+XXXX⟧. PDF-ссылки рассчитаны на этот компьютер.</p>
<div class="toolbar"><input id="query" aria-label="Поиск по таблице" placeholder="Поиск по полному тексту таблицы">
<button id="expand">Раскрыть тексты видимых строк</button><span id="count">{count} / {count}</span></div>
<p>Кнопка раскрывает Abstract, Conclusions и список Terms в видимых строках.
Подробные цитаты и остальные Terms загружаются отдельно при раскрытии соответствующего пункта.</p>
{'<p><button id="issues" aria-pressed="false">Только замечания</button></p>' if reviewed else ''}
<div class="scroll"><table><thead><tr>{header}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>
{"".join(context_templates)}
<script>const total={count};let issuesOnly=false;function filterRows(){{
const q=document.querySelector('#query').value.toLocaleLowerCase();let count=0;for(const row of document.querySelectorAll('tbody tr')){{
const text=row.textContent+' '+(row.querySelector('.terms')?.dataset.search||'');
row.hidden=!text.toLocaleLowerCase().includes(q)||(issuesOnly&&row.dataset.problems!=='true');if(!row.hidden)count++;}}
document.querySelector('#count').textContent=count+' / '+total;}}
document.querySelector('#query').addEventListener('input',filterRows);
document.querySelector('#issues')?.addEventListener('click',e=>{{issuesOnly=!issuesOnly;
e.target.setAttribute('aria-pressed',String(issuesOnly));
e.target.textContent=issuesOnly?'Все документы':'Только замечания';filterRows();}});
let expanded=false;
function materialize(d){{const t=d.querySelector(':scope > template');if(t){{d.append(t.content.cloneNode(true));t.remove();}}}}
function materializeContext(d){{const body=d.querySelector(':scope > .context-text');
if(body&&!body.dataset.loaded){{const t=document.getElementById('context-'+d.dataset.contextId);
if(t){{body.append(t.content.cloneNode(true));body.dataset.loaded='true';}}}}}}
document.addEventListener('toggle',e=>{{if(e.target.open){{
if(e.target.matches?.('.terms-page'))materialize(e.target);
if(e.target.matches?.('.term-context'))materializeContext(e.target);}}}},true);
document.querySelector('#expand').addEventListener('click',async e=>{{expanded=!expanded;
const button=e.target;button.disabled=true;
const rows=[...document.querySelectorAll('tbody tr')].filter(row=>!row.hidden);
const cells='td:nth-child(5) > details:not(.boundary-review),'+
'td:nth-child(6) > details:not(.boundary-review),td:nth-child(7) > details.terms';
for(let i=0;i<rows.length;i++){{
if(!rows[i].hidden)for(const d of rows[i].querySelectorAll(cells))d.open=expanded;
button.textContent='Обработка строк: '+(i+1)+' / '+rows.length;
await new Promise(resolve=>setTimeout(resolve,0));
}}
button.textContent=expanded?'Свернуть тексты видимых строк':'Раскрыть тексты видимых строк';
button.disabled=false;}});</script></body></html>"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--profiles", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, default=Path("."))
    parser.add_argument("--previous-profiles", type=Path)
    parser.add_argument("--boundary-review", type=Path, help="Optional source-bound assistant development audit; never corrects proposals")
    parser.add_argument("--terms", type=Path, help="Optional proposed article keyword sidecar")
    parser.add_argument("--term-contexts", type=Path, help="Optional exact mention/context and lexical containment sidecar")
    parser.add_argument("--classification", type=Path, help="Optional draft source-bound classifications and subsets")
    args = parser.parse_args()
    snapshot_raw, profiles_raw = args.snapshot.read_bytes(), args.profiles.read_bytes()
    snapshot, profiles = json.loads(snapshot_raw), json.loads(profiles_raw)
    validate_profiles(snapshot, profiles, hashlib.sha256(snapshot_raw).hexdigest())
    metadata_raw = args.metadata.read_bytes()
    terms_raw = args.terms.read_bytes() if args.terms else None
    contexts_raw = args.term_contexts.read_bytes() if args.term_contexts else None
    classification_raw = args.classification.read_bytes() if args.classification else None
    result = render_table(
        snapshot,
        profiles,
        json.loads(metadata_raw),
        args.source_root.resolve(),
        hashlib.sha256(profiles_raw).hexdigest(),
        hashlib.sha256(metadata_raw).hexdigest(),
        json.loads(args.previous_profiles.read_bytes()) if args.previous_profiles else None,
        json.loads(args.boundary_review.read_bytes()) if args.boundary_review else None,
        hashlib.sha256(args.boundary_review.read_bytes()).hexdigest() if args.boundary_review else "не указан",
        json.loads(terms_raw) if terms_raw else None,
        hashlib.sha256(terms_raw).hexdigest() if terms_raw else "не указан",
        json.loads(contexts_raw) if contexts_raw else None,
        hashlib.sha256(contexts_raw).hexdigest() if contexts_raw else "не указан",
        json.loads(classification_raw) if classification_raw else None,
        hashlib.sha256(classification_raw).hexdigest() if classification_raw else "не указан",
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        stream.write(result)
    print(json.dumps({"output": str(args.output), "documents": len(profiles["profiles"]), "version": profiles["schema"]}))


if __name__ == "__main__":
    main()
