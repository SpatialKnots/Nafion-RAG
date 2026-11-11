"""Versioned source fact bundles and exact ASCII selection; no database writes."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from typing import Any

from app.generation.answer_fidelity import Contract
from app.generation.fact_recipes import RECIPES
from app.generation.fact_types import FactPatternError
from app.generation.providers import Evidence, GeneratedClaim, GenerationOutputError
from app.generation.reference_quotes import Packet

VERSION = "source_fact_selection_v0.2"
SOURCE_TYPE = "source_fact_derived"
EXPECTED_RECIPES = {
    "composition_cycling": ("composition", "capacity", "coulombic"),
    "preparation_conductivity": ("dispersion_method", "casting", "conductivity_table"),
    "model_layer_bulk_conductivity_conditions": ("oxide_comparison", "oxide_synthesis", "oxide_eis"),
    "plasticiser_cycles_structure_qualifiers": ("thermal_cycles", "hold_interpretation", "crystals", "amorphous"),
}


@dataclass(frozen=True)
class Bundle:
    eligible: bool
    reason: str
    family: str
    evidence: list[Evidence]
    display: list[Evidence]
    records: list[dict[str, Any]]
    diagnostics: list[dict[str, str]]
    assembly: dict[str, Any] | None = None

    def metadata(self) -> dict[str, Any]:
        result = {"version": VERSION, "eligible": self.eligible, "reason": self.reason, "family": self.family,
                "records": self.records, "diagnostics": self.diagnostics,
                "output_policy": "all_ascii_fact_ids_then_recomputed_russian_rendering_or_abstention",
                "scope": "request_local_finite_textual_bindings_not_independent_scientific_confirmation",
                "units_converted": False, "scientific_ownership_verified": False}
        if self.assembly is not None:
            result["assembly"] = self.assembly
        return result


def _record(recipe: str, source: Evidence, params: dict[str, str], selection_id: str) -> dict[str, Any]:
    if recipe not in RECIPES:
        raise FactPatternError("unsupported_fact_recipe")
    rendered = RECIPES[recipe](source, params)
    # JSON round-trip canonicalizes tuples without changing exact source strings.
    data = json.loads(json.dumps(rendered.data(), ensure_ascii=False))
    result = {"selection_id": selection_id, "recipe": recipe, "citation_id": source.citation_id,
            "article_id": source.article_id, "chunk_id": source.chunk_id, "facts": data["facts"],
            "arithmetic": data["arithmetic"], "allowed_claim": data["text"]}
    if rendered.grammar is not None:
        result["source_grammar"] = {"version": rendered.grammar}
    return result


def prepare(question: str, sources: list[Evidence], quotation: Packet | None, fidelity: Contract | None,
            *, answer_language: str = "auto") -> Bundle | None:
    family = quotation.diagnostics["family"] if quotation is not None else fidelity.family if fidelity is not None else None
    if family is None:
        return None
    diagnostics: list[dict[str, str]] = []

    def incomplete(reason: str) -> Bundle:
        return Bundle(False, reason, family, [], [], [], diagnostics)

    if answer_language == "en" or (answer_language == "auto" and not re.search(r"[а-яё]", question, re.I)):
        return incomplete("russian_fact_renderer_not_requested")
    assignments: list[tuple[str, list[Evidence]]] = []
    params: dict[str, str] = {}
    if quotation is not None:
        if not quotation.eligible:
            return incomplete("reference_precondition_not_eligible")
        by_role = {r["role"]: next(e for e in sources if e.citation_id == r["citation_id"]) for r in quotation.records}
        if family == "composition_cycling":
            assignments = [(recipe, [by_role["abstract"]]) for recipe in ("composition", "capacity", "coulombic")]
        else:
            sample = re.search(r"(?:образец|sample)\s+([a-z]\d+)", question, re.I)
            grade = re.search(r"Nafion[-‐‑ ]\d+", question, re.I)
            comparison = re.findall(r"\b[A-Z][A-Z0-9]{2,}\b", question)
            if sample is None or grade is None or len(comparison) != 1:
                return incomplete("ambiguous_query_fact_selectors")
            params = {"product": sample[1], "grade": grade.group(), "comparator": comparison[0]}
            assignments = [("dispersion_method", [by_role["method"]]), ("casting", [by_role["method"]]),
                           ("conductivity_table", [by_role["table"]])]
    elif fidelity is not None:
        if not fidelity.eligible:
            return incomplete("fidelity_source_precondition_not_eligible")
        article_ids = {a["article_id"] for r in fidelity.requirements for a in r.anchors}
        if len(article_ids) != 1:
            return incomplete("fact_source_work_ambiguous")
        selected = [e for e in sources if e.article_id in article_ids]
        recipes = ("oxide_comparison", "oxide_synthesis", "oxide_eis") if family.startswith("model_layer") else (
            "thermal_cycles", "hold_interpretation", "crystals", "amorphous")
        assignments = [(recipe, selected) for recipe in recipes]
    records: list[dict[str, Any]] = []
    parents: dict[str, Evidence] = {}
    for recipe, candidates in assignments:
        parsed = []
        for source in candidates:
            try:
                record = _record(recipe, source, params, f"F{len(records) + 1}")
            except FactPatternError as exc:
                diagnostics.append({"recipe": recipe, "citation_id": source.citation_id, "reason": str(exc)})
                continue
            parsed.append((source, record))
        if not parsed:
            return incomplete("unsupported_or_incomplete_fact_grammar")
        # Repeated overlapping raw chunks are redundant, not independent support.
        if len({r["allowed_claim"] for _, r in parsed}) != 1:
            return incomplete("ambiguous_fact_values_or_conditions")
        source, record = min(parsed, key=lambda pair: (len(pair[0].text), pair[0].chunk_id))
        records.append(record)
        parents[source.citation_id] = source
    derived = [replace(source, source_type=SOURCE_TYPE, text=json.dumps({"version": VERSION, "family": family,
                "language": "ru", "params": params, "raw_source": source.text,
                "records": [r for r in records if r["citation_id"] == source.citation_id]}, ensure_ascii=False))
               for source in parents.values()]
    if not records:
        return incomplete("no_supported_fact_records")
    return Bundle(True, "complete_source_bound_fact_bundle", family, derived, list(parents.values()), records, diagnostics)


def selection_records(evidence: list[Evidence]) -> dict[str, dict[str, Any]]:
    selected = [e for e in evidence if e.source_type == SOURCE_TYPE]
    if not selected:
        return {}
    if len(selected) != len(evidence) or len({e.article_id for e in selected}) != 1:
        raise GenerationOutputError("Fact selections must contain one work without unrestricted/mixed evidence")
    for source in selected:
        try:
            extension = json.loads(source.text)
        except (ValueError, UnicodeError) as exc:
            raise GenerationOutputError("Invalid fact selection JSON") from exc
        if isinstance(extension, dict) and "quantitative_policy" in extension:
            from app.generation.quantitative_facts import selection_records as quantitative_records
            return quantitative_records(selected)
    if any('"source_assembly"' in e.text or '"assembly"' in e.text for e in selected):
        from app.generation.methods_identity import POLICY
        from app.generation.methods_identity import selection_records as methods_records
        try:
            payload = json.loads(selected[0].text)
        except ValueError as exc:
            raise GenerationOutputError("Invalid assembly payload JSON") from exc
        if isinstance(payload, dict) and isinstance(payload.get("assembly"), dict) and payload["assembly"].get("version") == POLICY:
            return methods_records(selected)
        from app.generation.source_role_assembly import selection_records as assembled_records
        return assembled_records(selected)
    result: dict[str, dict[str, Any]] = {}
    families, parameters = set(), set()
    for source in selected:
        try:
            payload = json.loads(source.text)
        except (ValueError, UnicodeError) as exc:
            raise GenerationOutputError("Invalid fact selection JSON") from exc
        if (not isinstance(payload, dict) or payload.get("version") != VERSION or payload.get("language") != "ru"
                or not isinstance(payload.get("family"), str) or payload["family"] not in EXPECTED_RECIPES
                or not isinstance(payload.get("raw_source"), str) or not isinstance(payload.get("params"), dict)
                or not all(isinstance(k, str) and isinstance(v, str) for k, v in payload["params"].items())
                or not isinstance(payload.get("records"), list) or not payload["records"]):
            raise GenerationOutputError("Invalid fact selection contract")
        families.add(payload["family"])
        parameters.add(json.dumps(payload["params"], sort_keys=True))
        expected_params = {"product", "grade", "comparator"} if payload["family"] == "preparation_conductivity" else set()
        if set(payload["params"]) != expected_params:
            raise GenerationOutputError("Unexpected fact selectors")
        raw = replace(source, text=payload["raw_source"], source_type="main_text")
        for record in payload["records"]:
            if (not isinstance(record, dict) or not isinstance(record.get("selection_id"), str)
                    or not re.fullmatch(r"F[1-9][0-9]*", record["selection_id"], re.ASCII)
                    or record["selection_id"] in result or not isinstance(record.get("recipe"), str)):
                raise GenerationOutputError("Invalid or duplicate fact selection ID")
            try:
                expected = _record(record["recipe"], raw, payload["params"], record["selection_id"])
            except (FactPatternError, KeyError) as exc:
                raise GenerationOutputError("Fact record cannot be recomputed from its source") from exc
            if record != expected:
                raise GenerationOutputError("Fact fields/rendering differ from recomputed raw-source facts")
            result[record["selection_id"]] = record
    if set(result) != {f"F{i}" for i in range(1, len(result) + 1)}:
        raise GenerationOutputError("Noncanonical fact selection ID set")
    ordered = dict(sorted(result.items(), key=lambda pair: int(pair[0][1:])))
    if len(families) != 1 or len(parameters) != 1 or tuple(r["recipe"] for r in ordered.values()) != EXPECTED_RECIPES[next(iter(families))]:
        raise GenerationOutputError("Incomplete or mixed fact role contract")
    return ordered


def selection_choices(evidence: list[Evidence]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for key, record in selection_records(evidence).items():
        result.setdefault(record["citation_id"], []).append(key)
    return result


def prompt_records(evidence: list[Evidence]) -> list[dict[str, Any]]:
    """Keep source bindings server-side; provide compact, source-checkable facts."""
    result = []
    labels = {e.citation_id: e for e in evidence}
    for key, record in selection_records(evidence).items():
        facts = []
        for fact in record["facts"]:
            facts.append({"property": fact["property"], "sample": fact["sample"]["text"] if fact["sample"] else None,
                          "value": fact["value"]["text"] if fact["value"] else None,
                          "numeric_value": fact["value"]["numeric_value"] if fact["value"] else None,
                          "unit": fact["unit"]["text"] if fact["unit"] else None, "operation": fact["operation"],
                          "method": fact["method"]["text"] if fact["method"] else None,
                          "conditions": {k: v["text"] for k, v in fact["conditions"].items()},
                          "epistemic_status": fact["epistemic_status"], "unknown_fields": fact["unknown_fields"],
                          "source_quote": fact["support"]["text"]})
        parent = labels[record["citation_id"]]
        supplied = {"selection_id": key, "citation_id": record["citation_id"],
                       "source_title": parent.title, "source_doi": parent.doi,
                       "source_page_range": [parent.page_start, parent.page_end], "source_bound_facts": facts,
                       "server_russian_summary": record["allowed_claim"], "arithmetic": record["arithmetic"]}
        if "source_assembly" in record:
            context = json.loads(parent.text)["assembly"]
            from app.generation.methods_identity import POLICY, prompt_graph
            if context["version"] == POLICY:
                supplied["source_role_assembly"] = prompt_graph(context)
            else:
                link = next(b for b in context["bindings"] if b["selection_id"] == key)
                supplied["source_role_assembly"] = {"version": context["version"], "label": context["label"],
                                                "source_marker_quote": link["marker"]["text"]}
        result.append(supplied)
    return result


def resolve_selections(claims: list[GeneratedClaim], evidence: list[Evidence]) -> list[GeneratedClaim]:
    records = selection_records(evidence)
    if not records:
        return claims
    seen = set()
    for claim in claims:
        if (claim.text not in records or claim.text in seen
                or claim.citation_ids != [records[claim.text]["citation_id"]]):
            raise GenerationOutputError("Invalid fact selection ID/citation")
        seen.add(claim.text)
    if seen != set(records):
        raise GenerationOutputError("Fact answer must select every required ID")
    resolved = []
    for record in records.values():
        ids = [record["citation_id"]]
        from app.generation.methods_identity import POLICY
        if record.get("source_assembly") == POLICY:
            context = json.loads(next(e.text for e in evidence if e.citation_id == record["citation_id"]))["assembly"]
            ids = list(dict.fromkeys([*ids, *(p["citation_id"] for p in context["parents"])]))
        resolved.append(GeneratedClaim(record["allowed_claim"], ids))
    return resolved


def verify_raw_binding(text: str, raw: str, *, article_id: str, chunk_id: str, citation_id: str,
                       page_start: int, page_end: int, source_type: str | None = None) -> None:
    payload = json.loads(text)
    if not isinstance(payload, dict) or payload.get("raw_source") != raw:
        raise ValueError("Fact payload raw source differs from registered chunk")
    if "quantitative_policy" in payload:
        from app.generation.quantitative_facts import verify_raw_binding as verify_quantitative
        verify_quantitative(text, raw, article_id=article_id, chunk_id=chunk_id, citation_id=citation_id,
                            page_start=page_start, page_end=page_end, source_type=source_type)
        return
    from app.generation.methods_identity import ASSUMPTION_TEXT, POLICY
    context = payload.get("assembly")
    methods_policy = isinstance(context, dict) and context.get("version") == POLICY
    if isinstance(context, dict) and methods_policy:
        parents = context.get("parents")
        if not isinstance(parents, list) or {"citation_id": citation_id, "article_id": article_id,
                "chunk_id": chunk_id, "page_start": page_start, "page_end": page_end,
                "source_type": payload.get("raw_source_type")} not in parents:
            raise ValueError("Methods parent identity differs from registered chunk")
    # Source identity/page bounds are recomputed by selection_records in the runtime;
    # DB capture independently checks the registered chunk identity above this call.
    for record in payload.get("records", []):
        if (record.get("article_id"), record.get("chunk_id"), record.get("citation_id")) != (article_id, chunk_id, citation_id):
            raise ValueError("Fact record raw-source identity differs")
        source = Evidence(citation_id, article_id, chunk_id, None, None, page_start, page_end, "main_text", raw, 0, "binding", {}, {})
        expected = _record(record["recipe"], source, payload["params"], record["selection_id"])
        if "assembly" in payload:
            from app.generation.source_role_assembly import VERSION as ASSEMBLY_VERSION
            context = payload["assembly"]
            version = POLICY if methods_policy else ASSEMBLY_VERSION
            if (not isinstance(context, dict) or context.get("version") != version
                    or record.get("source_assembly") != version):
                raise ValueError("Invalid assembly parent version")
            expected["source_assembly"] = version
            if methods_policy:
                expected["allowed_claim"] += " " + ASSUMPTION_TEXT
        if record != expected:
            raise ValueError("Registered raw source does not reproduce fact fields/rendering")
