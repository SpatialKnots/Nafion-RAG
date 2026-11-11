"""Freeze-preserving offline intake of the supplied twenty Satoh/Fan development cases."""

from __future__ import annotations

import argparse
import json
import re
import sys
from html import escape
from pathlib import Path
from typing import Any

from app.generation.answer_requirements import _query
from scripts import gigachat_answer_smoke as files

ROOT = files.ROOT
BASE = ROOT / "output/satoh_fan_qa_20261110"
FREEZE = BASE / "freeze_v01"
PROTOCOL = ROOT / "docs/records/satoh_fan_qa_intake_protocol_2026-11-10_v0.1.md"
VERSION = "satoh_fan_development_intake_v0.1"
PROVENANCE = {"source": "user_reply_in_current_chat", "statement_verbatim": "Я составил ответы. Видел ответы сам",
    "authorship": "user_declared_self", "answer_exposure": "user_declared_answers_seen",
    "specific_outputs_and_timing": "not_declared", "llm_assistance": "not_declared",
    "expert_verification": "not_declared", "independent_annotation": "not_established",
    "implementation_agent_has_seen_references": True, "evaluation_status": "development_exposed_not_hidden_gold"}


def span(raw: str, start: int, end: int) -> dict[str, Any]:
    if not 0 <= start < end <= len(raw):
        raise ValueError("Invalid original Markdown span")
    return {"start": start, "end": end, "text": raw[start:end], "offset_unit": "unicode_code_points_end_exclusive"}


def parse_document(raw: str) -> dict[str, Any]:
    sections = list(re.finditer(r"^## Статья (?P<n>[12])\. (?P<label>[^\r\n]+)\r?$", raw, re.M))
    rubrics = list(re.finditer(r"^## Рекомендуемая оценка ответов Ariadne\r?$", raw, re.M))
    if len(sections) != 2 or [m["n"] for m in sections] != ["1", "2"] or len(rubrics) != 1:
        raise ValueError("Expected exactly two ordered article sections and one separately stored rubric")
    if not sections[1].end() < rubrics[0].start():
        raise ValueError("Rubric must follow both article sections")
    cases, articles = [], []
    for index, section in enumerate(sections):
        expected_name = "Satoh" if index == 0 else "Fan"
        expected_year = "2013" if index == 0 else "2018"
        expected_doi = "10.1149/05048.0127ecst" if index == 0 else "10.1038/s41565-018-0183-2"
        if section["label"].strip() != expected_name + " et al., " + expected_year:
            raise ValueError("Article header differs from the declared source binding")
        end = sections[index + 1].start() if index == 0 else rubrics[0].start()
        questions = list(re.finditer(r"^### (?P<n>\d+)\. (?P<q>[^\r\n]+)\r?$", raw[section.end():end], re.M))
        if [m["n"] for m in questions] != [str(i) for i in range(1, 11)]:
            raise ValueError("Each article must contain questions 1..10 exactly once and in order")
        first = section.end() + questions[0].start()
        article = {"label": expected_name, "declared_heading": section["label"],
            "heading_span": span(raw, section.start(), section.end()),
            "bibliography_span": span(raw, section.end(), first)}
        if article["bibliography_span"]["text"].count(expected_doi) != 1:
            raise ValueError("Article bibliography DOI differs from the declared source binding")
        articles.append(article)
        for i, question in enumerate(questions):
            left = section.end() + question.end()
            right = section.end() + questions[i + 1].start() if i + 1 < len(questions) else end
            block = raw[left:right]
            answers = list(re.finditer(r"\*\*Эталонный ответ:\*\*", block))
            sources = list(re.finditer(r"\*\*Источник:\*\*[ \t]*(?P<text>[^\r\n]+)", block))
            if len(answers) != 1 or len(sources) != 1 or answers[0].end() >= sources[0].start():
                raise ValueError("Each question requires one answer and one following source pointer")
            answer = span(raw, left + answers[0].end(), left + sources[0].start())
            if not answer["text"].strip():
                raise ValueError("Reference answer is empty")
            qstart, qend = section.end() + question.start("q"), section.end() + question.end("q")
            cases.append({"id": expected_name + f"_{i + 1:02}", "article_label": expected_name,
                "question_span": span(raw, qstart, qend), "reference_answer_span": answer,
                "source_pointer_span": span(raw, left + sources[0].start("text"), left + sources[0].end("text")),
                "reference_validation": "not_scientifically_validated", "actual_model_output": None,
                "actual_score": None, "scientific_validity": "not_evaluated"})
    return {"articles": articles, "cases": cases, "rubric_span": span(raw, rubrics[0].start(), len(raw)),
            "rubric_status": "user_supplied_proposal_not_adopted_or_executed"}


