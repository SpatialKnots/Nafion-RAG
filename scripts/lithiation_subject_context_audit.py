"""Explicit heading/figure subject-link proposals; frozen operation audit unchanged.

Raw text only, no case IDs, questions or reference labels. A link is a bounded
proposal, never a performed experiment, material/value owner or runtime permit.
"""

from __future__ import annotations

import re
from typing import Any

from scripts import lithiation_operation_audit as base

VERSION = "lithiation_subject_context_v0.1"
NAFION = re.compile(r"(?<!\w)(?:(?:Li|H)[-‑–])?Nafion(?:\s*[-‑–]\s*\d+)?(?!\w)", re.I)
HEADING = re.compile(r"(?m)^[^\S\n]*(?P<number>\d+(?:\.\d+)+)\.?[ \t]+(?P<title>[^\n]+)")
CAPTION = re.compile(r"(?m)^[^\S\n]*(?:Рисунок|Figure|Fig\.)[ \t]+(?P<number>\d+(?:\.\d+)*)[ \t]*[—–:-][^\n]*", re.I)
FIGURE_REF = re.compile(
    r"(?<!\w)(?:рисунок|рис\.|figure|fig\.)\s*(?P<number>\d+(?:\.\d+)*)\s*(?P<label>[a-zа-я])?(?![\w.])", re.I,
)
SUBLABEL = re.compile(r"\((?P<label>[a-zа-я])\)", re.I)
KNOWN_OTHER = re.compile(r"(?<!\w)(?:PBI|PVDF|PTFE|Aquivion|MF[-‑]?4SK|полиэтилен\w*|полистирол\w*|polyethylene|polystyrene)(?!\w)", re.I)
OTHER_SCOPE = re.compile(
    r"\b(?:друг\w*\s+(?:материал\w*|мембран\w*|полимер\w*)|(?:another|different)\s+(?:material|membrane|polymer))\b|"
    r"(?:мембран\w*|полимер\w*|material|membranes?|polymer)\s+(?!(?:Nafion|Li[-‑]Nafion|H[-‑]Nafion)\b)"
    r"(?-i:[A-ZА-ЯЁ])[\w-]*", re.I,
)
ANALOGUE = re.compile(r"Nafion\s*[-‑]\s*(?:like|подоб\w*)|аналог\w*\s+Nafion|Nafion\s*[/+]", re.I)
STEP_CHANGE = re.compile(r"\b(?:друг\w*\s+этап\w*|(?:another|different)\s+step)\b", re.I)
SEQUENCE_STEP = re.compile(
    r"\b(?:затем|далее|then|subsequently)\b|на\s+(?:первом|втором|третьем|следующем)\s+этапе", re.I,
)
FORMS = {"membrane": re.compile(r"\b(?:мембран\w*|membranes?)\b", re.I),
         "dispersion": re.compile(r"\b(?:дисперси\w*|dispersion\w*)\b", re.I)}
GENERIC_OBJECT = {"ионным", "проводили", "выполняли", "осуществляли", "мембран", "мембраны", "образцов", "образца",
                  "was", "were", "by", "with", "in", "at", "for", "в", "при", "с", "на", "раствором"}


def _forms(text: str) -> list[str]:
    return [name for name, pattern in FORMS.items() if pattern.search(text)]


def _material_conflicts(text: str) -> list[str]:
    result = []
    if KNOWN_OTHER.search(text) or OTHER_SCOPE.search(text):
        result.append("other_material_or_scope_cue")
    if ANALOGUE.search(text):
        result.append("nafion_analogue_or_composite_scope")
    return result


def _operation_object_conflicts(text: str) -> list[str]:
    result = []
    for match in re.finditer(base.NOUN + r"\s+(?P<object>[\w-]+)", text, re.I):
        token = match["object"].casefold()
        if token not in GENERIC_OBJECT and not NAFION.fullmatch(match["object"]):
            result.append("explicit_lithiation_object_not_resolved_as_section_target")
    for match in re.finditer(r"(?:мембран[аыуе]?|дисперсии|membranes?|dispersion\s+of)\s+(?P<object>[\w-]+)", text, re.I):
        token = match["object"].casefold()
        if token not in GENERIC_OBJECT and not NAFION.fullmatch(match["object"]):
            result.append("explicit_material_object_not_resolved_as_section_target")
    return result


