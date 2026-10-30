"""Source-bound finite scope diagnostics for saved answers. Never scientific admission."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Any

from scripts.event_value_ownership_audit import recognition_view, source_regions
from scripts.experiment_sentence_links import statement_units

VERSION = "answer_scope_audit_v0.2"
_NUMBER = r"\d+(?:[.,]\d+)?"
_MAXIMUM = re.compile(r"\b(?:максим\w*|наибольш\w*|maximum|maximal|highest|largest)\b", re.I)
_PROPERTY = re.compile(r"\b(?:набух\w*|swelling)\b", re.I)
_ROOM = re.compile(r"\b(?:комнатн\w*\s+температур\w*|room\s+temperature)\b", re.I)
_FORM = re.compile(r"(?<!\w)(Li|H)(?:[-‑– ](?:Nafion|форм\w*|form)\b|(?=\b))", re.I)
_RESTRICTION = re.compile(r"\b(?:среди|из\s+набора|в\s+таблице|among|within\s+the\s+(?:set|table)|in\s+table)\b", re.I)
_SCOPE_CUES = {
    "mixture": re.compile(r"\b(?:смес\w*|смешан\w*|mixtures?|mixed)\b", re.I),
    "individual_solvent": re.compile(r"\b(?:индивидуальн\w*\s+растворител\w*|чист\w*\s+растворител\w*|pure\s+solvents?)\b", re.I),
}
_TEMPERATURE = re.compile(
    rf"(?<![\w.,–—-])(?P<lo>-?{_NUMBER})(?:\s*[-–—]\s*(?P<hi>-?{_NUMBER}))?\s*°\s*[CС](?!\w)", re.I)
_ALPHA = re.compile(
    rf"(?<!\w)(?:α|alpha)\s*_?\s*(?P<form>Li|H)\s*=\s*(?P<value>{_NUMBER})"
    rf"(?!\w|[.,]\d|\s*(?:[-–—]|to\b|до\b)\s*\d)", re.I)
_FOR_FORM = re.compile(
    rf"(?<![\w.,–—-])(?P<value>{_NUMBER})\s+(?:для|for)\s+(?P<form>Li|H)[-‑– ](?:форм\w*|form)\b", re.I)
_BASIS = {
    "regression": re.compile(r"\b(?:регресс\w*|regression|model[- ]derived|расчетн\w*|расчётн\w*)\b", re.I),
    "experiment": re.compile(r"\b(?:экспериментальн\w*|experimental(?:ly)?|observed)\b", re.I),
}
_UNCERTAIN = re.compile(
    r"\b(?:не|not|never|если|if|could|would|respectively|соответственно|аналогич\w*)\b", re.I)
_APPROXIMATE = re.compile(r"(?:около|примерно|about|approximately|≈|~)\s*$", re.I)


@dataclass(frozen=True)
class PageSource:
    article_id: str
    page_number: int
    text_layer: str
    original_pdf_path: str
    original_pdf_sha256: str
    page_text: str
    origin: str


@dataclass(frozen=True)
class SuppliedEvidence:
    citation_id: str
    article_id: str
    chunk_id: str
    page_start: int
    page_end: int
    text_layer: str
    text: str


def _hits(pattern: re.Pattern[str], text: str, offset: int = 0) -> list[dict[str, Any]]:
    return [{"start": offset + m.start(), "end": offset + m.end(), "text": m.group()} for m in pattern.finditer(text)]


def requirements(question: str) -> dict[str, Any]:
    if not question.strip():
        raise ValueError("Question must be nonblank")
    view = recognition_view(question)
    forms = sorted({m.group(1).lower() for m in _FORM.finditer(view.text)})
    return {"maximum": bool(_MAXIMUM.search(view.text)), "swelling": bool(_PROPERTY.search(view.text)),
        "forms": forms, "room_temperature": bool(_ROOM.search(view.text)),
        "temperatures": temperatures(question), "comparison_restriction_cues": _hits(_RESTRICTION, question),
        "medium_cues": {key: _hits(pattern, question) for key, pattern in _SCOPE_CUES.items()},
        "interpretation": "finite_grammar_only_no_complete_question_parse"}


def temperatures(text: str) -> list[dict[str, Any]]:
    view = recognition_view(text)
    return [{**view.anchor(m.start(), m.end()), "low": str(Decimal(m["lo"].replace(",", "."))),
             "high": str(Decimal(m["hi"].replace(",", "."))) if m["hi"] else None, "unit": "Celsius"}
            for m in _TEMPERATURE.finditer(view.text)]


def numeric_relations(text: str) -> list[dict[str, Any]]:
    """Explicit syntax only. No table parsing, percent conversion or unlabeled numbers."""
    view = recognition_view(text)
    result = []
    for kind, pattern in (("alpha_assignment", _ALPHA), ("number_for_form", _FOR_FORM)):
        for m in pattern.finditer(view.text):
            if kind == "number_for_form" and re.search(r"\d\s+(?:to|до)\s*$", view.text[:m.start()], re.I):
                continue
            # A trailing percent is not silently read as dimensionless alpha.
            percent = bool(re.match(r"\s*%", view.text[m.end():]))
            result.append({"syntax": kind, "form": m["form"].lower(), "value": str(Decimal(m["value"].replace(",", "."))),
                "unit": "percent_unmodeled" if percent else "alpha_symbol" if kind == "alpha_assignment" else "unresolved",
                "relation": view.anchor(m.start(), m.end()), "number": view.anchor(m.start("value"), m.end("value")),
                "form_anchor": view.anchor(m.start("form"), m.end("form")),
                "immediate_approximation_cue": bool(_APPROXIMATE.search(view.text[:m.start()])),
                "scientific_relation": "unverified_explicit_syntax_only"})
    return sorted(result, key=lambda r: r["relation"]["start"])


def _validate(pages: Sequence[PageSource], evidence: Sequence[SuppliedEvidence]) -> None:
    keys = [(p.article_id, p.page_number, p.text_layer) for p in pages]
    if len(keys) != len(set(keys)):
        raise ValueError("Source pages must have unique article/page/layer identities")
    for page in pages:
        if (not page.article_id.strip() or type(page.page_number) is not int or page.page_number < 1 or page.text_layer != "original"
                or not page.original_pdf_path.strip() or not re.fullmatch(r"[0-9a-f]{64}", page.original_pdf_sha256)
                or page.origin not in {"registered_original_run_page", "posthoc_original_pdf_page"}):
            raise ValueError("Source page identity/provenance is invalid")
    for article_id in {p.article_id for p in pages}:
        identities = {(p.original_pdf_path, p.original_pdf_sha256) for p in pages if p.article_id == article_id}
        if len(identities) != 1:
            raise ValueError("Conflicting original PDF identities for one article")
    if len({e.citation_id for e in evidence}) != len(evidence):
        raise ValueError("Evidence citation IDs must be unique")
    for item in evidence:
        if (not all(x.strip() for x in (item.citation_id, item.article_id, item.chunk_id, item.text_layer, item.text))
                or not 1 <= item.page_start <= item.page_end):
            raise ValueError("Supplied evidence identity/range/text is invalid")
        if not any(p.article_id == item.article_id and p.text_layer == item.text_layer
                   and item.page_start <= p.page_number <= item.page_end for p in pages):
            raise ValueError("Supplied evidence has no matching source page registry")
        registered = {p.page_number for p in pages if p.article_id == item.article_id and p.text_layer == item.text_layer}
        if set(range(item.page_start, item.page_end + 1)) - registered:
            raise ValueError("Supplied evidence page range has missing registered pages")


def candidates(page: PageSource, evidence: Sequence[SuppliedEvidence]) -> list[dict[str, Any]]:
    text = page.page_text
    units = statement_units(text)
    regions = source_regions(text)
    output = []
    for relation in numeric_relations(text):
        span = relation["relation"]
        containing = [u for u in units if u.start <= span["start"] and span["end"] <= u.end]
        if len(containing) != 1:
            raise ValueError("Detected numeric relation has no unique source statement")
        unit = containing[0]
        local = text[unit.start:unit.end]
        cues = [{"kind": kind, **s} for kind, pattern in _BASIS.items() for s in _hits(pattern, local, unit.start)]
        before = sorted((s for s in cues if s["end"] <= span["start"]), key=lambda s: s["end"])
        temps = [{**s, "start": s["start"] + unit.start, "end": s["end"] + unit.start} for s in temperatures(local)]
        medium = {key: _hits(pattern, local, unit.start) for key, pattern in _SCOPE_CUES.items()}
        owner_regions = [r for r in regions if r["start"] <= span["start"] and span["end"] <= r["end"]]
        diagnostics = ["scientific_value_ownership_unresolved", "maximum_comparison_universe_not_established"]
        if relation["syntax"] == "number_for_form":
            diagnostics.extend(["property_and_material_identity_not_explicit_in_value_relation", "value_unit_unresolved"])
        if relation["unit"] == "percent_unmodeled":
            diagnostics.append("percent_to_alpha_conversion_not_implemented")
        if not temps:
            diagnostics.append("temperature_not_in_value_statement")
        else:
            diagnostics.append("same_statement_temperature_not_ownership_proof")
        if len(temps) > 1 or any(t["high"] is not None for t in temps):
            diagnostics.append("multiple_or_range_temperature_scope_unresolved")
        if len({r["form"] for r in numeric_relations(local)}) > 1:
            diagnostics.append("mixed_forms_in_statement_no_condition_transfer")
        if _UNCERTAIN.search(local):
            diagnostics.append("negation_reference_or_coordination_unresolved")
        if len({s["kind"] for s in cues}) > 1:
            diagnostics.append("mixed_regression_experiment_cues_unresolved")
        if any(medium.values()):
            diagnostics.append("medium_cue_locality_not_value_scope_proof")
        else:
            diagnostics.append("medium_scope_not_explicit_in_value_statement")
        if all(medium.values()):
            diagnostics.append("multiple_medium_scopes_unresolved")
        bindings = [{"citation_id": e.citation_id, "chunk_id": e.chunk_id,
                     "occurrences_in_supplied_text": e.text.count(span["text"])} for e in evidence
                    if e.article_id == page.article_id and e.text_layer == page.text_layer
                    and e.page_start <= page.page_number <= e.page_end and span["text"] in e.text]
        output.append({**relation, "source": {k: v for k, v in asdict(page).items() if k != "page_text"},
            "statement": {"start": unit.start, "end": unit.end, "text": local}, "temperature_candidates": temps,
            "medium_cues": medium, "basis_cues": cues, "nearest_preceding_basis_cue_unverified": before[-1] if before else None,
            "operation_regions": owner_regions, "supplied_evidence_bindings": bindings,
            "available_as_exact_fragment_in_supplied_evidence": bool(bindings), "diagnostics": diagnostics,
            "state": "unresolved"})
    return output


def audit(question: str, claims: Sequence[dict[str, Any]], evidence: Sequence[SuppliedEvidence],
          pages: Sequence[PageSource]) -> dict[str, Any]:
    """Read actual claims/citations. Never fabricate events or modify answer status."""
    _validate(pages, evidence)
    req = requirements(question)
    known = {e.citation_id for e in evidence}
    if not claims or any(not isinstance(c.get("text"), str) or not c["text"].strip()
           or not isinstance(c.get("citation_ids"), list) or not c["citation_ids"] for c in claims):
        raise ValueError("Audit requires nonblank structurally valid cited claims")
    if any(not isinstance(cid, str) or cid not in known for c in claims for cid in c["citation_ids"]):
        raise ValueError("Claim contains unknown citation ID")
    source_candidates = [r for page in pages for r in candidates(page, evidence)]
    results = []
    for index, claim in enumerate(claims):
        checked = []
        for selected in numeric_relations(claim["text"]):
            same_form = [c for c in source_candidates if c["form"] == selected["form"]]
            cited = [c for c in same_form if c["value"] == selected["value"] and c["unit"] == selected["unit"] and any(
                b["citation_id"] in claim["citation_ids"] for b in c["supplied_evidence_bindings"])]
            # Number-for-form has unresolved units/property; never compare it as a scientifically established alpha.
            larger = [c for c in same_form if selected["unit"] == "alpha_symbol" and c["unit"] != "percent_unmodeled"
                      and Decimal(c["value"]) > Decimal(selected["value"])]
            claim_temperatures = temperatures(claim["text"])
            local_temperatures = [t for c in cited for t in c["temperature_candidates"]]
            wanted_temperatures = req["temperatures"] + claim_temperatures
            requested_points = {t["low"] for t in wanted_temperatures if t["high"] is None}
            local_points = {t["low"] for t in local_temperatures if t["high"] is None}
            temperature_diagnostics = []
            if (req["room_temperature"] or _ROOM.search(claim["text"])):
                temperature_diagnostics.append("room_temperature_numeric_equivalence_unresolved")
            if wanted_temperatures and not local_temperatures:
                temperature_diagnostics.append("temperature_not_on_cited_value_statement")
            if any(t["high"] is not None for t in wanted_temperatures + local_temperatures):
                temperature_diagnostics.append("range_point_equivalence_unresolved")
            if requested_points and local_points and not requested_points.intersection(local_points):
                temperature_diagnostics.append("different_explicit_temperature_points_locality_only")
            if len(local_points) > 1:
                temperature_diagnostics.append("multiple_temperature_owners_unresolved")
            form_status = ("different_requested_form" if req["forms"] and selected["form"] not in req["forms"]
                           else "same_label_only_unverified")
            requested_medium = {k for k, hits in req["medium_cues"].items() if hits}
            claim_medium = {k for k, pattern in _SCOPE_CUES.items() if pattern.search(claim["text"])}
            local_medium = {k for c in cited for k, hits in c["medium_cues"].items() if hits}
            medium_diagnostics = ["medium_locality_does_not_establish_value_scope"]
            if (requested_medium or claim_medium) and not local_medium:
                medium_diagnostics.append("medium_not_explicit_on_cited_value_statement")
            if requested_medium and local_medium and not requested_medium.intersection(local_medium):
                medium_diagnostics.append("different_medium_type_cues_unresolved")
            checked.append({"claim_numeric_relation": selected,
                "requested_form_surface_status": form_status,
                "cited_exact_numeric_surface_candidates": cited,
                "numeric_surface_status": "present_unverified" if cited else "not_detected_in_cited_evidence",
                "larger_same_form_numeric_review_candidates": larger,
                "temperature_check": {"question": req["temperatures"], "claim": claim_temperatures,
                    "cited_value_statement_candidates": local_temperatures, "diagnostics": temperature_diagnostics,
                    "state": "unresolved_no_condition_transfer"},
                "operation_ownership": "unresolved_source_regions_are_diagnostics_only",
                "medium_scope_check": {"requested_cues": sorted(requested_medium), "claim_cues": sorted(claim_medium),
                    "cited_value_statement_cues": sorted(local_medium), "diagnostics": medium_diagnostics,
                    "state": "unresolved_no_medium_transfer"},
                "comparison_status": "not_scientifically_established_no_conditions_or_units_assumed"})
        warnings = ["claim_entailment_and_numeric_ownership_not_established"]
        if req["maximum"]:
            warnings.append("maximum_scope_and_candidate_completeness_not_established")
        if req["room_temperature"]:
            warnings.append("room_temperature_not_equated_with_numeric_celsius")
        if not checked:
            warnings.append("claim_numeric_syntax_outside_finite_scope")
        results.append({"claim_index": index, "original_claim": claim, "checks": checked, "diagnostics": warnings,
                        "comparison_universe": {"request_restriction_cues": req["comparison_restriction_cues"],
                            "claim_restriction_cues": _hits(_RESTRICTION, claim["text"]),
                            "state": "not_established_restriction_mentions_are_not_an_enumerated_universe"},
                        "scientific_coverage": "unresolved"})
    return {"version": VERSION, "question": question, "requirements": req, "claims": results,
        "source_candidates": source_candidates,
        "source_context_inventory": [{"article_id": p.article_id, "page_number": p.page_number, "origin": p.origin,
            "temperature_candidates": temperatures(p.page_text),
            "medium_cues": {k: _hits(pattern, p.page_text) for k, pattern in _SCOPE_CUES.items()},
            "layout_diagnostics": (["table_column_value_extraction_not_implemented"] if re.search(
                r"\b(?:таблиц\w*|tables?)\b", p.page_text, re.I) else []) +
                (["caption_to_value_link_not_implemented"] if re.search(r"\b(?:рисунок|figure)\b", p.page_text, re.I) else []),
            "page_mentions_are_not_value_conditions": True} for p in pages],
        "scientific_coverage": "unresolved" if req["maximum"] and req["swelling"] else "outside_finite_maximum_swelling_scope",
        "runtime_action": "none_offline_only", "answer_modified": False,
        "limits": ["finite_ru_en_syntax_not_semantic_extraction", "no_table_column_or_caption_link_resolution",
                   "no_room_temperature_definition_or_unit_conversion", "no_completeness_or_scientific_entailment_proof",
                   "no_reference_labels_or_model_calls_used"]}