def public_questions(parsed: dict[str, Any], sources: dict[str, dict[str, Any]]) -> dict[str, Any]:
    articles = {a["label"]: a for a in parsed["articles"]}
    rows = []
    for case in parsed["cases"]:
        label, question = case["article_label"], case["question_span"]["text"]
        heading = articles[label]["declared_heading"]
        rows.append({"id": case["id"], "question_verbatim": question, "article_context_declared": heading,
            "article_id": sources[label]["article"]["article_id"],
            "original_pdf_sha256": sources[label]["article"]["original_pdf_sha256"],
            "suggested_scoped_question_unsent": "По статье " + heading + ": " + question,
            "augmentation": "explicit_article_context_from_section_header_original_question_unchanged",
            "request_constructed": False, "model_call_authorized": False})
    return {"version": VERSION, "purpose": "question_only_development_inputs_not_native_requests", "cases": rows}


def page_map(source: dict[str, Any]) -> list[dict[str, Any]]:
    label, mapped = source["label"], []
    marker = "ECS Transactions, 50 (48)" if label == "Satoh" else "Nature Nanotechnology | VOL 13"
    for page in source["pages"]:
        raw = page["text"]
        start = raw.rfind(marker)
        printed = list(re.finditer(r"(?m)^\s*(?P<n>\d{3})\s*$", raw[start:])) if start >= 0 else []
        if len(printed) > 1:
            raise ValueError("Ambiguous literal page footer")
        match = printed[0] if printed else None
        mapped.append({"pdf_page": page["pdf_page"], "printed_page": int(match["n"]) if match else None,
            "mapping": "literal_page_footer" if match else "no_printed_page_number_proven",
            "footer_span": span(raw, start + match.start("n"), start + match.end("n")) if match else None,
            "page_text_sha256": page["page_text_sha256"]})
    return mapped


def resolve_pointer(pointer: str, source: dict[str, Any], mapped: list[dict[str, Any]]) -> dict[str, Any]:
    match = re.search(r"стр\.\s*(?P<spec>\d+(?:(?:\s*[–-]\s*|\s*,\s*)\d+)*)", pointer)
    if match is None:
        raise ValueError("Missing declared printed-page pointer")
    printed: set[int] = set()
    for part in match["spec"].split(","):
        bounds = re.split(r"[–-]", part)
        if len(bounds) == 1:
            printed.add(int(bounds[0]))
        else:
            left, right = map(int, bounds)
            if not left <= right <= left + 30:
                raise ValueError("Invalid declared printed-page range")
            printed.update(range(left, right + 1))
    lookup = {p["printed_page"]: p["pdf_page"] for p in mapped if p["printed_page"] is not None}
    if not printed <= lookup.keys():
        raise ValueError("Declared printed page is not registered in this article")
    methods = []
    if "Screening of electrolytes" in pointer:
        methods = [p["pdf_page"] for p in source["pages"] if "Screening of electrolytes." in p["text"]]
        if len(methods) != 1:
            raise ValueError("Named Methods section is missing or ambiguous")
    supplements = re.findall(r"Supplementary Figs?\.\s*[\d–, -]+", pointer)
    return {"printed_pages": sorted(printed), "pdf_pages": sorted({lookup[n] for n in printed}),
        "named_methods_pdf_pages": methods, "supplementary_pointers": supplements,
        "supplementary_material_provided_in_this_intake": False,
        "status": "main_PDF_locations_resolved_supplement_unverified" if supplements else "main_PDF_locations_resolved",
        "meaning": "source_location_only_not_semantic_support_or_scientific_acceptance"}


def literal_observation(source: dict[str, Any], pdf_page: int, pattern: str, reason: str) -> dict[str, Any]:
    page = next(p for p in source["pages"] if p["pdf_page"] == pdf_page)
    matches = list(re.finditer(pattern, page["text"], re.S))
    if len(matches) != 1:
        raise ValueError("Declared diagnostic source observation is not unique: " + reason)
    m = matches[0]
    return {"article_label": source["label"], "pdf_page": pdf_page, "page_text_sha256": page["page_text_sha256"],
        "span": span(page["text"], m.start(), m.end()), "reason": reason,
        "status": "literal_observation_not_independent_scientific_validation"}


