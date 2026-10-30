"""Finite offline event-link proposals with exact anchors; no scientific admission.

All relation/identity matches are proposals. Unknown syntax, negation, mixed
events and source mapping failures remain diagnostics, never repaired answers.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import Any, cast

from scripts.requested_information_audit import Span, audit_duration, duration_spans

VERSION = "requested_context_links_v0.1"
_SAMPLE = re.compile(r"\b(?:sample|specimen|образ(?:ец|ца|цу|цом))\s+(?:[A-ZА-Я]\d*|\d+)\b", re.I)
_WORK = re.compile(r"\b(?:в\s+работе|работ[аыу]|work\s+of)\s+([^\W\d_]+)\s*\(?(20\d{2}|19\d{2})\b", re.I)
_CUES = {
    "conductivity": r"\b(?:conductivit\w*|(?:электро)?провод(?:имост|ност)\w*)\b",
    "swelling": r"\b(?:swelling|набухани\w*)\b",
    "impedance": r"\b(?:impedance|EIS|импеданс\w*)\b",
    "gravimetry": r"\b(?:gravimetr\w*|гравиметр\w*|весов\w*)\b",
    "drying": r"\b(?:drying|dried|суш\w*|высуш\w*)\b",
    "soaking": r"\b(?:soak\w*|погру\w*|насыще\w*)\b",
    "preparation": r"\b(?:prepar\w*|подготов\w*|приготов\w*|для\s+получения)\b",
    "negation": r"\b(?:not\b(?!\s+(?:less|more)\s+than)|never|no|не\b(?!\s+(?:менее|более))|нет|без)\b",
    "hypothesis": r"\b(?:might|could|hypothes\w*|propos\w*|предполага\w*|гипотез\w*|возможно)\b",
    "equilibrium": r"\b(?:equilibrium|равновеси\w*)\b",
}
_CRITERION = re.compile(r"неиз[-\s]*менност\w*\s+спектров|unchanged\s+spectra|spectra\s+(?:were\s+)?unchanged", re.I)
_BEFORE = re.compile(r"before\s+(?:conductivity\s+|impedance\s+)?(?:measur\w*|record\w*)|перед\s+измерени\w*", re.I)
_HOLD = re.compile(r"\b(?:held|holding|equilibrat\w*|выдерж\w*)\b", re.I)
_TEMPERATURE = re.compile(r"(?<!\w)\d+(?:[.,]\d+)?\s*(?:°\s*[CСK]|℃)(?!\w)", re.I)


@dataclass(frozen=True)
class SourcePage:
    article_id: str
    page: int
    text_layer: str
    text_layer_id: str
    original_pdf_path: str
    original_pdf_sha256: str
    text: str


@dataclass(frozen=True)
class SourceEvidence:
    citation_id: str
    article_id: str
    chunk_id: str
    text: str
    page_start: int
    page_end: int
    text_layer: str
    author_names: tuple[str, ...] = ()
    year: int | None = None


def _hits(pattern: re.Pattern[str], text: str) -> list[Span]:
    return [Span(m.start(), m.end(), m.group()) for m in pattern.finditer(text)]


def _key(text: str) -> str:
    return re.sub(r"\s+", " ", text.casefold()).strip()


def _sample_key(text: str) -> str:
    return text.split()[-1].casefold()


def requirement(question: str) -> dict[str, object]:
    if not question.strip():
        raise ValueError("Question must be nonempty")
    duration = audit_duration(question, ["placeholder"])
    kind = ("duration" if duration.requirement_spans else "equilibrium_criterion" if
            re.search(r"критери\w*|по\s+какому\s+признаку|\bcriteri(?:on|a)\b", question, re.I) else "outside_scope")
    cues = {name: [asdict(s) for s in _hits(re.compile(pattern, re.I), question)]
            for name, pattern in _CUES.items() if name in {"conductivity", "swelling", "impedance", "gravimetry"}}
    stages = [name for name in ("drying", "soaking", "preparation") if re.search(_CUES[name], question, re.I)]
    if _BEFORE.search(question):
        stages.append("measurement_dwell")
    work = [{"surname": m[1], "year": int(m[2]), "span": asdict(Span(m.start(), m.end(), m.group()))}
            for m in _WORK.finditer(question)]
    return {"kind": kind, "question": question, "quantity_spans": [asdict(s) for s in duration.requirement_spans],
            "sample_spans": [asdict(s) for s in _hits(_SAMPLE, question)], "work_constraints": work,
            "context_cues": cues, "requested_stage_cues": stages,
            "temperature_spans": [asdict(s) for s in _hits(_TEMPERATURE, question)],
            "unparsed_requirements": (["comparison_or_additional_requirements_unparsed"] if re.search(
                r"\b(?:compare|сравн\w*|амплитуд\w*|amplitude|диапазон\w*|frequency\s+range)\b", question, re.I) else []),
            "interpretation": "finite_grammar_proposal_not_complete_query_parse"}


def _statements(text: str) -> list[Span]:
    # Decimal dots are retained; clauses and paragraphs never silently pool times.
    boundaries = list(re.finditer(r"(?<!\d)[.!?;](?:\s+|$)|\n\s*\n", text))
    result, start = [], 0
    for m in boundaries:
        if text[start:m.end()].strip():
            result.append(Span(start, m.end(), text[start:m.end()]))
        start = m.end()
    if text[start:].strip():
        result.append(Span(start, len(text), text[start:]))
    return result


def events(text: str) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for statement in _statements(text):
        raw = statement.text
        values = [("duration", s) for s in duration_spans(raw)] + [("equilibrium_criterion", s) for s in _hits(_CRITERION, raw)]
        for kind, span in values:
            cues = [name for name, pattern in _CUES.items() if re.search(pattern, raw, re.I)]
            stages = [s for s in ("drying", "soaking", "preparation") if s in cues]
            if _BEFORE.search(raw) and _HOLD.search(raw):
                stages.append("measurement_dwell")
            # Whole-statement co-occurrence remains unverified, even in a positive template.
            result.append({"kind": kind, "value": asdict(Span(statement.start + span.start, statement.start + span.end, span.text)),
                           "statement": asdict(statement), "cues": cues, "stage_cues": stages,
                           "bound_or_approximation_cue": bool(re.search(
                               r"не\s+(?:менее|более)|not\s+(?:less|more)\s+than|at\s+least|about|approximately|около|примерно",
                               raw, re.I)),
                           "sample_spans": [asdict(Span(statement.start + s.start, statement.start + s.end, s.text))
                                            for s in _hits(_SAMPLE, raw)],
                           "temperature_spans": [asdict(Span(statement.start + s.start, statement.start + s.end, s.text))
                                                 for s in _hits(_TEMPERATURE, raw)],
                           "relation": "same_statement_candidate_not_entailment"})
    return result


def _page_anchors(e: SourceEvidence, statement: str, pages: Sequence[SourcePage]) -> list[dict[str, object]]:
    anchors = []
    for p in pages:
        if p.article_id != e.article_id or p.text_layer != e.text_layer or not e.page_start <= p.page <= e.page_end:
            continue
        # Permit exact leading/trailing whitespace removal only; no text repair.
        quote = statement.strip()
        for match in re.finditer(re.escape(quote), p.text):
            anchors.append({"article_id": p.article_id, "page": p.page, "text_layer": p.text_layer,
                            "text_layer_id": p.text_layer_id, "start": match.start(), "end": match.end(), "text": quote,
                            "original_pdf_path": p.original_pdf_path, "original_pdf_sha256": p.original_pdf_sha256})
    return anchors


def audit_links(question: str, claims: Sequence[tuple[str, Sequence[str]]], evidence: Sequence[SourceEvidence],
                pages: Sequence[SourcePage]) -> dict[str, object]:
    """Propose requirement/event/source links; no changes to claims or runtime status."""
    req = requirement(question)
    by_id = {e.citation_id: e for e in evidence}
    if len(by_id) != len(evidence) or any(not e.citation_id.strip() for e in evidence):
        raise ValueError("Evidence IDs must be unique and nonempty")
    if any(not e.article_id or not e.chunk_id or not e.text_layer or not 1 <= e.page_start <= e.page_end for e in evidence):
        raise ValueError("Evidence requires article/chunk/layer and valid page range")
    if any(p.page < 1 or not p.article_id or not p.text_layer or not p.text_layer_id or not p.original_pdf_path
           or not re.fullmatch(r"[0-9a-f]{64}", p.original_pdf_sha256) for p in pages):
        raise ValueError("Source pages require page/layer/PDF identities")
    # JSON-shaped outputs; casts below only describe locally constructed structures.
    requirement_data = cast(dict[str, Any], req)
    candidates: list[dict[str, Any]] = []
    for e in evidence:
        for event_raw in events(e.text):
            event = cast(dict[str, Any], event_raw)
            reasons = list(requirement_data["unparsed_requirements"])
            if event["kind"] != req["kind"]:
                reasons.append("different_requested_quantity")
            if "negation" in event["cues"]:
                reasons.append("negation_cue_unresolved")
            if "hypothesis" in event["cues"]:
                reasons.append("hypothesis_cue_unresolved")
            if event["kind"] == "duration" and event["bound_or_approximation_cue"]:
                reasons.append("bounded_or_approximate_duration_unresolved")
            if event["kind"] == "duration" and re.search(r"\d\s*[-–—]\s*\d", event["value"]["text"]):
                reasons.append("duration_range_unresolved")
            stages = event["stage_cues"]
            wanted = requirement_data["requested_stage_cues"]
            if len(stages) > 1:
                reasons.append("mixed_stage_cues_unresolved")
            elif wanted and stages and not set(wanted).intersection(stages):
                reasons.append("competing_stage_cue")
            elif wanted and not stages:
                reasons.append("requested_stage_link_unresolved")
            samples = {_sample_key(s["text"]) for s in event["sample_spans"]}
            target_samples = {_sample_key(s["text"]) for s in requirement_data["sample_spans"]}
            if len(samples) > 1:
                reasons.append("mixed_sample_labels_unresolved")
            elif target_samples and samples and not target_samples.intersection(samples):
                reasons.append("competing_sample_label")
            elif target_samples and not samples:
                reasons.append("requested_sample_link_unresolved")
            works = requirement_data["work_constraints"]
            if len(works) > 1:
                reasons.append("multiple_work_constraints_unresolved")
            elif works:
                work = works[0]
                if e.year is None or not e.author_names:
                    reasons.append("article_metadata_missing")
                elif e.year != work["year"] or not any(re.search(
                        r"(?<!\w)" + re.escape(name.split()[-1]) + r"(?:а|у|ым|е)?(?!\w)", work["surname"], re.I)
                        for name in e.author_names if name.split()):
                    reasons.append("article_metadata_constraint_mismatch")
            for cue, hits in requirement_data["context_cues"].items():
                if hits and cue not in event["cues"]:
                    reasons.append("requested_" + cue + "_link_unresolved")
            temperatures = {_key(s["text"]) for s in event["temperature_spans"]}
            wanted_t = {_key(s["text"]) for s in requirement_data["temperature_spans"]}
            if wanted_t and not wanted_t.intersection(temperatures):
                reasons.append("requested_temperature_link_unresolved")
            anchors = _page_anchors(e, event["statement"]["text"], pages)
            if len(anchors) != 1:
                reasons.append("unique_exact_page_anchor_unresolved")
            candidates.append({"citation_id": e.citation_id, "article_id": e.article_id, "chunk_id": e.chunk_id,
                               **event, "page_anchors": anchors, "diagnostics": reasons,
                               "state": "unresolved" if reasons else "local_context_link_proposal_unverified",
                               "metadata_identity": "recorded_metadata_only_not_independent_bibliographic_confirmation"})
    eligible = [c for c in candidates if c["kind"] == "duration" and not c["diagnostics"]]
    if len({_key(c["value"]["text"]) for c in eligible}) > 1:
        for c in eligible:
            c["diagnostics"].append("multiple_distinct_duration_candidates_unresolved")
            c["state"] = "unresolved"
    claim_rows = []
    for index, (text, cited_ids) in enumerate(claims):
        if not text.strip() or not cited_ids or any(cid not in by_id for cid in cited_ids):
            raise ValueError("Claims require text and known citation IDs")
        matching: list[dict[str, Any]] = []
        for ce_raw in events(text):
            ce = cast(dict[str, Any], ce_raw)
            claim_diagnostics = []
            if ce["kind"] != req["kind"]:
                claim_diagnostics.append("different_requested_quantity")
            for marker in ("negation", "hypothesis"):
                if marker in ce["cues"]:
                    claim_diagnostics.append(marker + "_cue_unresolved")
            target_samples = {_sample_key(s["text"]) for s in requirement_data["sample_spans"]}
            samples = {_sample_key(s["text"]) for s in ce["sample_spans"]}
            if len(samples) > 1:
                claim_diagnostics.append("mixed_sample_labels_unresolved")
            elif target_samples and samples and not target_samples.intersection(samples):
                claim_diagnostics.append("competing_sample_label")
            elif target_samples and not samples:
                claim_diagnostics.append("requested_sample_link_unresolved")
            if len(ce["stage_cues"]) > 1:
                claim_diagnostics.append("mixed_stage_cues_unresolved")
            elif requirement_data["requested_stage_cues"] and ce["stage_cues"] and not set(
                    requirement_data["requested_stage_cues"]).intersection(ce["stage_cues"]):
                claim_diagnostics.append("competing_stage_cue")
            elif requirement_data["requested_stage_cues"] and not ce["stage_cues"]:
                claim_diagnostics.append("requested_stage_link_unresolved")
            for cue, hits in requirement_data["context_cues"].items():
                if hits and cue not in ce["cues"]:
                    claim_diagnostics.append("requested_" + cue + "_link_unresolved")
            wanted_t = {_key(s["text"]) for s in requirement_data["temperature_spans"]}
            if wanted_t and not wanted_t.intersection(_key(s["text"]) for s in ce["temperature_spans"]):
                claim_diagnostics.append("requested_temperature_link_unresolved")
            if ce["kind"] == "duration" and ce["bound_or_approximation_cue"]:
                claim_diagnostics.append("bounded_or_approximate_duration_unresolved")
            links = [i for i, se in enumerate(candidates) if se["citation_id"] in cited_ids and se["kind"] == ce["kind"]
                     and (ce["kind"] == "equilibrium_criterion" or _key(se["value"]["text"]) == _key(ce["value"]["text"]))]
            matching.append({"event": ce, "source_candidate_indices": links,
                             "diagnostics": claim_diagnostics,
                             "state": "literal_value_or_criterion_candidates_unverified" if links else "no_literal_source_candidate"})
        claim_rows.append({"claim_index": index, "text": text, "citation_ids": list(cited_ids), "events": matching,
                           "requested_kind_expressed": any(ev["event"]["kind"] == req["kind"] for ev in matching),
                           "context_identity_in_claim": "not_established"})
    return {"version": VERSION, "requirement": req, "source_candidates": candidates, "claims": claim_rows,
            "scientific_coverage": "not_evaluated", "runtime_action": "none_offline_only",
            "limitations": ["finite_grammar", "same_statement_is_not_entailment", "metadata_not_independently_validated",
                            "no_cross_sentence_coreference", "no_unit_conversion", "no_unknown_condition_validation",
                            "claim_context_identity_not_established", "no_corpus_absence_proof"]}
