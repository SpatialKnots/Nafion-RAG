"""Offline complete-scope block planning; no inference or scientific admission."""

from __future__ import annotations

import json
import math
import platform
import re
from dataclasses import asdict
from importlib.metadata import version
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from app.evaluation.context_compaction import SourcePage, complete_pages_in_request
from app.evaluation.context_windows import RegisteredBlocks, _structural_risks, read_registered_blocks
from app.evaluation.layout_groups import _NOTE, ProtectedGroup, propose_layout_groups
from app.evaluation.ruled_tables import propose_ruled_tables, read_registered_rules
from app.evaluation.source_gaps import read_source_gaps
from app.records.article_scope import VERSION as SCOPE_VERSION
from app.records.schema import CandidateBundle, SourceRegion, source_identity, text_hash
from app.records.sources import file_hash

VERSION = "records_article_windows_v0.1"
MAX_CONTEXT_CHARS = 6000
CODE = (
    "app/records/article_windows.py", "app/records/article_windows_html.py", "scripts/records_article_windows.py", "app/records/schema.py",
    "app/records/sources.py", "app/evaluation/context_windows.py", "app/evaluation/context_compaction.py",
    "app/evaluation/layout_groups.py", "app/evaluation/ruled_tables.py", "app/evaluation/source_gaps.py",
    "app/generation/providers.py", "docs/records/article_windows_protocol_v0.1.md", "pyproject.toml",
)
_CUES = {
    "citation_or_prior_work_lexical_cue": re.compile(r"\[\d[^\]\n]*\]|\b(?:previous|recent)\s+(?:work|stud)|работ[еаыу]\s*\[", re.I),
    "unmeasurable_or_failure_lexical_cue": re.compile(
        r"not possible to measure|measurements? impossible|could not be measured|не удалось|невозмож\w*", re.I),
}


def source_page(region: SourceRegion) -> SourcePage:
    return SourcePage(str(region.article_id), region.region_id, region.page_number, region.text_layer,
                      str(region.text_layer_id), region.page_text, region.original_pdf_path, region.original_pdf_sha256)


def protected_intervals(mapping: RegisteredBlocks, groups: list[ProtectedGroup]) -> list[tuple[int, int]]:
    """Enclose all source-order members; spatial groups never justify removing interleaved text."""
    by_number = {b.block_number: i for i, b in enumerate(mapping.blocks)}
    intervals = []
    for group in groups:
        if (group.article_id, group.page, group.layer_id) != (mapping.article_id, mapping.page, mapping.layer_id):
            raise ValueError("Protected group belongs to a different registered page")
        if not group.block_numbers or any(n not in by_number for n in (*group.block_numbers, *group.context_blocks)):
            raise ValueError("Protected group references an unknown block")
        expected = {(mapping.blocks[by_number[n]].page_start, mapping.blocks[by_number[n]].page_end) for n in group.block_numbers}
        if set(group.page_ranges) != expected:
            raise ValueError("Protected group ranges differ from exact registered blocks")
        indices = [by_number[n] for n in (*group.block_numbers, *group.context_blocks)]
        intervals.append((min(indices), max(indices)))
    merged: list[tuple[int, int]] = []
    for first, last in sorted(intervals):
        if merged and first <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], last))
        else:
            merged.append((first, last))
    return merged


