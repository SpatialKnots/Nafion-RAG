"""Offline finite Methods identity candidate; no runtime admission or source writes."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict
from decimal import Decimal
from typing import Any

from app.generation.fact_recipes import capacity, composition, coulombic
from app.generation.fact_types import NUMBER, FactPatternError, SourceView
from app.generation.providers import Evidence
from app.generation.source_paraphrases import PREFIX_GUARD

VERSION = "methods_identity_bridge_audit_v0.1"
CODE = r"[A-Z][A-Za-z0-9.-]+"
MIXTURE = r"[A-Za-z0-9/ ()-]+?"
RATIO = r"\d+:\d+(?::\d+)?"
LIST_DECIMAL = r"(?<![\w.,+−–-])\d+(?:\.\d+)?"
BASES = (
    rf"The electrolytes were prepared by dissolving (?P<base>{NUMBER}) (?P<unit>M) (?P<salt>Li[A-Za-z0-9]+) in "
    rf"(?P<mix1>{MIXTURE}) \((?P<ratio1>{RATIO}) by volume\), (?P<mix2>{MIXTURE}) "
    rf"\((?P<ratio2>{RATIO}) by volume\), and (?P<mix3>{MIXTURE}) \((?P<ratio3>{RATIO}) by volume\) "
    rf"solvents to obtain (?P<code1>{CODE}), (?P<code2>{CODE}), and (?P<code3>{CODE}), "
    r"three electrolytes with the same concentration, respectively\."
)
ADDITIONS = (
    rf"In addition, (?P<dose1>{LIST_DECIMAL}), (?P<dose2>{LIST_DECIMAL}), and (?P<dose3>{LIST_DECIMAL}) M "
    rf"(?P<additive>Li[A-Za-z0-9]+) were separately added to (?P<base_code>{CODE}) to obtain "
    rf"(?P<product1>{CODE}), (?P<product2>{CODE}), and (?P<product3>{CODE})\."
)


class BridgeError(ValueError):
    """Finite unsupported/ambiguous source or inconsistent candidate, never scientific absence."""


def raw_code(view: SourceView, match: re.Match[str], group: str) -> str:
    raw = view.value(match, group).source.text
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", raw))


def one(view: SourceView, pattern: str) -> re.Match[str]:
    try:
        match = view.one(pattern)
    except FactPatternError as exc:
        raise BridgeError("unsupported_or_ambiguous_finite_source_pattern") from exc
    prefix = re.split(r"[.!?]\s+", view.text[max(0, match.start() - 160):match.start()])[-1]
    if re.search(PREFIX_GUARD, prefix, re.I):
        raise BridgeError("nonasserted_or_foreign_source_context")
    return match


def inspect(abstract: Evidence, methods: Evidence, conclusion: Evidence, layers: dict[str, str]) -> dict[str, Any]:
    sources = [abstract, methods, conclusion]
    if len({s.article_id for s in sources}) != 1:
        raise BridgeError("different_source_work")
    if len({layers.get(s.chunk_id) for s in sources}) != 1 or any(not layers.get(s.chunk_id) for s in sources):
        raise BridgeError("different_or_missing_text_layer")
    av, mv, cv = (SourceView(s) for s in sources)
    try:
        comp = composition(abstract, {})
        ce = coulombic(conclusion, {})
        abstract_ce = coulombic(abstract, {})
        cap = capacity(abstract, {})
    except FactPatternError as exc:
        raise BridgeError("existing_fact_recipe_unresolved") from exc
    base, addition, total = comp.facts
    if base.value is None or addition.value is None or total.value is None or base.sample is None:
        raise BridgeError("incomplete_source_composition")
    def ce_fields(value: Any) -> dict[str, Any]:
        f = value.facts[0]
        return {"sample": f.sample.text, "value": f.value.text, "unit": f.unit.text,
                "conditions": {k: v.text for k, v in f.conditions.items()}}

    if ce_fields(ce) != ce_fields(abstract_ce):
        raise BridgeError("CE_claims_cell_value_unit_or_conditions_differ")
    section = one(mv, r"\b\d+\.\d+\. Material Preparation\.(?P<body>.{1,4500}?)\b\d+\.\d+\. Material Characterization\.")
    bases, doses = one(mv, BASES), one(mv, ADDITIONS)
    if not (section.start("body") <= bases.start() < bases.end() <= section.end("body")
            and section.start("body") <= doses.start() < doses.end() <= section.end("body")):
        raise BridgeError("definition_outside_material_preparation")
    context = one(cv, r"\b\d+\. CONCLUSION (?P<body>.{1,4500}?)■ASSOCIATED CONTENT")
    target = one(cv, rf"we have designed a functional electrolyte (?P<code>{CODE}),")
    if not context.start("body") <= target.start() < target.end() <= context.end("body"):
        raise BridgeError("target_outside_conclusion")
    ce_span = ce.facts[0].support
    target_raw, context_raw = cv.support(target), cv.support(context)
    if not target_raw.end <= ce_span.start < ce_span.end <= context_raw.end:
        raise BridgeError("CE_outside_target_conclusion")
    aliases = []
    solutes = base.sample.text.split("/")
    expanded = []
    for term in solutes:
        if " " in term:
            alias = one(mv, re.escape(term) + r" \((?P<alias>[A-Z][A-Za-z0-9]+)\)")
            aliases.append(asdict(mv.support(alias)))
            expanded.append(alias["alias"])
        else:
            expanded.append(term)
    additive_name = addition.conditions["salt"].text
    additive_alias = one(av, re.escape(additive_name) + r" \((?P<alias>[A-Z][A-Za-z0-9]+)\)")
    aliases.append(asdict(av.support(additive_alias)))
    codes = [raw_code(mv, bases, f"code{i}") for i in range(1, 4)]
    products = [raw_code(mv, doses, f"product{i}") for i in range(1, 4)]
    target_code, base_code = raw_code(cv, target, "code"), raw_code(mv, doses, "base_code")
    if len(set(codes)) != 3 or len(set(products)) != 3 or products.count(target_code) != 1 or codes.count(base_code) != 1:
        raise BridgeError("code_identity_or_parallel_list_ambiguity")
    product_index, base_index = products.index(target_code) + 1, codes.index(base_code) + 1
    selected_mix = bases[f"mix{base_index}"]
    if (bases["salt"] != base.conditions["salt"].text or Decimal(bases["base"]) != Decimal(base.value.text)
            or selected_mix.split("/") != expanded or bases[f"ratio{base_index}"] != base.conditions["solvent_ratio"].text
            or doses["additive"] != additive_alias["alias"] or Decimal(doses[f"dose{product_index}"]) != Decimal(addition.value.text)
            or Decimal(bases["base"]) + Decimal(doses[f"dose{product_index}"]) != Decimal(total.value.text)):
        raise BridgeError("methods_composition_fields_do_not_match_abstract")
    return {"version": VERSION, "status": "finite_ordered_methods_identity_candidate", "target_code": target_code,
            "base_code": base_code, "base_position": base_index, "product_position": product_index,
            "solvents": expanded, "ratio": bases[f"ratio{base_index}"], "additive_alias": additive_alias["alias"],
            "base_concentration": bases["base"], "additive_concentration": doses[f"dose{product_index}"],
            "reported_total": total.value.text,
            "explicit_assumption": "ordered_parallel_dose_product_lists_not_general_semantic_entailment",
            "bindings": {"composition": comp.data(), "bases": asdict(mv.support(bases)),
                         "additions": asdict(mv.support(doses)), "aliases": aliases,
                         "target": asdict(target_raw), "CE": ce.data(), "abstract_CE": abstract_ce.data(),
                         "capacity": cap.data(), "methods_section": asdict(mv.support(section))},
            "source_types_retained": {s.chunk_id: s.source_type for s in sources},
            "code_normalization": "raw_span_nfkc_whitespace_only_preserve_structural_hyphens",
            "scientific_ownership_verified": False, "values_propagated": False, "production_admission_changed": False}
