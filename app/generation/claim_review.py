"""Bound, readable claim/evidence inspection; no scientific decisions or inference."""

from __future__ import annotations

import json
from copy import deepcopy
from html import escape
from pathlib import Path
from typing import Any
from uuid import UUID

from app.documents.service import build_pdf_url
from app.generation.answer_evidence_packet import serialize_packet, validate_packet
from app.generation.claim_checks import build_checks, fact_assertion
from app.generation.preparation_routes import REASONS
from app.generation.requirements_routes import STATES
from app.records.schema import text_hash
from app.records.sources import file_hash

VERSION = "claim_evidence_review_v0.1"
CODE_FILES = ("app/generation/claim_review.py", "app/generation/claim_review_routes.py")
LABELS = {"property": "Показатель", "sample": "Образец / ячейка", "value": "Значение", "unit": "Единица",
    "operation": "Операция", "method": "Метод", "conditions": "Условия", "epistemic_status": "Статус сообщения",
    "unknown_fields": "Неизвестные поля", "source_reported": "Сообщено в источнике",
    "source_reported_approximate": "Сообщено приблизительно", "capacity_retention": "Сохранение ёмкости",
    "coulombic_efficiency": "Кулоновская эффективность", "base_salt_concentration": "Концентрация основной соли",
    "additive_concentration": "Концентрация добавки", "reported_solution_concentration": "Концентрация раствора",
    "measurement_temperature": "Температура измерения", "electrolyte_composition_in_this_clause": "Состав в этой фразе",
    "exact_match": "Точное совпадение", "mismatch_at_bound_anchor": "Не совпадает с выбранной цитатой",
    "exact_bound_surfaces": "Текст полей совпал с raw-фрагментами", "raw_surface_differences": "Есть различия raw-поверхности",
    "not_exact_raw_surface": "Raw-написание отличается", "no_bound_field_anchor": "Для поля нет bound anchor",
    "no_textual_values_asserted": "Текстовые значения не заявлены", "matches_finite_source_contract": "Поля совпали с конечным рецептом",
    "differs_from_bound_fact": "Поля отличаются от записи источника", "not_evaluated": "Не оценено",
    "not_requested": "Не запрошено", "not_applicable_system_arithmetic": "Расчёт системы, не цитата",
    "matches_bound_sum": "Сумма и привязки совпали", "sum_or_binding_mismatch": "Ошибка суммы или её привязок",
    "no_claims": "Утверждения не переданы", "explicit_claim_checks_complete": "Явные проверки завершены"}
STYLE = ("<style>.claim-review{max-width:1200px}.claim-grid{display:grid;grid-template-columns:1fr 1fr;gap:18px}"
    ".claim-card{border:1px solid #b5c5d0;border-radius:10px;padding:18px;margin:18px 0;overflow-wrap:anywhere}"
    ".claim-review pre{white-space:pre-wrap;overflow-wrap:anywhere}.claim-review table{width:100%;border-collapse:collapse}"
    ".claim-review td,.claim-review th{padding:8px;border:1px solid #b5c5d0;text-align:left;vertical-align:top}"
    ".claim-review mark{background:#ffed9e;color:#183044}.claim-review blockquote{margin:10px 0;padding:10px;border-left:3px solid #678}"
    ".claim-status{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin:14px 0}"
    ".claim-status div{padding:10px;background:#edf2f6;border-radius:6px}.claim-review details{margin:10px 0}"
    "@media(max-width:800px){.claim-grid{grid-template-columns:1fr}.claim-status{grid-template-columns:1fr 1fr}}"
    "</style>")


def _hash(value: dict[str, Any]) -> str:
    return text_hash(serialize_packet(value).decode("utf-8"))


def code_bindings() -> dict[str, str]:
    root = Path(__file__).resolve().parents[2]
    return {name: file_hash(root / name) for name in CODE_FILES}


def build_review(packet: dict[str, Any], claims: list[dict[str, Any]], *, expected_packet_id: str) -> dict[str, Any]:
    bindings = code_bindings()
    report = build_checks(packet, packet["content"]["parent"], claims, expected_packet_id=expected_packet_id)
    core = {"version": VERSION, "packet": deepcopy(packet), "report": report, "code_bindings": bindings,
        "meaning": "explicit_diagnostic_inspection_not_human_review_or_scientific_acceptance",
        "human_reviews": [], "generation_performed": False, "admission_changed": False, "network_ready": False}
    if bindings != code_bindings():
        raise ValueError("Claim review code changed during construction")
    return {**core, "review_id": _hash(core)}


