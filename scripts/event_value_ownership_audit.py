"""Finite source-region ownership diagnostics, never scientific/runtime admission.

Rules consume raw source and exact selected spans only: no expected labels, case
IDs, question matching or model kind is used to establish a source region.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from scripts.event_spans_v02 import validate_catalog, validate_reply
from scripts.experiment_sentence_links import statement_units
from scripts.gigachat_event_proposal import _DURATION

VERSION = "event_value_ownership_audit_v0.1"
_JOIN = re.compile(r"(?<=[^\W\d_])[-\u00ad][^\S\n]*\r?\n\s*(?=[^\W\d_])|\u00ad")
_OPERATIONS = {
    "cleaning": r"\b(?:очищал\w*|очистк\w*|(?:was|were)\s+cleaned|cleaning)\b",
    "rinsing": r"\b(?:промыв\w*|rinsed|rinsing|washed|washing)\b",
    "protonation": r"\b(?:протонирован\w*|protonated|protonation)\b",
    "drying": r"\b(?:сушил\w*|высушив\w*|(?:was|were)\s+dried|drying)\b",
    "storage": r"\b(?:оставлял\w*|хранил\w*|stored|storage)\b",
    "degassing": r"\b(?:дегазаци\w*|дегазир\w*|degassed|degassing)\b",
    "mixing": r"\b(?:перемешив\w*|mixed|mixing|stirred|stirring)\b",
    "waiting": r"\b(?:выдерживал\w*|выдержива\w*|термостатир\w*|held|equilibrated|equilibrating)\b",
    "measurement": r"\b(?:измерял\w*|измерен\w*|регистрировал\w*|записывал\w*|measured|recorded)\b",
    "analysis": r"\b(?:анализировал\w*|определял\w*|analyzed|analysed|determined)\b",
    "cooling": r"\b(?:охлаждени\w*|охлаждал\w*|cooled|cooling)\b",
}
_SEQUENCE = re.compile(r"\b(?:затем|далее|потом|с\s+последующ\w*|then|subsequently|afterwards)\b", re.I)
_AND = re.compile(r"\b(?:и|and)\s*$", re.I)
_ABBREVIATION_END = re.compile(r"\b(?:мас|ос|wt|vol|fig|eq|no|табл|рис)\.\s*$", re.I)
_SHARED = re.compile(
    r"\b(?:same|identical|both|respectively|similarly|each|оба|обе|соответственно|аналогич\w*|одинаков\w*)\b|"
    r"при\s+тех\s+же|так\s*же|как\s+(?:выше|описано)|as\s+(?:above|described)|see\s+above", re.I)
_MODAL = re.compile(
    r"\b(?:if|unless|would|could|never|not|except|если|мог\w*|возможно|вероятно|без)\b|"
    r"\bне\s+(?!(?:менее|более|меньше|больше)\b)", re.I)
_CUES = {
    "at_least": r"(?:не\s+менее|at\s+least|not\s+less\s+than)",
    "at_most": r"(?:не\s+более|at\s+most|no\s+more\s+than|up\s+to)",
    "approximate": r"(?:около|приблизительно|about|approximately|~|≈)",
    "strict_bound_unmodeled": r"(?:более|менее|more\s+than|less\s+than)",
}


@dataclass(frozen=True)
class View:
    text: str
    positions: tuple[int, ...]
    raw: str

    def anchor(self, start: int, end: int) -> dict[str, Any]:
        if not 0 <= start < end <= len(self.positions):
            raise ValueError("Invalid normalized-view span")
        a, b = self.positions[start], self.positions[end - 1] + 1
        return {"start": a, "end": b, "text": self.raw[a:b]}


def recognition_view(text: str) -> View:
    """A mapped sidecar only; stored/raw source is never rewritten."""
    removed = {i for match in _JOIN.finditer(text) for i in range(match.start(), match.end())}
    positions = tuple(i for i in range(len(text)) if i not in removed)
    return View("".join(text[i] for i in positions), positions, text)


def source_regions(text: str) -> list[dict[str, Any]]:
    view = recognition_view(text)
    recognized = sorted([
        {"kind": kind, **view.anchor(m.start(), m.end())}
        for kind, pattern in _OPERATIONS.items() for m in re.finditer(pattern, view.text, re.I)
    ], key=lambda a: (a["start"], a["end"]))
    regions: list[dict[str, Any]] = []
    units = statement_units(text)
    for unit_index, unit in enumerate(units):
        anchors = [a for a in recognized if unit.start <= a["start"] and a["end"] <= unit.end]
        # Generic hold language within a typed step is not a second assigned step.
        primary = [a for a in anchors if a["kind"] != "waiting"] or anchors
        cuts = [unit.start]
        coordination_unresolved = False
        for a, b in zip(primary, primary[1:], strict=False):
            between = text[a["end"]:b["start"]]
            sequence = list(_SEQUENCE.finditer(between))
            if sequence:
                cuts.append(a["end"] + sequence[-1].start())
            else:
                conjunction = _AND.search(between)
                if conjunction:
                    cut = a["end"] + conjunction.start()
                    before = recognition_view(text[cuts[-1]:cut]).text
                    after = recognition_view(text[b["end"]:unit.end]).text
                    if _DURATION.search(before) and _DURATION.search(after):
                        cuts.append(cut)
                    else:
                        coordination_unresolved = True
        cuts.append(unit.end)
        for start, end in zip(cuts, cuts[1:], strict=False):
            ops = [a for a in primary if start <= a["start"] and a["end"] <= end]
            raw = text[start:end]
            normalized = recognition_view(raw).text
            diagnostics = []
            if not ops:
                diagnostics.append("operation_lexeme_not_recognized")
            elif len(ops) != 1:
                diagnostics.append("multiple_operation_lexemes_unresolved")
            if coordination_unresolved:
                diagnostics.append("coordinated_scope_unresolved")
            if _ABBREVIATION_END.search(unit.text) or (unit_index and _ABBREVIATION_END.search(units[unit_index - 1].text)):
                diagnostics.append("abbreviation_statement_boundary_unresolved")
            if _SHARED.search(normalized):
                diagnostics.append("shared_or_referential_scope_unresolved")
            if _MODAL.search(normalized):
                diagnostics.append("negated_or_modal_scope_unresolved")
            regions.append({"id": len(regions), "start": start, "end": end, "text": raw,
                            "operation_anchors": ops, "diagnostics": diagnostics,
                            "recognition": "single_explicit_lexeme" if len(ops) == 1 and not diagnostics else "unresolved"})
    return regions


def duration_relation_audit(text: str, span: dict[str, Any], declared: str) -> dict[str, Any]:
    view = recognition_view(text)
    atoms = []
    for match in _DURATION.finditer(view.text):
        anchor = view.anchor(match.start(), match.end())
        if span["start"] <= anchor["start"] and anchor["end"] <= span["end"]:
            atoms.append((match, anchor))
    result: dict[str, Any] = {"declared_relation": declared, "state": "duration_expression_unresolved",
                              "diagnostics": [], "source_atoms": [anchor for _, anchor in atoms], "cue": None}
    if len(atoms) != 1:
        return result
    match, atom = atoms[0]
    prefix = view.text[:match.start()]
    observed = "range" if re.search(r"\d\s*[-–—]\s*\d", match["value"]) else None
    for relation, pattern in _CUES.items():
        cue = re.search(r"(?<!\w)" + pattern + r"\s*$", prefix, re.I)
        if cue:
            observed = relation
            result["cue"] = view.anchor(cue.start(), cue.end())
            if result["cue"]["start"] < span["start"]:
                result["diagnostics"].append("explicit_cue_outside_selected_span")
            break
    result["observed_lexical_relation"] = observed or "numeric_expression_without_recognized_bound"
    if observed == "strict_bound_unmodeled":
        result["state"] = "strict_bound_unmodeled_unresolved"
    elif declared == "unresolved":
        result["state"] = "declared_unresolved"
    elif observed and declared != observed:
        result["state"] = "declared_relation_differs_from_explicit_cue"
    elif not observed and declared != "exact":
        result["state"] = "declared_relation_cue_not_found_in_finite_scope"
    else:
        result["state"] = "no_lexical_relation_conflict_unverified"
    # Neither a bare number nor agreement with a cue proves the requested exact duration.
    return result


def audit(source: dict[str, Any], restored: dict[str, Any]) -> dict[str, Any]:
    validate_catalog(source)
    if validate_reply(restored["raw_selection"], source) != restored:
        raise ValueError("Restored proposal drift")
    text = source["exact_text"]
    regions = source_regions(text)

    def containing(span: dict[str, Any]) -> list[dict[str, Any]]:
        return [r for r in regions if r["start"] <= span["start"] and span["end"] <= r["end"]]

    rows = []
    for event in restored["events"]:
        op = event["operation"]
        op_regions = containing(op)
        recognized_op = len(op_regions) == 1 and op_regions[0]["recognition"] == "single_explicit_lexeme" and any(
            op["start"] < a["end"] and a["start"] < op["end"] for a in op_regions[0]["operation_anchors"])
        for field in ("duration", "conditions"):
            selected = event["fields"][field]
            if not selected["spans"]:
                rows.append({"event_id": event["id"], "field": field, "selection_status": selected["status"],
                             "state": "no_selected_value_not_evaluated", "operation": op, "value": None,
                             "operation_region_ids": [r["id"] for r in op_regions], "value_region_ids": [],
                             "owner_established": False, "duration_relation": None})
            for span in selected["spans"]:
                value_regions = containing(span)
                if not recognized_op:
                    state = "selected_operation_or_scope_unresolved"
                elif len(value_regions) != 1 or value_regions[0]["recognition"] != "single_explicit_lexeme":
                    state = "selected_value_or_scope_unresolved"
                elif op_regions[0]["id"] == value_regions[0]["id"]:
                    state = "same_local_region_unverified"
                else:
                    lo = min(op_regions[0]["start"], value_regions[0]["start"])
                    hi = max(op_regions[0]["end"], value_regions[0]["end"])
                    bridge = recognition_view(text[lo:hi]).text
                    state = "cross_region_reference_unresolved" if _SHARED.search(bridge) or _MODAL.search(bridge) else (
                        "different_explicit_operation_regions")
                rows.append({"event_id": event["id"], "field": field, "selection_status": selected["status"], "state": state,
                             "operation": op, "value": span, "operation_region_ids": [r["id"] for r in op_regions],
                             "value_region_ids": [r["id"] for r in value_regions], "owner_established": False,
                             "duration_relation": duration_relation_audit(
                                 text, span, selected["relation"]) if field == "duration" else None})
    return {"version": VERSION, "regions": regions, "selections": rows, "source_text_modified": False,
            "proposal_modified": False, "uses_reference_annotations": False, "scientific_acceptance": "not_evaluated",
            "runtime_action": "none_offline_only", "limits": ["finite_ru_en_lexemes_and_sequence_markers",
                "source_region_diagnostics_not_semantic_ownership_proof", "no_coreference_or_shared_value_resolution",
                "no_sample_method_or_question_coverage_validation", "no_runtime_gate_or_value_repair"]}