def plan_page(region: SourceRegion, mapping: RegisteredBlocks, groups: list[ProtectedGroup], *,
              max_chars: int = MAX_CONTEXT_CHARS) -> dict[str, Any]:
    """Account for every source block; unknown layout defers the page, never trims it."""
    if max_chars < 1:
        raise ValueError("Positive development context ceiling required")
    if region.start != 0 or region.end != len(region.page_text):
        raise ValueError("Article planner requires a complete stored source page")
    if (mapping.article_id, mapping.page, mapping.layer_id, mapping.text_sha256, mapping.selected_pdf_sha256) != (
        str(region.article_id), region.page_number, str(region.text_layer_id), region.page_text_sha256, region.layer_pdf_sha256
    ):
        raise ValueError("Block mapping differs from source identity")
    base: dict[str, Any] = {
        "article_id": str(region.article_id), "page_number": region.page_number, "parent_region_id": region.region_id,
        "page_text_sha256": region.page_text_sha256, "text_layer": region.text_layer,
        "text_layer_id": str(region.text_layer_id), "original_pdf_path": region.original_pdf_path,
        "original_pdf_sha256": region.original_pdf_sha256, "selected_pdf_path": region.layer_pdf_path,
        "selected_pdf_sha256": region.layer_pdf_sha256, "source_type": "not_recorded_in_source_packet",
        "page_text": region.page_text, "mapping": asdict(mapping), "protected_groups": [asdict(g) for g in groups],
        "contexts": [], "diagnostics": [], "block_accounting": [], "cross_page_relations": "not_resolved",
        "non_text_completeness": "not_established", "scientific_extraction": "not_run",
    }
    cursor = 0
    for block in mapping.blocks:
        if block.page_start != cursor or not cursor < block.page_end <= len(region.page_text):
            base["diagnostics"].append("block_registry_gap_overlap_or_invalid_range")
            break
        if (not all(math.isfinite(v) for v in block.bbox)
                or block.bbox[0] >= block.bbox[2] or block.bbox[1] >= block.bbox[3]):
            base["diagnostics"].append("invalid_block_geometry")
        cursor = block.page_end
    if cursor != len(region.page_text) or len({b.block_number for b in mapping.blocks}) != len(mapping.blocks):
        base["diagnostics"].append("block_registry_does_not_cover_page_exactly")
    if mapping.diagnostic:
        base["diagnostics"].append(mapping.diagnostic)
    if base["diagnostics"]:
        base.update(planning_state="deferred_page", deferred_characters=len(region.page_text),
                    block_accounting=[{"block_number": b.block_number, "page_start": b.page_start, "page_end": b.page_end,
                                       "state": "unproven_mapping_deferred_page"} for b in mapping.blocks])
        return base
    protected = protected_intervals(mapping, groups)
    shadow = list(region.quote)
    covered: set[int] = set()
    for first, last in protected:
        start, end = mapping.blocks[first].page_start, mapping.blocks[last].page_end
        shadow[start:end] = [" "] * (end - start)
        covered.update(range(first, last + 1))
    risks = _structural_risks("".join(shadow))
    # A table's geometric closure does not repair its damaged scientific notation.
    if "damaged_or_private_use_formula_text" in _structural_risks(region.quote):
        risks.append("damaged_or_private_use_formula_text")
    if any(_NOTE.match(region.quote[b.page_start:b.page_end]) for i, b in enumerate(mapping.blocks) if i not in covered):
        risks.append("unprotected_footnote_or_note_boundary")
    if risks:
        base.update(planning_state="deferred_page", deferred_characters=len(region.page_text), diagnostics=sorted(set(risks)),
                    block_accounting=[{"block_number": b.block_number, "page_start": b.page_start, "page_end": b.page_end,
                                       "state": "deferred_page"} for b in mapping.blocks])
        return base
    units = []
    index = 0
    starts = dict(protected)
    while index < len(mapping.blocks):
        last = starts.get(index, index)
        units.append((index, last))
        index = last + 1
    contexts: dict[tuple[int, int], dict[str, Any]] = {}
    for first, last in units:
        left, right = max(0, first - 1), min(len(mapping.blocks) - 1, last + 1)
        while True:
            before = (left, right)
            for begin, finish in protected:
                if begin <= right and finish >= left:
                    left, right = min(left, begin), max(right, finish)
            if before == (left, right):
                break
        start, end = mapping.blocks[left].page_start, mapping.blocks[right].page_end
        if (start, end) not in contexts:
            text = region.quote[start:end]
            reasons = []
            if len(text) > max_chars:
                reasons.append("context_exceeds_development_character_ceiling")
            user = {"context": [{"article_id": str(region.article_id), "page": region.page_number, "text": text}]}
            # Check plain content too: JSON escaping must never bypass the literal guard.
            matches = complete_pages_in_request(text, [source_page(region)])
            serialized_matches = complete_pages_in_request(json.dumps(user, ensure_ascii=False), [source_page(region)])
            if matches or serialized_matches:
                reasons.append("complete_source_page_guard")
            identifier = text_hash(json.dumps([VERSION, region.region_id, start, end], separators=(",", ":")))
            contexts[(start, end)] = {
                "context_id": identifier, "parent_region_id": region.region_id, "start": start, "end": end,
                "quote": text, "quote_sha256": text_hash(text), "core_units": [],
                "state": "deferred_context" if reasons else "bounded_context_proposal", "diagnostics": reasons,
                "cross_page_relations": "not_resolved", "scientific_adequacy": "not_established",
                "paragraph_completeness": "not_established_by_pdf_block_boundaries",
                "table_cell_semantics": "not_established_by_protected_geometry",
                "dispatch_status": "not_dispatched_offline_only", "extraction_status": "not_run",
                "lexical_cues": [{"kind": kind, "start": start + m.start(), "end": start + m.end(), "quote": m.group()}
                                 for kind, pattern in _CUES.items() for m in pattern.finditer(text)],
                "touches_page_start": start == 0, "touches_page_end": end == len(region.quote),
            }
        context = contexts[(start, end)]
        core = {"first_block_index": first, "last_block_index": last,
                "start": mapping.blocks[first].page_start, "end": mapping.blocks[last].page_end}
        context["core_units"].append(core)
        for i in range(first, last + 1):
            block = mapping.blocks[i]
            base["block_accounting"].append({"block_number": block.block_number, "page_start": block.page_start,
                                             "page_end": block.page_end, "core_context_id": context["context_id"],
                                             "state": context["state"]})
    base.update(planning_state="planned_with_explicit_context_states", deferred_characters=0,
                contexts=list(contexts.values()), protected_block_intervals=protected)
    return base