def validate_review(review: dict[str, Any], current_packet: dict[str, Any], claims: list[dict[str, Any]], *,
                    expected_packet_id: str, expected_review_id: str) -> None:
    if review.get("review_id") != expected_review_id:
        raise ValueError("Claim review differs from pinned identity")
    rebuilt = build_review(current_packet, claims, expected_packet_id=expected_packet_id)
    if serialize_packet(review) != serialize_packet(rebuilt):
        raise ValueError("Claim review differs from trusted current packet/claims/code reconstruction")


def _label(value: str) -> str:
    return LABELS.get(value, STATES.get(value, value))


def _details(label: str, value: Any) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)
    return "<details><summary>" + escape(label) + "</summary><pre>" + escape(text) + "</pre></details>"


def _value(value: Any) -> str:
    if value is None:
        return "Не указано"
    if isinstance(value, dict) and "text" in value:
        return str(value["text"])
    if isinstance(value, list):
        return "; ".join(_label(str(x)) for x in value) or "Нет в записи"
    return _label(str(value))


def _fact_table(fact: dict[str, Any]) -> str:
    rows = []
    for key in ("property", "sample", "value", "unit", "operation", "method", "conditions", "epistemic_status", "unknown_fields"):
        value = fact[key]
        if key == "conditions":
            for name in sorted(value):
                rows.append("<tr><th>Условие: " + escape(_label(name)) + "</th><td>" + escape(_value(value[name])) + "</td></tr>")
        else:
            rows.append("<tr><th>" + escape(_label(key)) + "</th><td>" + escape(_value(value)) + "</td></tr>")
    return "<table><tbody>" + "".join(rows) + "</tbody></table>"


def _source_html(anchor: dict[str, Any], packet: dict[str, Any]) -> str:
    content, data = packet["content"], anchor["anchor"]
    source = next(s for s in content["sources"] if s["id"] == anchor["source_ref"])
    evidence = next(e for e in content["parent"]["preparation"]["evidence"] if e["chunk_id"] == source["chunk_id"])
    title = evidence.get("title") or "Название не зарегистрировано"
    links = []
    try:
        article_id = str(UUID(source["article_id"]))
    except ValueError:
        links.append("Ссылка недоступна: article ID не является UUID.")
    else:
        page_numbers = {p["id"]: p["page_number"] for p in content["pages"]}
        exact = [page_numbers[s["page_ref"]] for s in anchor["page_spans"]]
        page = exact[0] if exact else source["page_start"]
        location = ("страница " + str(page) if exact else "диапазон " + str(source["page_start"]) + "–" + str(source["page_end"]))
        links.append('<a href="' + escape(build_pdf_url(article_id, "original", page), quote=True)
            + '">Оригинальный PDF · ' + escape(location) + "</a>")
        if source["text_layer"] == "ocr":
            links.append('<a href="' + escape(build_pdf_url(article_id, "ocr", page), quote=True)
                         + '">PDF слоя OCR · ' + escape(location) + "</a>")
    mapping = ("Цитата точно сопоставлена одной странице зарегистрированного текстового слоя."
        if anchor["page_spans"] else "Точная страница цитаты не установлена; ссылка открывает начало диапазона источника.")
    if source["text_layer"] != "original":
        mapping += " Совпадение OCR-текста с текстом оригинального PDF отдельно не проверялось."
    raw = str(source["raw_text"])
    marked = escape(raw[:data["start"]]) + "<mark>" + escape(raw[data["start"]:data["end"]]) + "</mark>" + escape(raw[data["end"]:])
    return ("<div data-claim-source><p><strong>" + escape(str(title)) + "</strong><br>"
        + escape(str(source["citation_id"]) + " · слой: " + str(source["text_layer"])) + "</p><p>" + " · ".join(links) + "</p><p>"
        + escape(mapping) + "</p><blockquote><pre>" + escape(str(data["text"])) + "</pre></blockquote>"
        + "<details><summary>Полный raw-фрагмент с выделением цитаты</summary><pre>" + marked + "</pre></details>"
        + _details("Точный адрес и page mapping", anchor) + "</div>")


def render_catalog(packet: dict[str, Any]) -> str:
    validate_packet(packet, packet["content"]["parent"], expected_packet_id=packet["packet_id"])
    content, items = packet["content"], []
    for row in content["facts"]:
        anchor = next(a for a in content["anchors"] if a["id"] == row["support_ref"])
        items.append('<div class="claim-card"><h3>' + escape(_label(row["fact"]["property"]))
            + '</h3><div class="claim-grid"><div>' + _fact_table(fact_assertion(row["fact"])) + "</div><div>"
            + _source_html(anchor, packet) + "</div></div>" + _details("Fact ID и исходные структурированные поля", row) + "</div>")
    return (STYLE + '<div class="claim-review" data-claim-catalog><h2>Записи выбранных источников</h2>'
        "<p>Это записи существующих source recipes, а не проверенные утверждения ответа. "
        "Утверждения ещё не переданы. Совпадение шаблона не подтверждает научную достоверность.</p>"
        + ("".join(items) if items else "<p>Распознанных записей фактов в этом пакете нет.</p>")
        + _details("Доступные anchors для проверки точной цитаты", content["anchors"])
        + _details("Доступные арифметические преобразования", content["transformations"])
        + _details("Неизвестные и непроверенные области", content["inspection"]) + "</div>")


