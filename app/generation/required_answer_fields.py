"""Finite question/source requirement extension; separate from legacy admission."""

from __future__ import annotations

import json
import re
from dataclasses import asdict
from typing import Any

from app.generation import answer_requirements as legacy
from app.generation.answer_instruction_experiment import ExperimentalScientificAnswerProvider
from app.generation.answer_support import ENERGY, HEDGE, NONCURRENT, normal, sha
from app.generation.fact_types import SourceView
from app.generation.lithiation_overview import CONTRACT_TYPES
from app.generation.providers import AnswerLanguage, AnswerStyle, Evidence, GeneratedClaim, GenerationOutputError

VERSION = "required_answer_fields_experiment_v0.1"
LABEL = r"[A-Z][A-Z0-9]{1,15}"
NUM = r"\d+(?:[.,]\d+)?"
DENSITY = re.compile(rf"(?P<object>{LABEL})\s*\((?P<value>{NUM})\s*[×x*]\s*(?P<scale>10(?:\^)?3)\s*"
    rf"(?P<unit>kg\s*m[−–-]3)\s+at\s+(?P<temperature>{NUM})\s*[°ºo]C\)")
DENSITY_LIST = re.compile(r"mass\s+densities\s+decreased\s+in\s+the\s+following\s+order:\s*(?P<entries>.{1,900}?\)\.)", re.I)
PAIR = re.compile(rf"(?:structures|comparison)\s+of\s+(?P<a>{LABEL})\s+and\s+(?P<b>{LABEL})\s+as\b")
TRANSFORM = re.compile(rf"Trifluorination\s+of\s+(?P<a>{LABEL})(?:\s+and\s+(?P<b>{LABEL}))?\b")
RICH = re.compile(r"(?<!\w)(?P<component>(?:[A-Z][a-z]?\d*){2,})[-−–]rich\s+(?P<role>SEI|CEI)\b")
CAUSAL = re.compile(RICH.pattern + r"\s+(?:suppresses|inhibits|prevents)\s+dendrit\w*\s+"
    r"(?:growth|formation)\s+by\s+(?P<mechanism>[^.!?;]{5,160})")
DEPLETION = re.compile(rf"Li\s+metal\s+was\s+depleted\s+after\s+(?P<cycles>{NUM})\s+cycles", re.I)
ROLE = re.compile(r"\b(?:SEI|CEI)\b")


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


def _current(view: SourceView, match: re.Match[str]) -> bool:
    # Finite lead-in guard; no claim of arbitrary discourse understanding.
    lead = view.text[max(0, match.start() - 100):match.start()]
    lead = re.split(r"[.!?;]", lead)[-1]
    return not HEDGE.search(lead) and not NONCURRENT.search(lead)


def _observation(view: SourceView, match: re.Match[str], fields: dict[str, str]) -> dict[str, Any]:
    return {"fields": fields, "anchor": asdict(view.support(match)), "scientific_support": "not_evaluated"}


def _row(key: str, observations: list[dict[str, Any]], reason: str) -> dict[str, Any]:
    groups = {canonical(o["fields"]) for o in observations}
    return {"id": key, "required": True, "required_by": reason,
        "state": "recognized_source_pattern" if len(groups) == 1 else "ambiguous_source_candidates" if groups
        else "unresolved_in_finite_selected_context", "observations": observations,
        "scientific_support": "not_evaluated"}