def _detail(label: str, value: Any) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)
    return "<details><summary>" + escape(label) + "</summary><pre>" + escape(text) + "</pre></details>"


def render(report: dict[str, Any]) -> str:
    public = {c["id"]: c for c in report["public_questions"]["cases"]}
    articles = {a["label"]: a for a in report["parsed"]["articles"]}
    parts = []
    for label, source in report["sources"].items():
        parts.append("<h2>" + escape(label) + "</h2>" + _detail("Библиография пользователя, без исправлений",
                     articles[label]["bibliography_span"]["text"]))
        for case in [c for c in report["parsed"]["cases"] if c["article_label"] == label]:
            links = []
            for page in sorted(set(case["source_locations"]["pdf_pages"] + case["source_locations"]["named_methods_pdf_pages"])):
                href = Path(source["article"]["original_pdf_path"]).as_uri() + "#page=" + str(page)
                links.append('<a href="' + escape(href, quote=True) + '">PDF ' + str(page) + "</a>")
            parts.append('<section data-qa-case="' + case["id"] + '"><h3>' + case["id"] + "</h3><p>"
                + escape(case["question_span"]["text"]) + "</p>" + " · ".join(links)
                + _detail("Исходный эталон пользователя — scientific validation не выполнена", case["reference_answer_span"]["text"])
                + "<p>Указатель пользователя: " + escape(case["source_pointer_span"]["text"]) + "</p>"
                + _detail("Привязки страниц и непроверенные supplement pointers", case["source_locations"])
                + _detail("Применимость текущей конечной карты — не результат /answer", case["finite_query_applicability"])
                + _detail("Question-only контекст и несохранённый как request вариант", public[case["id"]]) + "</section>")
    return ("<!doctype html><html lang='ru'><meta charset='utf-8'><title>ARIADNE — Satoh/Fan QA intake</title>"
        "<style>body{font:16px/1.5 system-ui;max-width:1100px;margin:25px auto;padding:0 18px;color:#183044}"
        "section{border:1px solid #b5c5d0;border-radius:8px;margin:15px 0;padding:16px}"
        "pre{white-space:pre-wrap;overflow-wrap:anywhere}summary{cursor:pointer}details{margin:10px 0}</style><body>"
        "<h1>Satoh/Fan:20 supplied development QA</h1><p>Два ранее раскрытых PDF. Эталоны предоставлены пользователем; "
        "просмотр ответов задекларирован, участие LLM/точное время не указаны. Это не hidden independent gold. "
        "Модель не запускалась, баллы не выставлялись, исходные вопросы и эталоны сохранены.</p>"
        + _detail("Итог и ограничения", report["summary"]) + _detail("Provenance", report["provenance"])
        + _detail("Отдельные source observations/неоднозначные указатели", report["source_observations"])
        + "".join(parts) + _detail("Предложенная шкала пользователя — не применена", report["parsed"]["rubric_span"]["text"])
        + "</body></html>")