def _structures(text: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    view = base._view(text)
    headings: list[dict[str, Any]] = [{"number": m["number"], "span": view.anchor(m.start(), m.end()),
                 "target_spans": [view.anchor(m.start("title") + n.start(), m.start("title") + n.end())
                                  for n in NAFION.finditer(m["title"])],
                 "form_cues": _forms(m["title"]), "diagnostics": _material_conflicts(m["title"])}
                for m in HEADING.finditer(view.text)]
    for heading in headings:
        title = heading["span"]["text"]
        if base.NEGATIVE.search(title) or base.FUTURE.search(title) or base.UNCERTAIN.search(title):
            heading["diagnostics"].append("heading_status_scope_unresolved")
    captions: list[dict[str, Any]] = []
    for match in CAPTION.finditer(view.text):
        tail = re.search(r"\n\s*\n", view.text[match.end():])
        end = match.end() + tail.start() if tail else len(view.text)
        raw = view.text[match.start():end]
        separator, first_label = raw.find(":"), SUBLABEL.search(raw)
        previous = separator + 1 if first_label and 0 <= separator < first_label.start() else 0
        parts = []
        for label in SUBLABEL.finditer(raw):
            parts.append({"label": label["label"].casefold(),
                          "span": view.anchor(match.start() + previous, match.start() + label.end()),
                          "parent_prefix_excluded": previous > 0,
                          "form_cues": _forms(raw[previous:label.end()])})
            previous = label.end()
        captions.append({"number": match["number"], "span": view.anchor(match.start(), end), "parts": parts,
                         "target_spans": [view.anchor(match.start() + n.start(), match.start() + n.end())
                                          for n in NAFION.finditer(raw)],
                         "form_cues": _forms(raw),
                         "diagnostics": _material_conflicts(raw) + _operation_object_conflicts(raw)})
    return headings, captions


def audit(text: str) -> dict[str, Any]:
    baseline = base.audit(text)
    headings, captions = _structures(text)
    attempts = []
    for index, operation in enumerate(baseline["operations"]):
        region = operation["region"]
        if operation["state"] == "local_target_action_candidate_unverified":
            attempts.append({"operation_index": index, "state": "local_target_already_present", "links": [],
                             "performed_established": False, "material_owner_established": False})
            continue
        prior = [heading for heading in headings if heading["span"]["end"] <= region["start"]]
        heading = prior[-1] if prior else None
        following = [h["span"]["start"] for h in headings if h["span"]["start"] > region["start"]]
        section_end = following[0] if following else len(text)
        common = [d for d in operation["diagnostics"] if d != "explicit_local_nafion_attachment_not_found"]
        common += _material_conflicts(region["text"]) + _operation_object_conflicts(region["text"])
        if STEP_CHANGE.search(region["text"]):
            common.append("explicit_other_step_cue")
        if any(h["span"]["start"] <= span["start"] < span["end"] <= h["span"]["end"]
               for h in headings for span in operation["operation_spans"]):
            common.append("operation_inside_heading_not_execution")
        links = []
        heading_diagnostics = list(common)
        if heading is None:
            heading_diagnostics.append("no_prior_numbered_heading")
        else:
            bridge = text[heading["span"]["end"]:region["start"]]
            heading_diagnostics += heading["diagnostics"] + _material_conflicts(bridge) + _operation_object_conflicts(bridge)
            if not heading["target_spans"]:
                heading_diagnostics.append("nearest_heading_has_no_explicit_nafion")
            if len(heading["form_cues"]) != 1:
                heading_diagnostics.append("heading_material_form_unresolved")
            if set(_forms(bridge + region["text"])) - set(heading["form_cues"]):
                heading_diagnostics.append("material_form_change_or_mixed_scope")
            if STEP_CHANGE.search(bridge):
                heading_diagnostics.append("explicit_other_step_cue")
            if SEQUENCE_STEP.search(bridge + region["text"]):
                heading_diagnostics.append("step_transition_requires_explicit_reference")
        links.append({"kind": "nearest_numbered_heading", "state": "context_subject_candidate_unverified"
                      if not heading_diagnostics else "blocked_or_unresolved", "diagnostics": sorted(set(heading_diagnostics)),
                      "subject_heading": heading, "operation_span": region, "section_end": section_end,
                      "bridge_span": {"start": heading["span"]["end"], "end": region["start"],
                                      "text": text[heading["span"]["end"]:region["start"]]} if heading else None})
        for ref in FIGURE_REF.finditer(region["text"]):
            diagnostics = list(common)
            matched = [caption for caption in captions if caption["number"] == ref["number"]
                       and caption["span"]["end"] <= region["start"]]
            caption = matched[0] if len(matched) == 1 else None
            if caption is None:
                diagnostics.append("figure_caption_not_unique_or_missing")
            part = None
            if caption:
                diagnostics += caption["diagnostics"]
                parts = [p for p in caption["parts"] if p["label"] == (ref["label"] or "").casefold()]
                part = parts[0] if len(parts) == 1 else None
                if part is None:
                    diagnostics.append("explicit_unique_subpanel_not_found")
                if not caption["target_spans"]:
                    diagnostics.append("caption_parent_has_no_explicit_nafion")
                if heading and caption["span"]["start"] < heading["span"]["end"]:
                    diagnostics.append("section_boundary_between_caption_and_operation")
                bridge = text[caption["span"]["end"]:region["start"]]
                diagnostics += _material_conflicts(bridge) + _operation_object_conflicts(bridge)
                if STEP_CHANGE.search(bridge):
                    diagnostics.append("explicit_other_step_cue")
                if part:
                    diagnostics += _operation_object_conflicts(part["span"]["text"])
                    if not part["parent_prefix_excluded"]:
                        diagnostics.append("caption_parent_subpanel_boundary_unresolved")
                    if not base.OPERATION.search(part["span"]["text"]):
                        diagnostics.append("referenced_subpanel_is_not_lithiation")
                    if len(part["form_cues"]) != 1:
                        diagnostics.append("subpanel_material_form_unresolved")
                    if set(_forms(bridge + region["text"])) - set(part["form_cues"]):
                        diagnostics.append("material_form_change_or_mixed_scope")
                    if base.NEGATIVE.search(part["span"]["text"]) or base.FUTURE.search(part["span"]["text"]):
                        diagnostics.append("subpanel_nonperformance_or_future_cue")
            links.append({"kind": "explicit_figure_subpanel_reference", "state": "context_subject_candidate_unverified"
                          if not diagnostics else "blocked_or_unresolved", "diagnostics": sorted(set(diagnostics)),
                          "reference_span": {"start": region["start"] + ref.start(), "end": region["start"] + ref.end(),
                                             "text": ref.group()}, "caption": caption, "subpanel": part,
                          "operation_span": region})
        candidates = [link for link in links if link["state"] == "context_subject_candidate_unverified"]
        attempts.append({"operation_index": index, "state": "context_subject_candidate_unverified" if candidates
                         else "blocked_or_unresolved", "links": links,
                         "performed_established": False, "material_owner_established": False})
    return {"version": VERSION, "baseline": baseline, "headings": headings, "captions": captions,
            "attempts": attempts, "baseline_modified": False, "values_or_conditions_propagated": False,
            "runtime_admission": False, "scientific_acceptance": "not_evaluated",
            "method_catalogue_completeness": "not_established", "uses_reference_labels": False,
            "limitations": ["finite_numbered_single_line_headings", "finite_explicit_figure_subpanel_references",
                            "no_general_coreference", "finite_material_conflict_cues_not_entity_recognition",
                            "context_candidate_is_not_owner_or_execution_proof"]}
