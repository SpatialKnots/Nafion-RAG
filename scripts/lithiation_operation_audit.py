"""Finite operation/status/target sidecar; no scientific confirmation or gate override.

Only raw text enters audit(). Exact source offsets survive recognition-only
dehyphenation. Local templates propose candidates; implicit subjects, references,
shared conditions and mixed actions stay unresolved. No value is propagated.
"""

from __future__ import annotations

import re
from typing import Any

from scripts.event_value_ownership_audit import View, recognition_view

VERSION = "lithiation_operation_audit_v0.1"
NOUN = r"(?:литировани[еяю]|литированием|литировании|lithiation)"
VERB = r"(?:литировали|литировал[ао]?|lithiated)"
OPERATION = re.compile(r"(?<!\w)(?:" + NOUN + "|" + VERB + r")(?!\w)", re.I)
TARGET = r"Nafion(?:\s*[-‑–]\s*\d+)?"
MATERIAL = (r"(?:(?:мембран\w*|membranes?|(?:водно[-‑–]спиртов\w*\s+)?дисперси\w*|"
            r"dispersion\s+of)\s+)?" + TARGET + r"(?:\s+membranes?)?")
TARGET_LINKS = {
    "noun_object_ru": NOUN + r"\s+" + MATERIAL,
    "noun_object_en": r"lithiation\s+of\s+(?:the\s+)?" + MATERIAL,
    "verb_object_ru": r"литировали\s+" + MATERIAL,
    "subject_verb": MATERIAL + r"\s+(?:(?:was|were)\s+)?" + VERB,
}
POSITIVE = re.compile(
    r"(?:проводили|выполняли|осуществляли)\s+" + NOUN + "|"
    + NOUN + r"(?:\s+\w+){0,4}\s+(?:проводили|выполняли|осуществляли)|"
    + r"для\s+" + NOUN + r"(?:\s+\w+){0,4}\s+использовали|"
    + r"литировали|(?:was|were)\s+lithiated|"
    + r"lithiation(?:\s+of\s+(?:the\s+)?" + MATERIAL + r")?\s+was\s+(?:performed|carried\s+out)", re.I,
)
NEGATIVE = re.compile(
    r"\bне\s+(?:проводили|выполняли|осуществляли|литировали)\b|"
    r"\b(?:was|were)\s+not\s+(?:lithiated|performed|carried\s+out)\b|\bno\s+lithiation\b", re.I,
)
FUTURE = re.compile(r"\b(?:will|planned|plan\w*|будут|планиру\w*|предстоит)\b|в\s+будущем", re.I)
UNCERTAIN = re.compile(
    r"\b(?:if|unless|could|would|might|may|whether|hypothesi\w*|если|возможно|вероятно|мог\w*|"
    r"неизвестно|предполага\w*|бы)\b|не\s+установлено|not\s+known", re.I,
)
REFERENCE = re.compile(
    r"\b(?:similarly|respectively|both|same|аналогич\w*|соответственно|обе|оба)\b|"
    r"как\s+описано|as\s+described|те[хм]\s+же", re.I,
)
OTHER_ACTION = re.compile(
    r"\b(?:протонировал\w*|очищал\w*|сушил\w*|промывал\w*|хранил\w*|"
    r"протонировани\w*|очистк\w*|сушк\w*|хранени\w*|"
    r"cleaned|protonated|dried|rinsed|washed|stored|cleaning|protonation|drying|rinsing|storage)\b", re.I,
)
FIELD_NEGATION = re.compile(r"\bне\s+(?:использовал\w*|применял\w*)|\bnot\s+us(?:ed|ing)\b", re.I)
ABBREVIATION = re.compile(r"\b(?:мас|ос|ч|wt|vol|fig|eq|рис|табл|см)\.\s*$", re.I)
NUMBER = r"\d+(?:[.,]\d+)?(?:\s*[-–—]\s*\d+(?:[.,]\d+)?)?"
FIELDS = {
    "reagent": r"(?<!\w)(?:LiOH(?:[·⋅]H[2₂]O)?|гидроксид\w*\s+лити\w*|lithium\s+hydroxide)(?!\w)",
    "concentration": r"(?<!\w)" + NUMBER + r"\s*(?-i:[MМ])(?!\w)",
    "duration": r"(?<!\w)" + NUMBER + r"\s*(?:мин(?:ут\w*)?|ч(?:ас\w*)?|сут(?:ок)?|"
                r"minutes?|hours?|days?|weeks?)(?!\w)",
    "temperature": r"(?<!\w)" + NUMBER + r"\s*°\s*[CС](?!\w)",
}
LIGATURES = {"ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff", "ﬃ": "ffi", "ﬄ": "ffl"}