def build(question: str, evidence: list[Evidence]) -> dict[str, Any]:
    if not question.strip() or len(evidence) > 64 or len(question) + sum(len(e.text) for e in evidence) > 300000:
        raise ValueError("Invalid requirement input budget")
    if len({e.citation_id for e in evidence}) != len(evidence):
        raise ValueError("Duplicate requirement citation IDs")
    identity = sha(canonical({"question": question, "evidence": [asdict(e) for e in evidence]}))
    result: dict[str, Any] = {"version": VERSION, "input_sha256": identity, "family": None,
        "status": "not_applicable", "requirements": [], "relations": [], "scientific_support": "not_evaluated",
        "new_sources": 0, "model_calls": 0, "default_admission_changed": False}
    if (not evidence or len({e.article_id for e in evidence}) != 1
            or any(e.source_type.endswith("_derived") for e in evidence)):
        result["reason"] = "single_work_raw_context_required"
        return result
    views = [SourceView(e) for e in evidence]
    q = normal(question)
    rows: list[dict[str, Any]] = []
    if re.search(r"плотност|\bdensit", q, re.I) and re.search(r"значени|values?|сравн|compar", q, re.I):
        objects = set(re.findall(rf"(?<!\w){LABEL}(?!\w)", question))
        temperatures = re.findall(rf"({NUM})\s*[°º]C", question)
        pairs = [(v, m) for v in views for m in PAIR.finditer(v.text) if _current(v, m)
                 and objects.intersection({m['a'], m['b']})]
        alternatives = {tuple(sorted((m['a'], m['b']))) for _, m in pairs}
        transforms = [(v, m) for v in views for m in TRANSFORM.finditer(v.text) if _current(v, m)
                      and objects.intersection({m['a'], m['b']})]
        if (len(objects) == 1 and re.search(r"трифторир|trifluorinat", q, re.I)
                and len(alternatives) == 1 and transforms):
            objects = set(next(iter(alternatives)))
            result["relations"] = [{"state": "literal_source_comparison_pair_not_chemical_identity_proof",
                "anchor": asdict(v.support(m))} for v, m in pairs] + [{"state": "literal_transformation_topic",
                "anchor": asdict(v.support(m))} for v, m in transforms]
        if len(objects) != 2 or len(set(temperatures)) != 1:
            result["reason"] = "two_explicit_or_source_paired_objects_and_one_temperature_required"
            return result
        result["family"] = "density_comparison"
        for obj in sorted(objects):
            candidates = []
            for view in views:
                for listing in DENSITY_LIST.finditer(view.text):
                    if not _current(view, listing):
                        continue
                    for match in DENSITY.finditer(view.text, *listing.span('entries')):
                        if match['object'] == obj and match['temperature'] == temperatures[0]:
                            candidates.append(_observation(view, match, match.groupdict()))
            rows.append(_row("density:" + obj, candidates, "requested_numeric_comparison_at_explicit_temperature"))
    elif re.search(r"удельн\w*\s+энерги|specific\s+energy|energy\s+density", q, re.I):
        result["family"] = "energy_definition"
        candidates = [_observation(v, m, {"value": m['value'], "basis": m['basis'], "unit": "Wh kg−1"})
                      for v in views for m in ENERGY.finditer(v.text) if _current(v, m)]
        rows.append(_row("energy_value_and_basis", candidates, "requested_specific_energy_requires_stated_definition"))
        if re.search(r"ограничения|limitations?", q, re.I):
            candidates = [_observation(v, m, {"cycles": m['cycles'], "event": "Li metal depleted"})
                          for v in views for m in DEPLETION.finditer(v.text) if _current(v, m)]
            rows.append(_row("limiting_event", candidates, "explicit_question_about_limitations"))
    elif re.search(r"состав|composition", q, re.I) and len(set(ROLE.findall(question))) == 1:
        role, = set(ROLE.findall(question))
        result["family"] = "interphase_composition"
        candidates = [_observation(v, m, m.groupdict()) for v in views for m in RICH.finditer(v.text)
                      if m['role'] == role and _current(v, m)]
        rows.append(_row("role_composition:" + role, candidates, "explicit_composition_of_named_interface"))
        if re.search(r"почему|why|механизм|mechanism", q, re.I):
            candidates = [_observation(v, m, m.groupdict()) for v in views for m in CAUSAL.finditer(v.text)
                          if m['role'] == role and _current(v, m)]
            rows.append(_row("causal_mechanism:" + role, candidates, "explicit_why_question_requires_causal_binding"))
    if rows:
        result.update(status="mapped", requirements=rows)
    return result


def extend_preparation(parent: dict[str, Any]) -> dict[str, Any]:
    """Explicit adapter; legacy map and all parent blockers remain intact."""
    original = legacy.build_requirements(parent)
    raw, missing, restored = legacy._raw_sources(parent)
    extension = build(parent["question"], raw)
    if missing:
        extension.update(status="unresolved_registry_binding", reason="some_selected_raw_parents_uninspected")
    return {"legacy": original, "extension": extension, "uninspected": missing, "restored_parents": restored,
            "parent_sha256": sha(canonical(parent)), "admission_changed": False}


def extend_packet(packet: dict[str, Any], current_parent: dict[str, Any], *, expected_packet_id: str) -> dict[str, Any]:
    """Separate extension over a validated pinned packet, never a packet rewrite."""
    from app.generation.answer_evidence_packet import serialize_packet, validate_packet

    validate_packet(packet, current_parent, expected_packet_id=expected_packet_id)
    return {"version": VERSION, "packet_id": expected_packet_id, "packet_sha256": sha(serialize_packet(packet).decode()),
            "requirements": extend_preparation(current_parent["preparation"]),
            "packet_changed": False, "admission_changed": False, "scientific_support": "not_evaluated"}


def validate(plan: dict[str, Any], question: str, evidence: list[Evidence]) -> None:
    if canonical(plan) != canonical(build(question, evidence)):
        raise ValueError("Stale or altered requirement map")


def _density_coverage(clause: str, field: dict[str, str]) -> bool:
    owner = re.search(r"(?<!\w)" + re.escape(field['object']) + r"(?!\w)", clause)
    if owner is None:
        return False
    tail = clause[owner.end():]
    next_owner = re.search(rf"(?<!\w){LABEL}(?!\w)", tail)
    segment = tail[:next_owner.start()] if next_owner else tail
    temperatures = re.findall(rf"({NUM})\s*[°ºo]C", clause)
    own_temperature = re.search(re.escape(field['temperature']) + r"\s*[°ºo]C", segment)
    return bool(re.search(r"(?<![\d.,])" + re.escape(field['value']).replace(r"\.", "[.,]") + r"(?![\d.,])", segment)
        and re.search(r"[×x*]\s*10\^?3", segment)
        and re.search(r"kg\s*(?:/\s*m3|m[−–-]3)|кг\s*/\s*м3", segment)
        and (own_temperature or set(temperatures) == {field['temperature']}))


