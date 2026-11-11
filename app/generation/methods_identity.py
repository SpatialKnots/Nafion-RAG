"""Opt-in, recomputed finite Methods witness graph; no registered source writes."""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import asdict, replace
from decimal import Decimal
from typing import Any

from app.generation import answer_facts as facts
from app.generation.fact_recipes import capacity, composition, coulombic
from app.generation.fact_types import NUMBER, FactPatternError, SourceView
from app.generation.providers import Evidence, GenerationOutputError
from app.generation.reference_quotes import _cell
from app.generation.reference_quotes import prepare as quotations
from app.generation.source_paraphrases import PREFIX_GUARD

POLICY = "ordered_methods_identity_v0.2"
LOCAL_STATUS_GUARD = PREFIX_GUARD + r"|\b(?:another|other|different)\s+(?:electrolyte|cell|system)\b"
ASSUMPTION_TEXT = ("Связь состава с кодом электролита проверена по определениям Methods; "
                   "дозы добавки и коды продуктов сопоставлены по порядку списков. "
                   "Это явное правило системы, а не независимая научная проверка принадлежности. "
                   "Условия и значения между операциями не переносятся.")
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


def _asserted(source: Evidence, start: int) -> None:
    prefix = re.sub(r"\s+", " ", source.text[max(0, start - 220):start])
    prefix = re.split(r"[.!?]\s+", prefix)[-1]
    if re.search(LOCAL_STATUS_GUARD, prefix, re.I):
        raise BridgeError("nonasserted_or_foreign_source_context")


def raw_code(view: SourceView, match: re.Match[str], group: str) -> str:
    raw = view.value(match, group).source.text
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", raw))


def matches_packet(sources: list[Evidence]) -> bool:
    """Select only a three-parent Methods/Conclusion packet for the opt-in contract."""
    return (len(sources) == 3 and any(re.search(r"\d+\.\d+\.\s*Material Preparation\.", s.text) for s in sources)
            and any(re.search(r"\d+\.\s*CONCLUSION\b", s.text) for s in sources))


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
    abstract_region = one(av, r"\bABSTRACT: (?P<body>.{1,4500}?) KEYWORDS:")
    abstract_span = av.support(abstract_region)
    for rendering in (comp, cap, abstract_ce):
        for fact in rendering.facts:
            if not abstract_span.start <= fact.support.start < fact.support.end <= abstract_span.end:
                raise BridgeError("fact_outside_bounded_abstract")
            _asserted(abstract, fact.support.start)
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
    _asserted(methods, mv.support(section).start)
    if re.search(r"\b(?:Figure|Fig\.|Table|References)\s*\d*", section["body"], re.I):
        raise BridgeError("mixed_nonmethods_role_inside_definition_span")
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
    _asserted(conclusion, target_raw.start)
    _asserted(conclusion, ce_span.start)
    if not target_raw.end <= ce_span.start < ce_span.end <= context_raw.end:
        raise BridgeError("CE_outside_target_conclusion")
    if re.search(LOCAL_STATUS_GUARD, conclusion.text[target_raw.end:ce_span.start], re.I):
        raise BridgeError("target_to_CE_relation_unresolved")
    aliases = []
    solutes = base.sample.text.split("/")
    expanded = []
    for term in solutes:
        if " " in term:
            alias = one(mv, re.escape(term) + r" \((?P<alias>[A-Z][A-Za-z0-9]+)\)")
            if not section.start("body") <= alias.start() < alias.end() <= section.end("body"):
                raise BridgeError("alias_outside_material_preparation")
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
    return {"version": POLICY, "status": "finite_ordered_methods_identity_graph", "target_code": target_code,
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
            "scientific_ownership_verified": False, "values_propagated": False}