def _view(text: str) -> View:
    base = recognition_view(text)
    pieces, positions = [], []
    for char, position in zip(base.text, base.positions, strict=True):
        expanded = LIGATURES.get(char, char)
        pieces.append(expanded)
        positions.extend([position] * len(expanded))
    return View("".join(pieces), tuple(positions), text)


def _regions(text: str) -> list[tuple[int, int]]:
    """Finite punctuation/sequence boundaries, preserving decimal values."""
    boundaries = [0]
    for match in re.finditer(r"\.(?!\d)(?:\s+|$)|[!?;](?:\s+|$)|\n\s*\n|\b(?:затем|then|subsequently)\b", text, re.I):
        if match.group().lstrip().startswith(".") and ABBREVIATION.search(text[:match.end()]):
            continue
        boundaries.append(match.end() if not match.group()[0].isalpha() else match.start())
    boundaries.append(len(text))
    points = sorted(set(boundaries))
    return [(a, b) for a, b in zip(points, points[1:], strict=False) if text[a:b].strip()]


def audit(text: str) -> dict[str, Any]:
    if not isinstance(text, str):
        raise TypeError("Source text must be a string")
    view = _view(text)
    operations: list[dict[str, Any]] = []
    for start, end in _regions(view.text):
        region_text = view.text[start:end]
        operation_matches = list(OPERATION.finditer(region_text))
        if not operation_matches:
            continue

        def anchors(pattern: re.Pattern[str], offset: int = start, fragment: str = region_text) -> list[dict[str, Any]]:
            return [view.anchor(offset + m.start(), offset + m.end()) for m in pattern.finditer(fragment)]

        status_cues = {name: anchors(pattern) for name, pattern in
                      (("positive", POSITIVE), ("negative", NEGATIVE), ("future", FUTURE), ("uncertain", UNCERTAIN))}
        if status_cues["uncertain"]:
            status = "conditional_or_uncertain_cue"
        elif status_cues["future"]:
            status = "future_cue"
        elif status_cues["negative"]:
            status = "explicit_nonperformance_cue"
        elif status_cues["positive"]:
            status = "affirmative_action_cue_unverified"
        else:
            status = "status_unresolved"
        links = [{"template": name, **anchor} for name, pattern in TARGET_LINKS.items()
                 for anchor in anchors(re.compile(r"(?<!\w)(?:" + pattern + r")(?!\w)", re.I))]
        for link in links:
            link["form_cue"] = ("dispersion" if re.search(r"дисперси|dispersion", link["text"], re.I) else
                                "membrane" if re.search(r"мембран|membrane", link["text"], re.I) else "not_explicit")
        diagnostics = []
        if len(operation_matches) != 1:
            diagnostics.append("multiple_lithiation_mentions_unresolved")
        if OTHER_ACTION.search(region_text):
            diagnostics.append("multiple_operation_kinds_unresolved")
        if REFERENCE.search(region_text):
            diagnostics.append("reference_or_shared_scope_unresolved")
        if FIELD_NEGATION.search(region_text):
            diagnostics.append("reagent_use_negation_unresolved")
        if "?" in region_text:
            diagnostics.append("interrogative_statement_unresolved")
        if not links:
            diagnostics.append("explicit_local_nafion_attachment_not_found")
        if status != "affirmative_action_cue_unverified":
            diagnostics.append("performed_statement_not_established")
        state = "local_target_action_candidate_unverified" if not diagnostics else "blocked_or_unresolved"
        field_rows = [{"field": name, "span": anchor,
                       "relation": "same_region_unverified" if not diagnostics else "region_scope_unresolved",
                       "owner_established": False}
                      for name, pattern in FIELDS.items() for anchor in anchors(re.compile(pattern, re.I))]
        operations.append({"region": view.anchor(start, end),
                           "operation_spans": anchors(OPERATION), "status": status, "status_cues": status_cues,
                           "target_links": links, "state": state, "diagnostics": diagnostics, "fields": field_rows,
                           "performed_established": False, "material_owner_established": False})
    collected = {(field["field"], field["span"]["start"], field["span"]["end"])
                 for row in operations for field in row["fields"]}
    unassigned = []
    for name, pattern in FIELDS.items():
        for match in re.finditer(pattern, view.text, re.I):
            span = view.anchor(match.start(), match.end())
            if (name, span["start"], span["end"]) not in collected:
                unassigned.append({"field": name, "span": span, "owner_established": False,
                                   "relation": "no_recognized_lithiation_region"})
    return {"version": VERSION, "operations": operations, "unassigned_fields": unassigned, "source_modified": False,
            "method_catalogue_completeness": "not_established", "runtime_admission": False,
            "scientific_acceptance": "not_evaluated", "uses_reference_labels": False,
            "limitations": ["finite_ru_en_templates", "no_coreference_or_section_subject_inheritance",
                            "no_cross_region_value_propagation", "same_region_is_not_ownership_proof",
                            "affirmative_cue_is_not_confirmation", "not_a_lithiation_method_catalogue"]}