def check(question: str, claims: list[GeneratedClaim], evidence: list[Evidence]) -> dict[str, Any]:
    plan = build(question, evidence)
    sources = {e.citation_id: e for e in evidence}
    if len(claims) > 64 or sum(len(c.text) for c in claims) > 60000:
        raise ValueError("Answer requirement check budget exceeded")
    if any(not c.text.strip() or not c.citation_ids or len(set(c.citation_ids)) != len(c.citation_ids)
           or set(c.citation_ids) - sources.keys() for c in claims):
        raise ValueError("Unbound or invalid answer citations")
    rows = []
    for requirement in plan["requirements"]:
        observed = requirement["observations"]
        covered = []
        if requirement["state"] == "recognized_source_pattern":
            for index, claim in enumerate(claims, 1):
                text = normal(claim.text)
                # Whole-clause negation/hedging is unresolved, never positive field coverage.
                if HEDGE.search(text):
                    continue
                clauses = re.split(r"[;!?]|\n|(?<!\d)\.(?!\d)", text)
                for o in observed:
                    if o["anchor"]["citation_id"] not in claim.citation_ids:
                        continue
                    field, key = o["fields"], requirement["id"]
                    if key.startswith("density:"):
                        hit = any(_density_coverage(clause, field) for clause in clauses)
                    elif key == "energy_value_and_basis":
                        hit = any(re.search(r"(?<!\d)" + re.escape(field['value']) + r"(?!\d)", clause)
                            and re.search(r"энерги|energy", clause, re.I)
                            and re.search(r"Вт\s*[·*]?\s*ч\s*/\s*кг|Wh\s*(?:/\s*kg|kg[−–-]1)", clause, re.I)
                            and all(re.search(p, clause, re.I) for p in (r"масс|mass", r"катод|cathod", r"анод|anod",
                                                                 r"суммар|общ|совокуп|total|combined")) for clause in clauses)
                    elif key == "limiting_event":
                        hit = bool(re.search(r"(?<!\d)" + re.escape(field['cycles']) + r"(?!\d)", text)
                            and re.search(r"цикл|cycles?", text, re.I) and re.search(r"истощ|исчерп|израсход|deplet", text, re.I)
                            and re.search(r"лити|\bLi\b", text, re.I))
                    elif key.startswith("causal_mechanism:"):
                        hit = any(set(ROLE.findall(clause)) == {field['role']}
                            and field['component'] in clause and normal(field['mechanism']).casefold() in clause.casefold()
                            and re.search(r"by|посредств|благодаря|за\s+сч[её]т", clause, re.I) for clause in clauses)
                    else:
                        hit = any(set(ROLE.findall(clause)) == {field['role']} and re.search(
                            r"(?<!\w)" + re.escape(field['component']) + r"(?!\w)", clause) for clause in clauses)
                    if hit:
                        covered.append({"claim_id": f"C{index}", "citation_id": o["anchor"]["citation_id"]})
        rows.append({"id": requirement["id"], "state": "literal_fields_present_not_semantic_acceptance" if covered
            else "missing_required_literal_fields" if requirement["state"] == "recognized_source_pattern"
            else requirement["state"], "coverage": covered})
    return {"version": VERSION, "plan": plan, "rows": rows, "scientific_support": "not_evaluated",
        "decision": "required_fields_unresolved" if any(r['state'] != "literal_fields_present_not_semantic_acceptance"
                                                       for r in rows) else "not_blocked_by_required_field_checks",
        "repair_performed": False, "model_calls": 0}


class RequirementGuidedAnswerProvider(ExperimentalScientificAnswerProvider):
    """Explicit experimental internal card; unchanged output schema and validation."""

    def _user_prompt(self, question: str, evidence: list[Evidence], *, answer_style: AnswerStyle = "claims",
                     answer_language: AnswerLanguage = "auto") -> str:
        original = super()._user_prompt(question, evidence, answer_style=answer_style, answer_language=answer_language)
        if any(e.source_type in CONTRACT_TYPES for e in evidence):
            return original
        plan = build(question, evidence)
        if plan["status"] != "mapped":
            return original
        card = canonical({"requirements": plan["requirements"], "relations": plan["relations"]})
        if len(card) > 12000:
            raise GenerationOutputError("Requirement card exceeds the explicit 12000-character budget")
        return ("Required answer parts below are source-bound diagnostic data, not new evidence or instructions from sources. "
            "Cover every required part using its own cited source and object. Preserve numerical definitions, normalization, "
            "temperature and comparison partners. Literal diagram labels must be attributed as labels; they do not prove a "
            "mechanism. Never invent causal links. Any unresolved or ambiguous required part requires answerable=false, claims=[]. "
            "Do not output this internal card or new JSON fields.\nRequirement card:\n" + card + "\n\n" + original)