def run(output: Path) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=False)
    files.verify_manifest(FREEZE)
    frozen_bindings = json.loads((FREEZE / "bindings.json").read_bytes())
    files.verify(frozen_bindings)
    app_bindings = files.bindings([*ROOT.joinpath("app").rglob("*.py"), *ROOT.joinpath("app").rglob("*.yaml")])
    raw_bytes = (FREEZE / "user_input_original.md").read_bytes()
    raw = raw_bytes.decode("utf-8")
    parsed = parse_document(raw)
    sources = {s["label"]: s for s in json.loads((FREEZE / "sources.json").read_bytes())}
    mappings = {label: page_map(s) for label, s in sources.items()}
    public = public_questions(parsed, sources)
    public_by_id = {c["id"]: c for c in public["cases"]}
    for case in parsed["cases"]:
        label = case["article_label"]
        case["source_locations"] = resolve_pointer(case["source_pointer_span"]["text"], sources[label], mappings[label])
        query = public_by_id[case["id"]]
        original, original_cells = _query(query["question_verbatim"])
        scoped, scoped_cells = _query(query["suggested_scoped_question_unsent"])
        case["finite_query_applicability"] = {"original_reason": original, "original_cells": original_cells,
            "explicit_context_variant_reason": scoped, "explicit_context_variant_cells": scoped_cells,
            "scope": "finite_requirement_map_only_not_whole_product_answerability"}
        for key in ("question_span", "reference_answer_span", "source_pointer_span"):
            s = case[key]
            if raw[s["start"]:s["end"]] != s["text"]:
                raise ValueError("Original reference span changed")
    observations = [
        literal_observation(sources["Satoh"], 1, r"10\.1149/05048\.0127ecst", "Satoh DOI literal"),
        literal_observation(sources["Fan"], 1, r"10\.1038/s41565-018-0183-2", "Fan DOI literal"),
        literal_observation(sources["Satoh"], 8, r"11\.20, 15\.91, 9\.27, and 13\.59",
                            "Satoh_08 activation values, source order preserved"),
        literal_observation(sources["Satoh"], 13, r"Although the\s+organofluorine compounds have not been identified",
                            "Satoh_07 identification caveat"),
        literal_observation(sources["Fan"], 5, r"recoverable capacity \(Fig\. 3e\)", "Fan_07 main-text panel pointer"),
        literal_observation(sources["Fan"], 4, r"d, Recoverable capacity.*?48\s*h", "Fan_07 caption names panel d instead"),
        literal_observation(sources["Fan"], 5, r">.*?680.*?total cathode/anode masses", "Fan_10 energy mass basis, not whole cell"),
    ]
    observations.append({"case_id": "Fan_07", "kind": "source_internal_panel_pointer_discrepancy",
        "note": "User cites Fig.3d; caption also names d for recoverable capacity, main text names Fig.3e. "
                "Displayed recovery curve is labelled e. Preserve original pointer; do not silently correct the reference.",
        "observed_PDF_pages": [4, 5], "scientific_support": "not_evaluated"})
    summary = {"version": VERSION, "input_sha256": files.sha(raw_bytes), "cases": len(parsed["cases"]),
        "cases_per_article": {label: sum(c["article_label"] == label for c in parsed["cases"]) for label in sources},
        "fresh_PDF_page_texts": sum(s["pdf_pages"] for s in sources.values()), "PDF_hashes_verified": len(sources),
        "main_source_pointers_resolved": len(parsed["cases"]),
        "cases_with_unverified_supplement_pointers": [c["id"] for c in parsed["cases"] if c["source_locations"]["supplementary_pointers"]],
        "finite_requirement_map_recognized_scoped_queries": sum(c["finite_query_applicability"]["explicit_context_variant_reason"] is None
                                                                  for c in parsed["cases"]),
        "semantic_source_support": "not_evaluated", "scientific_validity": "not_evaluated", "score": None,
        "proposed_user_rubric_executed": False, "new_model_calls": 0, "new_oauth_calls": 0, "new_slots": 0,
        "DB_calls": 0, "original_PDFs_modified": False, "pilot_enrollment": "none_development_only_not_24_new_tasks",
        "limitations": ["Prior corpus and reference exposure, no independent gold",
            "Source-location mapping is not full semantic validation of20 reference answers",
            "Supplementary figures not supplied; source narrative and figure evidence distinguished",
            "Broad question families; finite-map non-applicability is not a measured /answer refusal",
            "No new API/model execution, scoring, source grammar fix or retrieval change"]}
    report = {"summary": summary, "provenance": PROVENANCE, "parsed": parsed, "public_questions": public,
        "sources": sources, "page_maps": mappings, "source_observations": observations}
    files.save(output / "user_input_original.md", raw_bytes)
    files.write(output / "questions_only.json", public)
    files.write(output / "references_development.json", {"version": VERSION, "provenance": PROVENANCE,
        "cases": [{k: c[k] for k in ("id", "reference_answer_span", "source_pointer_span", "reference_validation")}
                  for c in parsed["cases"]],
        "original_rubric": parsed["rubric_span"], "rubric_status": parsed["rubric_status"]})
    report["bindings"] = files.bindings([Path(__file__), PROTOCOL, FREEZE / "manifest.json", *[Path(s["article"]["original_pdf_path"])
        for s in sources.values()], ROOT / "app/generation/answer_requirements.py"])
    report["app_bindings"] = app_bindings
    files.verify(app_bindings)
    files.verify(report["bindings"])
    files.write(output / "report.json", report)
    html = render(report)
    if html.count("data-qa-case=") != 20:
        raise ValueError("HTML case inventory changed")
    files.save(output / "review.html", html.encode())
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    policy = files.NetworkPolicy()
    sys.addaudithook(policy)
    summary = run(args.output)
    files.write(args.output / "network.json", {"external_denials": policy.denied})
    if policy.denied:
        raise ValueError("External network attempted")
    files.manifest(args.output)
    print(json.dumps(summary, ensure_ascii=True), flush=True)


if __name__ == "__main__":
    main()