def render_review(review: dict[str, Any], current_packet: dict[str, Any], *, expected_review_id: str) -> str:
    report = review["report"]
    validate_review(review, current_packet, report["claims"], expected_packet_id=current_packet["packet_id"],
                    expected_review_id=expected_review_id)
    cards = []
    for claim, result in zip(report["claims"], report["results"], strict=True):
        statuses = ["<div><strong>" + label + "</strong><br>" + escape(_label(result[key]["status"])) + "</div>"
            for key, label in (("literal_presence", "Наличие в тексте"), ("semantic_support", "Конечный смысловой контракт"),
                               ("arithmetic", "Арифметика"), ("scientific_validity", "Научная достоверность"))]
        if claim["kind"] == "quotation":
            asserted = "<blockquote><pre>" + escape(claim["text"]) + "</pre></blockquote>"
        elif claim["kind"] == "fact":
            asserted = _fact_table(claim["assertion"])
        else:
            value = claim["assertion"]
            asserted = "<p>" + escape(" + ".join(value["operands"]) + " = " + value["result"] + " " + value["unit"]) + "</p>"
        semantic = result["semantic_support"]
        diagnostics = ""
        if semantic.get("differences"):
            diagnostics += "<h4>Расхождения полей</h4><table><thead><tr><th>Поле</th><th>Заявлено</th><th>В записи источника</th></tr>"
            diagnostics += "<tbody>" + "".join("<tr><th>" + escape(d["field"]) + "</th><td>" + escape(_value(d["asserted"]))
                + "</td><td>" + escape(_value(d["bound"])) + "</td></tr>" for d in semantic["differences"]) + "</tbody></table>"
        if "bound_unknown_fields" in semantic:
            diagnostics += "<p>Неизвестные поля источника: " + escape(_value(semantic["bound_unknown_fields"])) + ".</p>"
            identity = semantic["role_identity"]
            diagnostics += "<p>Связь ролей: " + escape(_label(identity["state"]) if identity else "Не оценена") + ".</p>"
        if semantic.get("status") == "ambiguous_source_candidates":
            diagnostics += "<p>Варианты источников конфликтуют. Совпадение с одним вариантом не снимает неоднозначность.</p>"
        if semantic.get("uninspected_sources"):
            diagnostics += "<p>Часть выбранных источников не проверена.</p>"
        sources = "".join(_source_html(a, current_packet) for a in result["anchors"])
        cards.append('<article class="claim-card" data-claim-card><h3>Утверждение ' + escape(claim["id"])
            + '</h3><div class="claim-status">' + "".join(statuses) + '</div><div class="claim-grid"><div><h4>Заявлено</h4>'
            + asserted + diagnostics + "</div><div><h4>Источник и точные цитаты</h4>" + sources + "</div></div>"
            + _details("Подробные основания, нормализация, refs и вычисления", result) + "</article>")
    blockers = report["stop"]["baseline"]["baseline_blocking_reasons"]
    reasons = "".join("<li>" + escape(REASONS.get(b, b)) + "</li>" for b in blockers)
    return (STYLE + '<div class="claim-review" data-claim-review><h2>Утверждения и их основания</h2>'
        "<p>Детерминированные диагностические проверки. Научная достоверность не оценена. "
        "Копирование цитаты и совпадение полей не доказывают смысловую поддержку произвольного вывода. "
        "Расхождение полей не объявляется научным противоречием. Человеческое решение не записывалось.</p>"
        + "<p>Исходные блокировки сохранены:</p>" + ("<ul>" + reasons + "</ul>" if reasons else "<p>Нет записанных блокировок.</p>")
        + "<p>Остановка: " + escape(_label(report["stop"]["reason"])) + ". Проверок: " + str(len(report["results"])) + ".</p>"
        + "".join(cards) + _details("Журнал системных наблюдений — не human review", report["journal"])
        + _details("Идентификаторы снимков и версии", {"review_id": review["review_id"], "packet_id": report["packet_id"],
             "report_id": report["report_id"], "version": review["version"], "code_bindings": review["code_bindings"]}) + "</div>")