def prepare(question: str, sources: list[Evidence], reference: Any, layers: dict[str, str | None],
            *, policy: str = "disabled", answer_language: str = "ru") -> facts.Bundle:
    """Only a complete explicit policy graph may replace an incomplete fact bundle."""
    diagnostics: list[dict[str, str]] = []

    def blocked(reason: str) -> facts.Bundle:
        return facts.Bundle(False, reason, "composition_cycling", [], [], [], diagnostics,
                            {"version": POLICY, "reason": reason})

    if policy != POLICY:
        return blocked("methods_identity_policy_not_enabled")
    if answer_language == "en" or (answer_language == "auto" and not re.search(r"[а-яё]", question, re.I)):
        return blocked("methods_identity_russian_answer_required")
    quote = quotations(question, sources, reference, answer_language=answer_language)
    if (quote is None or quote.diagnostics.get("family") != "composition_cycling"
            or quote.reason not in {"missing_bounded_reference_source_roles", "complete_bounded_reference_quotations"}):
        return blocked("methods_identity_reference_or_query_precondition_failed")
    if (len(sources) != 3 or len({s.article_id for s in sources}) != 1
            or len({s.chunk_id for s in sources}) != 3 or len({s.citation_id for s in sources}) != 3
            or any(not 1 <= s.page_start <= s.page_end for s in sources)):
        return blocked("methods_identity_source_scope_unresolved")
    selected_layers = [layers.get(s.chunk_id) for s in sources]
    if any(not isinstance(v, str) or not v for v in selected_layers) or len(set(selected_layers)) != 1:
        return blocked("methods_identity_text_layer_unresolved")
    abstracts = [s for s in sources if s.citation_id in quote.diagnostics["front_matter_author_citation_ids"]
                 and s.source_type == "main_text"]
    methods = [s for s in sources if s.source_type in {"main_text", "formula_block", "figure_caption"}
               and re.search(r"\d+\.\d+\.\s*Material Preparation\.", s.text)]
    conclusions = [s for s in sources if s.source_type == "main_text" and re.search(r"\d+\.\s*CONCLUSION\b", s.text)]
    if (any(len(group) != 1 for group in (abstracts, methods, conclusions))
            or len({s.chunk_id for s in (abstracts + methods + conclusions)}) != 3):
        return blocked("methods_identity_role_scope_unresolved")
    abstract, method, conclusion = abstracts[0], methods[0], conclusions[0]
    ordered = [abstract, method, conclusion]
    try:
        graph = inspect(abstract, method, conclusion, {s.chunk_id: str(layers[s.chunk_id]) for s in ordered})
    except BridgeError as exc:
        return blocked(str(exc))
    records = [facts._record(recipe, source, {}, f"F{i}") for i, (recipe, source) in enumerate(
        (("composition", abstract), ("capacity", abstract), ("coulombic", conclusion)), 1)]
    requested = {_cell(c) for c in re.findall(r"Li\s*(?:‖|\|\|)\s*[A-Z][A-Za-z0-9₀-₉]*", question)}
    actual = {_cell(r["facts"][0]["sample"]["text"]) for r in records[1:]}
    if len(requested) != 2 or requested != actual:
        return blocked("methods_identity_requested_cell_binding_mismatch")
    bindings = graph["bindings"]
    witness_values = [bindings["bases"], bindings["additions"], *bindings["aliases"], bindings["target"],
                      *[f["support"] for role in ("CE", "abstract_CE") for f in bindings[role]["facts"]]]
    witnesses = list({(a["chunk_id"], a["start"], a["end"]): a for a in witness_values}.values())
    assembly = {**graph, "label": graph["target_code"], "question": question, "reference": reference,
                "layers": {s.chunk_id: layers[s.chunk_id] for s in ordered}, "witnesses": witnesses,
                "parents": [{"citation_id": s.citation_id, "article_id": s.article_id, "chunk_id": s.chunk_id,
                    "page_start": s.page_start, "page_end": s.page_end, "source_type": s.source_type} for s in ordered],
                "conditions_propagated": False, "assumption_text": ASSUMPTION_TEXT}
    for record in records:
        record["source_assembly"] = POLICY
        record["allowed_claim"] += " " + ASSUMPTION_TEXT
    derived = [replace(s, source_type=facts.SOURCE_TYPE, text=json.dumps({"version": facts.VERSION,
        "family": "composition_cycling", "language": "ru", "params": {}, "raw_source": s.text,
        "raw_source_type": s.source_type, "raw_chunk_id": s.chunk_id,
        "records": [r for r in records if r["citation_id"] == s.citation_id],
        "assembly": assembly}, ensure_ascii=False)) for s in ordered]
    return facts.Bundle(True, "complete_ordered_methods_identity", "composition_cycling", derived, ordered,
                        records, diagnostics, assembly)


def selection_records(evidence: list[Evidence]) -> dict[str, dict[str, Any]]:
    """Rebuild original source roles and entire graph, including definition-only parents."""
    try:
        payloads = [json.loads(e.text) for e in evidence]
        if not payloads or any(not isinstance(p, dict) for p in payloads):
            raise GenerationOutputError("Invalid Methods identity payload")
        context = payloads[0]["assembly"]
        if (not isinstance(context, dict) or context.get("version") != POLICY
                or not isinstance(context.get("question"), str) or not isinstance(context.get("reference"), dict)
                or not isinstance(context.get("layers"), dict)
                or not all(isinstance(k, str) and isinstance(v, str) for k, v in context["layers"].items())):
            raise GenerationOutputError("Invalid Methods identity context")
        if any(p.get("assembly") != context or e.source_type != facts.SOURCE_TYPE
               or not isinstance(p.get("raw_source"), str) or not isinstance(p.get("raw_source_type"), str)
               for e, p in zip(evidence, payloads, strict=True)):
            raise GenerationOutputError("Incomplete or inconsistent Methods identity graph")
        raw = [replace(e, source_type=p["raw_source_type"], text=p["raw_source"])
               for e, p in zip(evidence, payloads, strict=True)]
        rebuilt = prepare(context["question"], raw, context["reference"], context["layers"], policy=POLICY)
        if not rebuilt.eligible or [json.loads(e.text) for e in rebuilt.evidence] != payloads:
            raise GenerationOutputError("Methods identity graph differs from recomputed raw sources")
    except (KeyError, TypeError, ValueError) as exc:
        raise GenerationOutputError("Invalid Methods identity contract") from exc
    return {r["selection_id"]: r for r in rebuilt.records}


def prompt_graph(context: dict[str, Any]) -> dict[str, Any]:
    return {k: context[k] for k in ("version", "label", "explicit_assumption", "assumption_text", "witnesses", "parents")}