def _safe(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Article scope artifact path escapes its root")
    return path


def _bundle(region: SourceRegion, context: dict[str, Any], created_at: Any) -> CandidateBundle:
    data = region.model_dump()
    data.update(start=context["start"], end=context["end"], quote=context["quote"], quote_sha256=context["quote_sha256"],
                selection_basis="fixed_page", selection_note=f"{VERSION}: complete block context proposal; scientific adequacy unknown.")
    data["region_id"] = source_identity(data)
    return CandidateBundle(run_id=uuid5(NAMESPACE_URL, VERSION + context["context_id"]), created_at=created_at,
                           producer=VERSION, regions=(SourceRegion.model_validate(data),))


def export_article_windows(scope_dir: Path, output_dir: Path, *, source_root: Path,
                           max_chars: int = MAX_CONTEXT_CHARS) -> dict[str, Any]:
    if output_dir.exists():
        raise FileExistsError(f"Article window output already exists: {output_dir}")
    if max_chars < 1:
        raise ValueError("Positive development context ceiling required")
    scope_dir = scope_dir.resolve()
    manifest_path = scope_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    if manifest["version"] != SCOPE_VERSION:
        raise ValueError("Unsupported article scope input version")
    inputs = {str(manifest_path): file_hash(manifest_path)}
    for name, checksum in manifest["outputs"].items():
        path = _safe(scope_dir, name)
        if file_hash(path) != checksum:
            raise ValueError(f"Article scope artifact changed: {name}")
        inputs[str(path)] = checksum
    for name, checksum in manifest["inputs"].items():
        if file_hash(Path(name)) != checksum:
            raise ValueError(f"Frozen scope input changed: {name}")
        inputs[name] = checksum
    for name, checksum in manifest["code"].items():
        if file_hash(source_root / name) != checksum:
            raise ValueError(f"Article scope code context changed: {name}")
        inputs[str((source_root / name).resolve())] = checksum
    frozen_code = {name: file_hash(source_root / name) for name in CODE}
    report_input = json.loads((scope_dir / "report.json").read_bytes())
    inventory = {d["article_id"]: d for d in json.loads((scope_dir / "source_inventory.json").read_bytes())}
    if report_input["version"] != SCOPE_VERSION or report_input["source_fingerprint"] != manifest["source_fingerprint"]:
        raise ValueError("Article scope report identity mismatch")
    seen_documents = set()
    pages: list[dict[str, Any]] = []
    all_source_pages: list[SourcePage] = []
    bundles_to_write: dict[str, CandidateBundle] = {}
    for task in report_input["tasks"]:
        for declared in task["documents"]:
            identifier = declared["article_id"]
            if identifier in seen_documents or identifier not in inventory:
                raise ValueError("Task documents must be distinct registered sources")
            seen_documents.add(identifier)
            path = _safe(scope_dir, declared["bundle"])
            if file_hash(path) != declared["sha256"]:
                raise ValueError("Task bundle differs from declared hash")
            bundle = CandidateBundle.model_validate_json(path.read_bytes())
            source = inventory[identifier]
            if bundle.records or [r.model_dump(mode="json") for r in bundle.regions] != source["regions"]:
                raise ValueError("Task bundle is not the unchanged full source-only inventory")
            for name, expected in [(source["original_pdf_path"], source["original_pdf_sha256"]),
                                   *[(r.layer_pdf_path, r.layer_pdf_sha256) for r in bundle.regions]]:
                if file_hash(Path(name)) != expected:
                    raise ValueError("Source PDF differs from frozen hash")
                inputs[str(Path(name).resolve())] = expected
            import fitz  # type: ignore[import-untyped]

            with fitz.open(source["original_pdf_path"]) as pdf:
                if len(pdf) != source["pdf_page_count"]:
                    raise ValueError("Original PDF page count differs from source inventory")
            numbers = [p["page_number"] for p in declared["pages"]]
            if numbers != list(range(1, source["pdf_page_count"] + 1)):
                raise ValueError("Task must declare every original PDF page exactly once")
            regions = {r.page_number: r for r in bundle.regions}
            for declared_page in declared["pages"]:
                number = declared_page["page_number"]
                if number not in regions:
                    expected = "empty_selected_text" if number in source["stored_page_numbers"] else "missing_stored_page"
                    if declared_page["text_state"] != expected or declared_page["region_id"] is not None:
                        raise ValueError("Missing page declaration differs from source inventory")
                    pages.append({"task_id": task["task_id"], "article_id": identifier, "page_number": number,
                                  "planning_state": "deferred_page", "diagnostics": [expected], "contexts": [],
                                  "block_accounting": [], "page_text": None, "scientific_extraction": "not_run",
                                  "original_pdf_path": source["original_pdf_path"],
                                  "original_pdf_sha256": source["original_pdf_sha256"]})
                    continue
                region = regions[number]
                if (declared_page["text_state"], declared_page["region_id"], declared_page["page_text_sha256"],
                    declared_page["text_layer_id"], declared_page["text_layer"]) != (
                    "selected_text", region.region_id, region.page_text_sha256, str(region.text_layer_id), region.text_layer
                ):
                    raise ValueError("Declared page identity differs from source bundle")
                page = source_page(region)
                all_source_pages.append(page)
                mapping = read_registered_blocks(page, Path(region.layer_pdf_path), region.layer_pdf_sha256)
                layout = propose_layout_groups(page, mapping)
                table_groups: list[ProtectedGroup] = []
                table_diagnostics: list[dict[str, object]] = []
                if mapping.diagnostic is None:
                    tables = propose_ruled_tables(page, mapping, read_registered_rules(page, mapping))
                    table_groups, table_diagnostics = tables.groups, tables.diagnostics
                planned = plan_page(region, mapping, [*layout.groups, *table_groups], max_chars=max_chars)
                planned.update(task_id=task["task_id"], document_role=declared["role"],
                               layout_diagnostics=layout.diagnostics, table_diagnostics=table_diagnostics,
                               source_gaps=asdict(read_source_gaps(page, mapping)))
                for context in planned["contexts"]:
                    if context["state"] == "bounded_context_proposal":
                        bundles_to_write[context["context_id"]] = _bundle(region, context, bundle.created_at)
                        context["bundle"] = f'contexts/{context["context_id"]}.json'
                pages.append(planned)
    if len(report_input["tasks"]) != report_input["summary"]["article_tasks"] or len(pages) != report_input["summary"]["task_pdf_pages"]:
        raise ValueError("Task/page denominator differs from source-scope summary")
    for planned in pages:
        for context in planned["contexts"]:
            matches = complete_pages_in_request(context["quote"], all_source_pages)
            context["complete_page_matches_across_full_scope"] = matches
            if matches and context["state"] == "bounded_context_proposal":
                context["state"] = "deferred_context"
                context["diagnostics"].append("complete_source_page_guard_across_full_scope")
                context.pop("bundle")
                del bundles_to_write[context["context_id"]]
                for accounted in planned["block_accounting"]:
                    if accounted.get("core_context_id") == context["context_id"]:
                        accounted["state"] = "deferred_context"
    contexts = [c for page in pages for c in page["contexts"]]
    report = {
        "version": VERSION, "source_fingerprint": manifest["source_fingerprint"], "scope_manifest_sha256": inputs[str(manifest_path)],
        "policy": {"max_context_characters": max_chars, "neighbor_blocks": 1, "selection": "all_blocks_no_top_k",
                   "model_calls": 0, "existing_reply_limit": "one_measurement_per_request_not_exhaustive"},
        "summary": {"article_tasks": len(report_input["tasks"]), "source_documents": len(seen_documents), "pdf_pages": len(pages),
                    "deferred_pages": sum(p["planning_state"] == "deferred_page" for p in pages),
                    "registered_blocks": sum(len(p.get("mapping", {}).get("blocks", [])) for p in pages),
                    "accounted_blocks": sum(len(p["block_accounting"]) for p in pages),
                    "context_proposals": len(contexts), "bounded_context_proposals": len(bundles_to_write),
                    "deferred_contexts": sum(c["state"] == "deferred_context" for c in contexts),
                    "protected_groups": sum(len(p.get("protected_groups", [])) for p in pages),
                    "source_raster_occurrences": sum(sum(a["kind"] == "raster_image" for a in p.get("source_gaps", {}).get("assets", []))
                                                     for p in pages),
                    "scientific_precision": None, "scientific_recall": None, "new_model_calls": 0},
        "pages": pages,
        "limitations": ["Offline context planning, not completed measurement extraction or approved model transmission.",
                        "Every source remains development-exposed; no independent scientific evaluation.",
                        "Proposed layout groups do not establish scientific table/cell/footnote correctness.",
                        "Cross-page sample/condition/method dependencies and graphics completeness remain unresolved.",
                        "A bounded exact source slice is not proof of adequate scientific context.",
                        "Guard checks use plain context and a JSON fixture; the final provider request must be checked before dispatch.",
                        "Bibliography/citation/failure cues remain in scope, not automatic scientific labels or removals."],
    }
    output_dir.mkdir(parents=True, exist_ok=False)
    if bundles_to_write:
        (output_dir / "contexts").mkdir()
    for identifier, bundle in bundles_to_write.items():
        (output_dir / "contexts" / f"{identifier}.json").write_text(bundle.model_dump_json(indent=2) + "\n", encoding="utf-8")
    (output_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    from app.records.article_windows_html import render_plan

    (output_dir / "review.html").write_text(render_plan(report), encoding="utf-8")
    for name, checksum in inputs.items():
        if file_hash(Path(name)) != checksum:
            raise ValueError(f"Source/input changed during article planning: {name}")
    for name, checksum in frozen_code.items():
        if file_hash(source_root / name) != checksum:
            raise ValueError(f"Code changed during article planning: {name}")
    output_manifest = {"version": VERSION, "inputs": inputs, "code": frozen_code,
                       "runtime": {"python": platform.python_version(), "pymupdf": version("pymupdf"), "pydantic": version("pydantic")},
                       "outputs": {p.relative_to(output_dir).as_posix(): file_hash(p)
                                   for p in sorted(output_dir.rglob("*")) if p.is_file()}}
    (output_dir / "manifest.json").write_text(json.dumps(output_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report
