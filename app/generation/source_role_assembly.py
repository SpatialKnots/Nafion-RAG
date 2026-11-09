"""Finite same-label composition/capacity/CE assembly, never article-only ownership."""

from __future__ import annotations

import json
import re
from dataclasses import replace
from typing import Any

from app.generation import answer_facts as facts
from app.generation.fact_types import FactPatternError
from app.generation.providers import Evidence, GenerationOutputError
from app.generation.reference_quotes import _cell
from app.generation.reference_quotes import prepare as quotations
from app.generation.source_paraphrases import PREFIX_GUARD

VERSION = "source_role_assembly_v0.1"
ROLES = ("composition", "capacity", "coulombic")
MARKER = re.compile(r"(?m)^[ \t]*(?:ABSTRACT:[ \t]*(?:\r?\n)?)?Electrolyte (?P<label>[A-Za-z][A-Za-z0-9.-]*)\.[ \t]*(?:\r?\n)?")
MAX_PARAGRAPH = 4500


def has_markers(sources: list[Evidence]) -> bool:
    return any(MARKER.search(e.text) for e in sources)


def _marker(source: Evidence, record: dict[str, Any]) -> dict[str, Any] | None:
    supports = [f["support"] for f in record["facts"]]
    for match in MARKER.finditer(source.text):
        tail = source.text[match.end():]
        end = re.search(r"\n\s*\n|\n(?=\d+\.\s*[A-Z])|\n(?=Electrolyte )", tail)
        stop = match.end() + end.start() if end else len(source.text)
        paragraph = source.text[match.start():stop]
        if (len(paragraph) > MAX_PARAGRAPH or re.search(PREFIX_GUARD, paragraph, re.I)
                or not all(match.end() <= s["start"] < s["end"] <= stop for s in supports)):
            continue
        return {"label": match["label"], "citation_id": source.citation_id, "article_id": source.article_id,
                "chunk_id": source.chunk_id, "start": match.start(), "end": match.end(), "text": match.group(),
                "raw_chunk_sha256": supports[0]["raw_chunk_sha256"], "paragraph_end": stop}
    return None


def _signature(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _signature(v) for k, v in value.items() if k not in {"source", "support"}}
    if isinstance(value, list):
        return [_signature(v) for v in value]
    return value


