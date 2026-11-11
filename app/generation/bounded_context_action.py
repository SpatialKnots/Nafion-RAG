"""One explicit missing-CE context lookup; unchanged inference and source ownership."""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Article, Chunk, Collection
from app.documents.service import build_pdf_url
from app.evaluation.query_packet import MAX_BYTES
from app.generation.answer_evidence_packet import VERSION as PACKET_VERSION
from app.generation.answer_evidence_packet import _hash, _page_index, serialize_packet, validate_packet
from app.generation.answer_requirements import _raw_sources, build_requirements
from app.generation.preparation_routes import PreparationRequest
from app.generation.providers import Evidence
from app.generation.query_qualifiers import assess_query_qualifiers
from app.generation.reference_quotes import _cell
from app.generation.reference_quotes import prepare as quotations
from app.generation.source_role_assembly import _marker, _signature
from app.generation.source_role_assembly import prepare as assemble
from app.records.sources import file_hash
from app.retrieval.search import SearchFilters, SearchResult, _result_from_chunk_article, apply_search_filters

VERSION = "bounded_coulombic_context_action_v0.2"
MAX_ROWS = 12
PAGE_WINDOW = 2
MAX_CANDIDATE_CHARS = 60000
MAX_ADDED_CHARS = 8000
BUDGETS = {"additional_lookup_calls": 1, "accepted_raw_chunks": 1, "candidate_rows": MAX_ROWS,
           "page_window": PAGE_WINDOW, "candidate_characters": MAX_CANDIDATE_CHARS,
           "accepted_raw_characters": MAX_ADDED_CHARS, "evidence_bundle_bytes": MAX_BYTES, "model_calls": 0}
CODE_FILES = ("app/generation/bounded_context_action.py", "app/generation/context_action_routes.py",
              "app/retrieval/search.py", "app/evaluation/query_packet_run.py", "app/generation/query_qualifiers.py")
Loader = Callable[[dict[str, Any]], list[SearchResult]]
Registrar = Callable[[Evidence], dict[str, Any]]


def code_bindings() -> dict[str, str]:
    root = Path(__file__).resolve().parents[2]
    return {name: file_hash(root / name) for name in CODE_FILES}


def _bundle_bytes(question: str, evidence: list[dict[str, Any]]) -> int:
    return len(serialize_packet({"question": question, "evidence": evidence}))


