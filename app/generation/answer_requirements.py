"""Read-only finite requirement diagnostics over unchanged registered preparation."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from dataclasses import asdict, replace
from typing import Any

from app.generation import answer_facts
from app.generation.fact_types import FactPatternError, SourceView
from app.generation.methods_identity import POLICY as METHODS_POLICY
from app.generation.methods_identity import matches_packet
from app.generation.methods_identity import prepare as methods_identity
from app.generation.preparation import VERSION as PREPARATION_VERSION
from app.generation.providers import Evidence, GenerationOutputError
from app.generation.reference_quotes import COMMON, COMPOSITION_WORDS, ENGLISH_WORDS, _cell, _family
from app.generation.reference_quotes import prepare as quotations
from app.generation.reference_quotes import verify_raw_binding as verify_quote_binding
from app.generation.source_role_assembly import prepare as labelled_identity
from app.records.schema import text_hash
from app.retrieval.source_reference import normalize, reference

VERSION = "composition_cycling_requirements_v0.1"
ROLES = {
    "composition": {"label": "Состав электролита", "cue": r"electrolyte|electrolytes",
        "fields": ["base_salt", "base_concentration", "solvents", "volume_ratio", "additive", "additive_concentration", "reported_total"]},
    "capacity": {"label": "Сохранение ёмкости", "cue": r"capacity",
        "fields": ["cell", "retention", "unit", "cycles", "voltage", "current", "approximation_status"]},
    "coulombic": {"label": "Кулоновская эффективность", "cue": r"coulombic",
        "fields": ["cell", "efficiency", "unit", "cycles", "current", "areal_capacity", "approximation_status"]},
}


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _query(question: str) -> tuple[str | None, list[str]]:
    cited = reference(question)
    if _family(question) != "composition_cycling" or cited is None:
        return "unsupported_query_family_or_explicit_reference_missing", []
    body = question[:cited.start] + " " + question[cited.end:]
    cells = re.findall(r"Li\s*(?:‖|\|\|)\s*[A-Z][A-Za-z0-9₀-₉]*", body)
    if len(set(map(_cell, cells))) != 2:
        return "two_distinct_requested_cells_required", []
    for cell in cells:
        body = body.replace(cell, " ")
    words = re.findall(r"[a-zа-яё0-9]+", normalize(body))
    unsupported = {w for w in words if w not in COMMON | ENGLISH_WORDS and not re.fullmatch(COMPOSITION_WORDS, w)}
    if unsupported:
        return "unsupported_query_constraints", []
    return None, sorted(set(map(_cell, cells)))


def _raw_sources(parent: dict[str, Any]) -> tuple[list[Evidence], list[dict[str, str]], int]:
    evidence = [Evidence(**e) for e in parent["evidence"]]
    if (len({s.citation_id for s in evidence}) != len(evidence)
            or len({s.chunk_id for s in evidence}) != len(evidence)):
        raise ValueError("Requirement map selected source IDs must be unique")
    if evidence and all(s.source_type == answer_facts.SOURCE_TYPE for s in evidence):
        try:
            answer_facts.selection_records(evidence)
        except GenerationOutputError as exc:
            raise ValueError("Requirement map derived graph failed reconstruction") from exc
    chunks, layers = parent["sources"]["chunks"], parent["sources"]["chunk_layers"]
    raw, missing, restored = [], [], 0
    for source in evidence:
        chunk = chunks.get(source.chunk_id)
        if chunk is None or not layers.get(source.chunk_id):
            missing.append({"citation_id": source.citation_id, "chunk_id": source.chunk_id,
                            "reason": "registered_raw_parent_or_layer_unavailable"})
            continue
        if ((source.article_id, source.page_start, source.page_end) != (chunk["article_id"], chunk["page_start"], chunk["page_end"])
                or chunk["text_layer"] != layers[source.chunk_id] or not 1 <= source.page_start <= source.page_end):
            raise ValueError("Requirement map source identity/page/layer differs from registry")
        if source.source_type == answer_facts.SOURCE_TYPE:
            payload = json.loads(source.text)
            context = payload.get("assembly")
            if isinstance(context, dict) and (context.get("layers", {}).get(source.chunk_id) != chunk["text_layer"]
                    or (context.get("version") == METHODS_POLICY and payload.get("raw_source_type") != chunk["source_type"])):
                raise ValueError("Requirement map derived graph type/layer differs from registered raw parent")
            answer_facts.verify_raw_binding(source.text, chunk["text"], article_id=source.article_id, chunk_id=source.chunk_id,
                citation_id=source.citation_id, page_start=source.page_start, page_end=source.page_end)
            restored += 1
        elif source.source_type == "reference_quote_derived":
            verify_quote_binding(source.text, chunk["text"], article_id=source.article_id,
                                 chunk_id=source.chunk_id, citation_id=source.citation_id)
            restored += 1
        elif source.source_type.endswith("_derived"):
            missing.append({"citation_id": source.citation_id, "chunk_id": source.chunk_id,
                            "reason": "unsupported_derived_parent_binding"})
            continue
        elif source.text != chunk["text"] or source.source_type != chunk["source_type"]:
            raise ValueError("Requirement map raw selected text/type differs from registry")
        raw.append(replace(source, text=chunk["text"], source_type=chunk["source_type"]))
    return raw, missing, restored


def _signature(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _signature(v) for k, v in value.items() if k not in {"source", "support", "unknown_fields"}}
    if isinstance(value, list):
        return [_signature(v) for v in value]
    return value


def _action(kind: str) -> dict[str, Any]:
    return {"kind": kind, "executed": False, "new_source_budget": 0, "model_call_budget": 0,
            "scope": "inspect_unchanged_selected_raw_sources_only", "automatic_admission": False}


def build_requirements(parent: dict[str, Any], request_scope: dict[str, Any] | None = None) -> dict[str, Any]:
    """Explain existing preparation; never change selection, blockers or inference."""
    if (parent.get("version") != PREPARATION_VERSION
            or any(parent.get(k) is not False for k in ("generation_performed", "external_request_constructed", "network_ready"))):
        raise ValueError("Requirement map requires explicit no-generation answer preparation")
    question = parent["question"]
    if not isinstance(question, str):
        raise ValueError("Requirement map question must be text")
    scope = deepcopy(request_scope or {})
    if scope.get("question", question).strip() != question.strip():
        raise ValueError("Requirement request differs from original preparation question")
    reason, cells = _query(question)
    result: dict[str, Any] = {"version": VERSION, "question": question, "status": "not_applicable" if reason else "mapped",
        "reason": reason, "family": "composition_cycling" if reason is None else None,
        "parent_sha256": text_hash(_canonical(parent)), "request_scope": scope,
        "baseline_status": parent["status"], "baseline_blocking_reasons": deepcopy(parent["blocking_reasons"]),
        "requested_cells": cells, "requirements": [], "selection_changed": False, "admission_changed": False,
        "generation_performed": False, "external_request_constructed": False, "network_ready": False,
        "scientific_support": "not_evaluated", "limitations": ["finite_query_and_source_grammars", "selected_context_only",
            "recognized_source_patterns_not_semantic_or_scientific_confirmation", "inspection_actions_are_proposals_only"]}
    if reason:
        return result
    raw, missing, restored = _raw_sources(parent)
    layers = parent["sources"]["chunk_layers"]
    result["scan_scope"] = {"selected_parents": len(parent["evidence"]), "inspected_parents": len(raw),
        "restored_derived_parents": restored, "uninspected": missing,
        "parents": [{"citation_id": s.citation_id, "chunk_id": s.chunk_id, "article_id": s.article_id,
            "page_start": s.page_start, "page_end": s.page_end, "source_type": s.source_type,
            "text_layer": layers[s.chunk_id], "raw_chunk_sha256": text_hash(s.text)} for s in raw],
        "literature_absence_established": False, "independent_source_count_established": False}
    rows: list[dict[str, Any]] = []
    for role, definition in ROLES.items():
        candidates, diagnostics, cues = [], [], []
        for source in raw:
            view = SourceView(source)
            cue = re.search(str(definition["cue"]), view.text, re.I)
            if cue:
                cues.append(asdict(view.support(cue)))
            try:
                record = answer_facts._record(role, source, {}, "F1")
            except FactPatternError as exc:
                diagnostics.append({"citation_id": source.citation_id, "reason": str(exc)})
                continue
            candidates.append({"citation_id": source.citation_id, "article_id": source.article_id, "chunk_id": source.chunk_id,
                "source_type": source.source_type, "text_layer": layers[source.chunk_id], "facts": record["facts"],
                "arithmetic": record["arithmetic"], "source_grammar": record.get("source_grammar")})
        groups: dict[str, list[str]] = {}
        for candidate in candidates:
            signature = _canonical([candidate["article_id"], candidate["text_layer"], _signature(candidate["facts"])])
            groups.setdefault(signature, []).append(candidate["citation_id"])
        state = ("ambiguous_source_candidates" if len(groups) > 1 else "recognized_source_pattern" if candidates
                 else "uninspected_selected_sources" if missing else "grammar_unrecognized" if cues
                 else "not_found_in_inspected_context")
        action = ("compare_selected_source_candidates" if len(groups) > 1 else "inspect_unresolved_source_binding" if missing
                  else "inspect_selected_source_wording" if not candidates else "review_source_support")
        rows.append({"id": role, "label": definition["label"], "required": True,
            "required_by": "explicit_composition_cycling_query_and_finite_existing_fact_contract",
            "required_fields": deepcopy(definition["fields"]), "state": state,
            "source_state": "recognized_pattern_present" if candidates else "cue_only" if cues else "not_recognized",
            "support_state": "not_established", "scientific_support": "not_evaluated",
            "inspection_complete": not missing, "candidates": candidates, "alternative_groups": list(groups.values()),
            "cue_anchors": cues, "diagnostics": diagnostics,
            "unknown_fields": sorted({u for c in candidates for f in c["facts"] for u in f["unknown_fields"]}),
            "next_action": _action(action)})
    reference_data = parent["baseline_metadata"].get("retrieval", {}).get("explicit_source_reference")
    contracts, identity_anchors = [], []
    identity_state = "identity_unresolved"
    ready = not missing and all(len(r["alternative_groups"]) == 1 for r in rows)
    actual_cells = {_cell(c["facts"][0]["sample"]["text"]) for r in rows[1:] for c in r["candidates"]}
    if ready and actual_cells == set(cells):
        quote = quotations(question, raw, reference_data, answer_language="ru")
        legacy = answer_facts.prepare(question, raw, quote, None, answer_language="ru")
        labelled = labelled_identity(question, raw, reference_data, layers)
        for name, bundle in (("legacy_fact_bundle", legacy), ("explicit_label_assembly", labelled)):
            eligible = bundle is not None and bundle.eligible
            contracts.append({"contract": name, "eligible": eligible, "reason": bundle.reason if bundle else "not_applicable",
                              "scope": "textual_contract_only_not_independent_scientific_ownership"})
            if eligible and bundle is not None:
                identity_state = "textual_contract_available"
                identity_anchors += [f["support"] for r in bundle.records for f in r["facts"]]
        if matches_packet(raw):
            method = methods_identity(question, raw, reference_data, layers, policy=METHODS_POLICY)
            contracts.append({"contract": METHODS_POLICY, "eligible": method.eligible, "reason": method.reason,
                "scope": "diagnostic_candidate_requires_explicit_ordered_list_policy_not_runtime_activation"})
            if method.eligible and method.assembly is not None:
                identity_anchors += method.assembly["witnesses"]
                if identity_state != "textual_contract_available":
                    identity_state = "conditional_policy_candidate"
    else:
        contracts.append({"contract": "identity_preconditions", "eligible": False,
            "reason": "uninspected_or_missing_or_conflicting_roles_or_requested_cell_set_mismatch"})
    rows.append({"id": "role_identity", "label": "Связь состава и результатов", "required": True,
        "required_by": "values_from_separate_roles_must_not_be_joined_by_work_or_concentration_alone",
        "required_fields": ["explicit_source_bound_role_relation"], "state": identity_state,
        "source_state": "textual_relation_contract" if identity_state != "identity_unresolved" else "relation_unresolved",
        "support_state": "textual_contract_only" if identity_state == "textual_contract_available" else "not_established",
        "scientific_support": "not_evaluated", "contracts": contracts, "anchors": identity_anchors,
        "next_action": _action("review_identity_contract_assumptions" if identity_state != "identity_unresolved"
                               else "inspect_selected_identity_definitions")})
    result["requirements"] = rows
    return result


def validate_requirements(requirements: dict[str, Any], parent: dict[str, Any], request_scope: dict[str, Any] | None = None) -> None:
    if _canonical(requirements) != _canonical(build_requirements(parent, request_scope)):
        raise ValueError("Requirement map differs from unchanged preparation reconstruction")