def prepare(question: str, sources: list[Evidence], reference: Any, layers: dict[str, str | None],
            *, answer_language: str = "ru") -> facts.Bundle:
    diagnostics: list[dict[str, Any]] = []

    def blocked(reason: str) -> facts.Bundle:
        return facts.Bundle(False, reason, "composition_cycling", [], [], [], diagnostics,
                            {"version": VERSION, "reason": reason})

    if answer_language == "en" or (answer_language == "auto" and not re.search(r"[а-яё]", question, re.I)):
        return blocked("assembly_russian_answer_required")
    quote = quotations(question, sources, reference, answer_language=answer_language)
    if (quote is None or quote.diagnostics.get("family") != "composition_cycling"
            or quote.reason not in {"missing_bounded_reference_source_roles", "complete_bounded_reference_quotations"}):
        return blocked("assembly_reference_or_query_precondition_failed")
    if (not sources or len({e.article_id for e in sources}) != 1 or len({e.source_type for e in sources}) != 1
            or any(e.source_type.endswith("_derived") or not 1 <= e.page_start <= e.page_end for e in sources)
            or len({e.chunk_id for e in sources}) != len(sources)
            or len({e.citation_id for e in sources}) != len(sources)):
        return blocked("assembly_source_scope_unresolved")
    selected_layers = [layers.get(e.chunk_id) for e in sources]
    if any(not isinstance(v, str) or not v for v in selected_layers) or len(set(selected_layers)) != 1:
        return blocked("assembly_text_layer_unresolved")
    chosen = []
    for index, role in enumerate(ROLES, 1):
        candidates = []
        for source in sources:
            if role == "composition" and (source.page_start != 1 or source.citation_id not in
                                           quote.diagnostics["front_matter_author_citation_ids"]):
                continue
            try:
                record = facts._record(role, source, {}, f"F{index}")
            except FactPatternError as exc:
                diagnostics.append({"recipe": role, "citation_id": source.citation_id, "reason": str(exc)})
                continue
            marker = _marker(source, record)
            if marker is not None:
                candidates.append((source, record, marker))
        if not candidates:
            return blocked("assembly_missing_explicit_role_" + role)
        signatures = {(m["label"], json.dumps(_signature(r["facts"]), sort_keys=True), r["allowed_claim"])
                      for _, r, m in candidates}
        if len(signatures) != 1:
            return blocked("assembly_ambiguous_role_" + role)
        chosen.append(min(candidates, key=lambda c: (len(c[0].text), c[0].chunk_id)))
    labels = {m["label"] for _, _, m in chosen}
    if len(labels) != 1:
        return blocked("assembly_electrolyte_labels_differ")
    requested = {_cell(c) for c in re.findall(r"Li\s*(?:‖|\|\|)\s*[A-Z][A-Za-z0-9₀-₉]*", question)}
    actual = {_cell(r["facts"][0]["sample"]["text"]) for _, r, _ in chosen[1:]}
    if len(requested) != 2 or requested != actual:
        return blocked("assembly_requested_cell_binding_mismatch")
    parents = {e.citation_id: e for e, _, _ in chosen}
    assembly = {"version": VERSION, "label": next(iter(labels)), "question": question, "reference": reference,
                "layers": {e.chunk_id: layers[e.chunk_id] for e in parents.values()},
                "bindings": [{"recipe": r["recipe"], "selection_id": r["selection_id"], "marker": m} for _, r, m in chosen],
                "scope": "finite_explicit_label_relation_not_independent_scientific_ownership",
                "conditions_propagated": False}
    records = [{**r, "source_assembly": VERSION} for _, r, _ in chosen]
    derived = [replace(e, source_type=facts.SOURCE_TYPE, text=json.dumps({"version": facts.VERSION,
        "family": "composition_cycling", "language": "ru", "params": {}, "raw_source": e.text,
        "records": [r for r in records if r["citation_id"] == e.citation_id], "assembly": assembly}, ensure_ascii=False))
        for e in parents.values()]
    return facts.Bundle(True, "complete_source_role_assembly", "composition_cycling", derived, list(parents.values()),
                        records, diagnostics, assembly)


def selection_records(evidence: list[Evidence]) -> dict[str, dict[str, Any]]:
    """Recompute every parent, role and marker together; no partial graph acceptance."""
    try:
        payloads = [json.loads(e.text) for e in evidence]
        if not payloads or any(not isinstance(p, dict) for p in payloads):
            raise GenerationOutputError("Invalid assembly payload")
        context = payloads[0]["assembly"]
        if not isinstance(context, dict) or context.get("version") != VERSION:
            raise GenerationOutputError("Unsupported source assembly version")
        if (not isinstance(context.get("question"), str) or not isinstance(context.get("reference"), dict)
                or not isinstance(context.get("layers"), dict)
                or not all(isinstance(k, str) and isinstance(v, str) for k, v in context["layers"].items())
                or any(not isinstance(p.get("raw_source"), str) for p in payloads)):
            raise GenerationOutputError("Invalid source assembly context")
        if any(p.get("assembly") != context or e.source_type != facts.SOURCE_TYPE for e, p in zip(evidence, payloads, strict=True)):
            raise GenerationOutputError("Incomplete or inconsistent source assembly graph")
        raw = [replace(e, source_type="main_text", text=p["raw_source"]) for e, p in zip(evidence, payloads, strict=True)]
        rebuilt = prepare(context["question"], raw, context["reference"], context["layers"])
        if not rebuilt.eligible or [json.loads(e.text) for e in rebuilt.evidence] != payloads:
            raise GenerationOutputError("Assembly roles/fields/markers differ from recomputed raw sources")
    except (KeyError, TypeError, ValueError) as exc:
        raise GenerationOutputError("Invalid source assembly contract") from exc
    return {r["selection_id"]: r for r in rebuilt.records}