def _plan(packet: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
    parent = packet["content"]["parent"]
    p, mapped = parent["preparation"], parent["requirements"]
    if mapped["status"] != "mapped":
        return None, "unsupported_requirement_family"
    rows = {r["id"]: r for r in mapped["requirements"]}
    if rows["coulombic"]["state"] != "not_found_in_inspected_context":
        return None, "target_role_present_or_not_missing"
    if any(rows[r]["state"] != "recognized_source_pattern" or len(rows[r]["alternative_groups"]) != 1
           for r in ("composition", "capacity")):
        return None, "required_existing_roles_unresolved"
    allowed_blockers = {"baseline_insufficient_evidence", "source_registry_unproven"}
    inherited_qualifier_rejection = False
    if "query_qualifier_check_failed" in p["blocking_reasons"] and p.get("baseline_allowed") is False:
        qualifier_raw, _, _ = _raw_sources(p)
        expected = assess_query_qualifiers(p["question"], qualifier_raw, baseline_allowed=False,
                                          article_metadata=p.get("article_metadata"))
        if p.get("query_qualifiers") == expected and not expected["qualifiers"] and not expected["parse_warnings"]:
            allowed_blockers.add("query_qualifier_check_failed")
            inherited_qualifier_rejection = True
    if set(p["blocking_reasons"]) - allowed_blockers:
        return None, "blocking_reason_prevents_context_action"
    if p["sources"]["diagnostics"] or packet["content"]["inspection"]["uninspected"]:
        return None, "source_registry_diagnostics_unresolved"
    if not mapped["request_scope"]:
        return None, "request_scope_unrecorded"
    request = PreparationRequest.model_validate(mapped["request_scope"])
    if not request.collection.strip():
        return None, "request_collection_unresolved"
    if _bundle_bytes(p["question"], p["evidence"]) > MAX_BYTES:
        return None, "original_bundle_over_budget"
    raw, _, _ = _raw_sources(p)
    layers = p["sources"]["chunk_layers"]
    scopes = {(s.article_id, s.source_type, layers[s.chunk_id]) for s in raw}
    if len(scopes) != 1 or any(s.source_type != "main_text" for s in raw):
        return None, "selected_raw_source_scope_unresolved"
    reference = p["baseline_metadata"].get("retrieval", {}).get("explicit_source_reference")
    quote = quotations(p["question"], raw, reference, answer_language="ru")
    if quote is None or quote.reason != "missing_bounded_reference_source_roles":
        return None, "reference_or_query_precondition_failed"
    by_chunk = {s.chunk_id: s for s in raw}
    marked = []
    for role in ("composition", "capacity"):
        candidates = rows[role]["candidates"]
        markers = [_marker(by_chunk[c["chunk_id"]], {"facts": c["facts"]}) for c in candidates]
        if any(m is None for m in markers):
            return None, "existing_role_marker_unresolved"
        labels = {m["label"] for m in markers if m is not None}
        if len(labels) != 1:
            return None, "existing_role_marker_ambiguous"
        if role == "composition" and any(c["citation_id"] not in quote.diagnostics["front_matter_author_citation_ids"] for c in candidates):
            return None, "composition_author_binding_unresolved"
        marked.append((next(iter(labels)), candidates))
    if marked[0][0] != marked[1][0]:
        return None, "existing_role_labels_differ"
    capacity = min(marked[1][1], key=lambda c: (len(by_chunk[c["chunk_id"]].text), by_chunk[c["chunk_id"]].page_end, c["chunk_id"]))
    if _cell(capacity["facts"][0]["sample"]["text"]) not in mapped["requested_cells"]:
        return None, "capacity_requested_cell_mismatch"
    anchor = by_chunk[capacity["chunk_id"]]
    recorded = p["baseline_metadata"].get("retrieval", {}).get("filters", {})
    if not isinstance(recorded, dict) or set(recorded) - set(SearchFilters.__dataclass_fields__):
        return None, "recorded_filters_unresolved"
    library = str(request.library_source_id) if request.library_source_id is not None else None
    if recorded.get("library_source_id") not in {None, library}:
        return None, "recorded_library_scope_conflict"
    filters = SearchFilters.normalize(**{**recorded, "library_source_id": library}).as_metadata()
    if (filters.get("article_id", anchor.article_id) != anchor.article_id
            or filters.get("source_type", anchor.source_type) != anchor.source_type
            or filters.get("text_layer", layers[anchor.chunk_id]) != layers[anchor.chunk_id]):
        return None, "recorded_filter_scope_conflict"
    return {"question": p["question"], "collection": request.collection, "filters": filters,
        "article_id": anchor.article_id, "source_type": anchor.source_type, "text_layer": layers[anchor.chunk_id],
        "page_start_min": anchor.page_end, "page_end_max": anchor.page_end + PAGE_WINDOW - 1,
        "capacity_anchor_chunk_id": anchor.chunk_id, "label": marked[0][0],
        "inherited_empty_qualifier_rejection_preserved": inherited_qualifier_rejection}, "missing_coulombic_role_with_explicit_label"


def load_context_rows(session: Session, scope: dict[str, Any]) -> list[SearchResult]:
    statement = (select(Chunk, Article).join(Article).join(Collection)
        .where(Collection.name == scope["collection"], Article.id == UUID(scope["article_id"]),
            Chunk.source_type == scope["source_type"], Chunk.text_layer == scope["text_layer"],
            Chunk.page_start >= scope["page_start_min"], Chunk.page_end <= scope["page_end_max"])
        .order_by(Chunk.page_start, Chunk.page_end, Chunk.chunk_index, Chunk.id).limit(MAX_ROWS + 1))
    filters = SearchFilters.normalize(**scope["filters"])
    return [_result_from_chunk_article(c, a, query=scope["question"], score=0.0, retrieval_method="bounded_coulombic_context")
            for c, a in session.execute(apply_search_filters(statement, filters))]


def _evidence(row: SearchResult, selected: list[dict[str, Any]]) -> Evidence:
    used = {e["citation_id"] for e in selected}
    number = 1
    while f"E{number}" in used:
        number += 1
    return Evidence(f"E{number}", row.article_id, row.chunk_id, row.title, row.doi, row.page_start, row.page_end,
        row.source_type, row.full_text or "", row.score, row.retrieval_method, row.method_scores, row.method_ranks)


def _adapter(p: dict[str, Any], added: Evidence, registry: dict[str, Any], size: int) -> dict[str, Any]:
    if registry.get("diagnostics") or set(registry["chunks"]) != {added.chunk_id} or set(registry["chunk_layers"]) != {added.chunk_id}:
        raise ValueError("Additional source registry is incomplete or has foreign chunks")
    candidate = deepcopy(p)
    for kind in ("chunks", "chunk_layers", "pages"):
        for key, value in registry[kind].items():
            if key in candidate["sources"][kind] and candidate["sources"][kind][key] != value:
                raise ValueError("Additional context source registry collision")
            candidate["sources"][kind][key] = deepcopy(value)
    candidate["evidence"].append(asdict(added))
    candidate["diagnostic_candidate"] = {"version": VERSION, "original_preparation_hash": _hash(p),
        "added_chunk_ids": [added.chunk_id], "baseline_rechecked": False, "admission_changed": False}
    candidate["scope"] = {"baseline_scope": deepcopy(p.get("scope")), "diagnostic_only": True,
        "candidate_evidence_bundle_bytes": size, "byte_ceiling": MAX_BYTES}
    if "source_links" in candidate:
        candidate["source_links"].append({"citation_id": added.citation_id,
            "pdf_url": build_pdf_url(added.article_id, "original", added.page_start), "context_url": None})
    raw, missing, _ = _raw_sources(candidate)
    if missing or next(s for s in raw if s.chunk_id == added.chunk_id).text != added.text:
        raise ValueError("Registered additional context does not reproduce selected raw text")
    _page_index(candidate)
    return candidate


def run_context_action(packet: dict[str, Any], loader: Loader, registrar: Registrar) -> dict[str, Any]:
    if packet.get("version") != PACKET_VERSION:
        raise ValueError("Context action requires an original packet, never an action capsule/implicit continuation")
    validate_packet(packet, packet["content"]["parent"], expected_packet_id=packet["packet_id"])
    bindings = code_bindings()
    p = packet["content"]["parent"]["preparation"]
    plan, precondition = _plan(packet)
    observed: dict[str, Any] = {"lookup_performed": False, "candidate_rows": [], "registry_performed": False, "added_registry": None}
    diagnostics: list[dict[str, Any]] = []

    def finish(reason: str, added: Evidence | None = None, adapter: dict[str, Any] | None = None,
               after: dict[str, Any] | None = None) -> dict[str, Any]:
        consumed = {"additional_lookup_calls": int(observed["lookup_performed"]),
            "additional_registry_calls": int(observed["registry_performed"]), "accepted_raw_chunks": int(added is not None),
            "candidate_rows": len(observed["candidate_rows"]),
            "candidate_characters": sum(len(r["full_text"] or "") for r in observed["candidate_rows"]),
            "accepted_raw_characters": len(added.text) if added else 0, "model_calls": 0}
        core = {"version": VERSION, "input_packet": deepcopy(packet), "input_packet_id": packet["packet_id"],
            "code_bindings": bindings, "plan": plan, "precondition": precondition, "budgets": deepcopy(BUDGETS),
            "observations": deepcopy(observed), "candidate_diagnostics": deepcopy(diagnostics), "consumed": consumed,
            "added_evidence": asdict(added) if added else None, "candidate_map_input_adapter": adapter,
            "after_requirements": after, "stop_reason": reason, "admission_changed": False,
            "scientific_support": "not_evaluated", "generation_performed": False, "external_request_constructed": False,
            "network_ready": False, "automatic_continuation": False}
        previous = packet["journal"]["root_hash"]
        events: list[dict[str, Any]] = []
        observations: list[tuple[str, str, dict[str, Any]]] = [("preconditions_checked", precondition, {"plan": plan})]
        if observed["lookup_performed"]:
            observations.append(("bounded_lookup_observed", reason, {"scope": plan, "candidate_diagnostics": diagnostics}))
        if observed["registry_performed"]:
            observations.append(("additional_registry_observed", "raw_source_registered", {"added_evidence": core["added_evidence"]}))
        if after is not None:
            observations.append(("candidate_map_recomputed", "original_admission_preserved", {"after_map_hash": _hash(after)}))
        observations.append(("single_action_stop", reason, {"consumed": consumed, "automatic_continuation": False}))
        for kind, why, details in observations:
            event = {"sequence": len(events) + 1, "kind": kind, "reason": why, "details": details,
                "previous_hash": previous, "input_packet_id": packet["packet_id"], "actor_kind": "deterministic_system",
                "scientific_support": "not_evaluated"}
            previous = _hash(event)
            events.append({**event, "event_hash": previous})
        core["journal"] = {"version": "single_context_action_journal_v0.1", "parent_root_hash": packet["journal"]["root_hash"],
                           "events": events, "root_hash": previous, "human_reviews": []}
        if code_bindings() != bindings:
            raise ValueError("Context action code changed during execution")
        return {**core, "result_id": _hash(core)}

    if plan is None:
        return finish(precondition)
    raw_rows = loader(deepcopy(plan))
    observed.update(lookup_performed=True, candidate_rows=[asdict(r) for r in raw_rows])
    if len(raw_rows) > MAX_ROWS:
        return finish("candidate_overflow")
    if len({r.chunk_id for r in raw_rows}) != len(raw_rows):
        return finish("duplicate_candidate_id")
    if any(not isinstance(r.full_text, str) or not r.full_text.strip() for r in raw_rows):
        return finish("candidate_raw_text_unavailable")
    if sum(len(r.full_text or "") for r in raw_rows) > MAX_CANDIDATE_CHARS:
        return finish("candidate_text_budget_exceeded")
    if any((r.article_id, r.source_type, r.text_layer) != (plan["article_id"], plan["source_type"], plan["text_layer"])
           or not plan["page_start_min"] <= r.page_start <= r.page_end <= plan["page_end_max"]
           or r.chunk_id in {e["chunk_id"] for e in p["evidence"]} for r in raw_rows):
        return finish("loader_scope_violation")
    raw, _, _ = _raw_sources(p)
    reference = p["baseline_metadata"]["retrieval"]["explicit_source_reference"]
    eligible: list[tuple[SearchResult, Evidence, str]] = []
    for row in raw_rows:
        extra = _evidence(row, p["evidence"])
        layers = {**p["sources"]["chunk_layers"], row.chunk_id: row.text_layer}
        bundle = assemble(p["question"], [*raw, extra], reference, layers)
        diagnostics.append({"chunk_id": row.chunk_id, "eligible": bundle.eligible, "reason": bundle.reason,
                            "recipe_diagnostics": bundle.diagnostics})
        if bundle.eligible:
            signature = serialize_packet({"facts": _signature(bundle.records[2]["facts"]),
                                          "claim": bundle.records[2]["allowed_claim"]}).decode("utf-8")
            eligible.append((row, extra, signature))
    if not eligible:
        return finish("bounded_role_context_not_resolved")
    if len({signature for _, _, signature in eligible}) != 1:
        return finish("ambiguous_role_context")
    row, added, _ = min(eligible, key=lambda pair: (len(pair[1].text), pair[0].page_start, pair[0].page_end, pair[0].chunk_id))
    if len(added.text) > MAX_ADDED_CHARS:
        return finish("accepted_text_budget_exceeded")
    size = _bundle_bytes(p["question"], [*p["evidence"], asdict(added)])
    if size > MAX_BYTES:
        return finish("candidate_bundle_over_budget")
    registry = registrar(added)
    observed.update(registry_performed=True, added_registry=deepcopy(registry))
    adapter = _adapter(p, added, registry, size)
    after = build_requirements(adapter, packet["content"]["request_scope"])
    if after["requirements"][-1]["state"] != "textual_contract_available":
        raise ValueError("Additional context assembly did not reproduce the diagnostic map contract")
    return finish("bounded_raw_context_added", added, adapter, after)


def validate_context_result(result: dict[str, Any], current_packet: dict[str, Any], *, expected_result_id: str | None = None) -> None:
    if expected_result_id is not None and result.get("result_id") != expected_result_id:
        raise ValueError("Context result differs from pinned identity")
    try:
        observed = result["observations"]
        rebuilt = run_context_action(current_packet, lambda scope: [SearchResult(**r) for r in observed["candidate_rows"]],
                                     lambda source: deepcopy(observed["added_registry"]))
    except (KeyError, TypeError) as exc:
        raise ValueError("Malformed context action observations") from exc
    if serialize_packet(rebuilt) != serialize_packet(result):
        raise ValueError("Context action differs from trusted-packet/recorded-observation replay")
