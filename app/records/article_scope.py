"""Source-bound development screening and whole-stored-article task packets."""

from __future__ import annotations

import html
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Literal, Self
from uuid import UUID

from pydantic import Field, model_validator

from app.records.pilot_audit import audit_packet
from app.records.schema import CandidateBundle, ContractModel, EvidenceSpan, NonEmpty, Sha256
from app.records.sources import file_hash

VERSION = "records_article_scope_v0.1"


class ScreeningEntry(ContractModel):
    article_id: UUID
    status: Literal["proposed_primary", "proposed_supplement", "related_dissertation", "other_property_context", "unresolved"]
    rationale: NonEmpty
    inspected_pages: tuple[int, ...] = ()
    evidence: tuple[EvidenceSpan, ...] = ()

    @model_validator(mode="after")
    def validate_scope(self) -> Self:
        if len(set(self.inspected_pages)) != len(self.inspected_pages) or any(page < 1 for page in self.inspected_pages):
            raise ValueError("Inspected pages must be distinct positive page numbers")
        if self.status != "unresolved" and (not self.inspected_pages or not self.evidence):
            raise ValueError("An interpreted screening status requires evidence and declared inspected pages")
        return self


class SourceRelation(ContractModel):
    kind: Literal["proposed_supplement_of"]
    subject: UUID
    target: UUID
    rationale: NonEmpty
    subject_evidence: tuple[EvidenceSpan, ...] = Field(min_length=1)
    target_evidence: tuple[EvidenceSpan, ...] = Field(min_length=1)


class Screening(ContractModel):
    version: Literal["records_article_screening_v0.1"] = "records_article_screening_v0.1"
    source_fingerprint: Sha256
    author: NonEmpty
    author_kind: Literal["assistant"] = "assistant"
    scope: Literal["Li-Nafion conductivity; preserve author property wording"]
    independence: Literal["development_proposals_not_independent_annotation"] = "development_proposals_not_independent_annotation"
    documents: tuple[ScreeningEntry, ...] = Field(min_length=1)
    relations: tuple[SourceRelation, ...] = ()


def _check_spans(spans: tuple[EvidenceSpan, ...], bundle: CandidateBundle | None, article_id: UUID) -> set[int]:
    regions = {r.region_id: r for r in bundle.regions} if bundle else {}
    pages = set()
    for span in spans:
        region = regions.get(span.region_id)
        if region is None or region.article_id != article_id:
            raise ValueError("Screening evidence belongs to an unknown region or different document")
        if region.quote[span.start:span.end] != span.quote or span.end > len(region.quote):
            raise ValueError("Screening evidence differs from exact source span")
        pages.add(region.page_number)
    return pages


def validate_screening(screening: Screening, inventory: list[dict[str, Any]],
                       bundles: dict[str, CandidateBundle | None], fingerprint: str) -> None:
    if screening.source_fingerprint != fingerprint:
        raise ValueError("Screening source fingerprint differs from verified packet")
    entries = {str(entry.article_id): entry for entry in screening.documents}
    sources = {row["article_id"]: row for row in inventory}
    if len(entries) != len(screening.documents) or set(entries) != set(sources):
        raise ValueError("Screening must cover each packet document exactly once")
    for identifier, entry in entries.items():
        pages = _check_spans(entry.evidence, bundles[identifier], entry.article_id)
        if bundles[identifier] is not None and not entry.evidence:
            raise ValueError("Document with stored text requires an identity or screening excerpt")
        if any(page > sources[identifier]["pdf_page_count"] for page in entry.inspected_pages):
            raise ValueError("Inspected page outside original PDF")
        if entry.status != "unresolved" and not pages <= set(entry.inspected_pages):
            raise ValueError("Interpreted evidence must belong to declared inspected pages")
    linked: set[str] = set()
    for relation in screening.relations:
        subject, target = str(relation.subject), str(relation.target)
        if subject not in entries or target not in entries or subject == target:
            raise ValueError("Relation requires distinct registered documents")
        if entries[subject].status != "proposed_supplement" or entries[target].status != "proposed_primary":
            raise ValueError("Supplement relation requires supplement subject and primary target")
        if subject in linked:
            raise ValueError("Supplement cannot have multiple or duplicate proposed parent links")
        linked.add(subject)
        for identifier, spans in ((subject, relation.subject_evidence), (target, relation.target_evidence)):
            pages = _check_spans(spans, bundles[identifier], UUID(identifier))
            if not pages <= set(entries[identifier].inspected_pages):
                raise ValueError("Relation evidence must belong to declared inspected pages")
    if linked != {identifier for identifier, entry in entries.items() if entry.status == "proposed_supplement"}:
        raise ValueError("Every proposed supplement needs one source-supported proposed parent")


def _identity_groups(inventory: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    groups: dict[str, list[str]] = defaultdict(list)
    for row in inventory:
        if value := row[key]:
            # DOI values are compared as recorded; do not repair/truncate/normalize metadata.
            groups[value].append(row["article_id"])
    return [{"recorded_value": value, "article_ids": sorted(ids)} for value, ids in sorted(groups.items()) if len(ids) > 1]


def _coverage(row: dict[str, Any], bundle: CandidateBundle | None) -> list[dict[str, Any]]:
    regions = {r.page_number: r for r in bundle.regions} if bundle else {}
    stored = set(row["stored_page_numbers"])
    pages = []
    for number in range(1, row["pdf_page_count"] + 1):
        region = regions.get(number)
        pages.append({
            "page_number": number,
            "text_state": "selected_text" if region else "empty_selected_text" if number in stored else "missing_stored_page",
            "region_id": region.region_id if region else None,
            "text_layer": region.text_layer if region else None,
            "text_layer_id": str(region.text_layer_id) if region else None,
            "page_text_sha256": region.page_text_sha256 if region else None,
            "non_text_completeness": "not_established",
            "scientific_extraction": "not_run",
        })
    return pages


def _render(report: dict[str, Any], bundles: dict[str, CandidateBundle | None]) -> str:
    rows = []
    for row in report["documents"]:
        identifier = row["article_id"]
        bundle = bundles[identifier]
        uri = Path(row["original_pdf_path"]).resolve().as_uri()
        excerpts = []
        regions = {r.region_id: r for r in bundle.regions} if bundle else {}
        for span in row["screening"]["evidence"]:
            region = regions[span["region_id"]]
            source = f'PDF p.{region.page_number}, {region.text_layer}, offsets {span["start"]}:{span["end"]}'
            excerpts.append(f'<p><a href="{html.escape(uri, quote=True)}#page={region.page_number}">{source}</a></p>'
                            f'<pre>{html.escape(span["quote"])}</pre>')
        pages = "".join(f'<details><summary>PDF p.{r.page_number} · {r.text_layer}</summary>'
                        f'<a href="{html.escape(uri, quote=True)}#page={r.page_number}">Original PDF page</a>'
                        f'<pre>{html.escape(r.quote)}</pre></details>' for r in bundle.regions) if bundle else ""
        rows.append('<tr class="document"><td>' + html.escape(row["title"] or "Title absent in snapshot")
                    + '<br><code>' + identifier + '</code><br>' + html.escape(row["doi"] or "DOI absent in snapshot")
                    + '</td><td>' + html.escape(row["screening"]["status"]) + '<p>'
                    + html.escape(row["screening"]["rationale"]) + '</p></td><td>'
                    + str(row["pdf_pages"]) + '<br>development_exposed</td><td>' + "".join(excerpts)
                    + '<details><summary>Source and scope diagnostics</summary><pre>'
                    + html.escape(json.dumps(row, ensure_ascii=False, indent=2)) + '</pre></details>'
                    + '<details><summary>All stored selected-text pages</summary>' + pages + '</details></td><td>'
                    + f'<a href="{html.escape(uri, quote=True)}">Original PDF</a></td></tr>')
    return ('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
            '<title>ARIADNE — article development scope</title><style>'
            'body{font:15px system-ui;margin:24px;color:#19332d}table{border-collapse:collapse;width:100%}'
            'td,th{border:1px solid #bccbc4;padding:12px;vertical-align:top}th{text-align:left;background:#e9f1ec}'
            'pre{white-space:pre-wrap;overflow-wrap:anywhere;max-width:70ch}details{margin:8px 0}'
            'code{overflow-wrap:anywhere}input{padding:8px;width:50%}[hidden]{display:none!important}</style>'
            f'<h1>Article-level development scope · {VERSION}</h1>'
            '<p>Assistant screening proposals. Scientific eligibility and independent evaluation remain unestablished. '
            'Source-only tasks contain no extracted measurements. Non-text completeness remains unresolved.</p><pre>'
            + html.escape(json.dumps(report["summary"], ensure_ascii=False, indent=2))
            + '</pre><details><summary>Input snapshot, identity diagnostics and source relations</summary><pre>'
            + html.escape(json.dumps({k: report[k] for k in ("source_fingerprint", "identity_diagnostics", "relations", "limitations")},
                                     ensure_ascii=False, indent=2))
            + '</pre></details><label>Search <input id="search" type="search"></label><p id="count"></p>'
            '<table><thead><tr><th>Title / recorded DOI</th><th>Provisional screening</th><th>Pages / exposure</th>'
            '<th>Exact source evidence / full stored text</th><th>Original file</th></tr></thead><tbody>'
            + "".join(rows) + '</tbody></table><script>'
            'const rows=[...document.querySelectorAll("tr.document")];function filter(){'
            'const q=document.getElementById("search").value.toLocaleLowerCase();let n=0;'
            'for(const r of rows){r.hidden=!r.textContent.toLocaleLowerCase().includes(q);if(!r.hidden)n++;}'
            'document.getElementById("count").textContent=n+" / "+rows.length;}'
            'document.getElementById("search").addEventListener("input",filter);filter();</script></html>\n')


def export_article_scope(packet: Path, screening_path: Path, output_dir: Path, *, source_root: Path) -> dict[str, Any]:
    """Verify the historical packet, then export deterministic offline task inputs."""
    if output_dir.exists():
        raise FileExistsError(f"Article scope output already exists: {output_dir}")
    packet = packet.resolve()
    screening_raw = screening_path.read_bytes()
    screening = Screening.model_validate_json(screening_raw)
    # The auditor creates its own fresh directory only after validating source integrity.
    audit = audit_packet(packet, output_dir / "source_audit", source_root=source_root)
    inventory = json.loads((packet / "source_inventory.json").read_bytes())
    bundles = {row["article_id"]: CandidateBundle.model_validate_json(
        (packet / "sources" / f'{row["article_id"]}.json').read_bytes()) if row["regions"] else None for row in inventory}
    validate_screening(screening, inventory, bundles, audit["source_fingerprint"])
    sources = {row["article_id"]: row for row in inventory}
    entries = {str(entry.article_id): entry for entry in screening.documents}
    identity = {"same_original_pdf": _identity_groups(inventory, "original_pdf_sha256"),
                "same_recorded_doi": _identity_groups(inventory, "doi"),
                "scientific_work_or_measurement_equivalence": "not_established"}
    tasks: list[dict[str, Any]] = []
    for identifier, entry in sorted(entries.items()):
        if entry.status != "proposed_primary":
            continue
        attached = sorted(str(r.subject) for r in screening.relations if str(r.target) == identifier)
        documents: list[dict[str, Any]] = []
        for doc_id in [identifier, *attached]:
            bundle_path = packet / "sources" / f"{doc_id}.json"
            if bundles[doc_id] is None:
                raise ValueError("Article task requires a source bundle for every selected document")
            destination = output_dir / "tasks" / identifier / f"{doc_id}.json"
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(bundle_path.read_bytes())
            documents.append({"article_id": doc_id, "role": "primary" if doc_id == identifier else "proposed_supplement",
                              "bundle": destination.relative_to(output_dir).as_posix(), "sha256": file_hash(destination),
                              "original_pdf_path": sources[doc_id]["original_pdf_path"],
                              "original_pdf_sha256": sources[doc_id]["original_pdf_sha256"],
                              "pages": _coverage(sources[doc_id], bundles[doc_id]),
                              "diagnostics": sources[doc_id]["diagnostics"]})
        tasks.append({"task_id": identifier, "primary_article_id": identifier, "documents": documents,
                      "scope": "All original PDF pages; complete available stored selected text, including bibliography.",
                      "exposure": "development_exposed", "work_group_status": "provisional_source_relation_only",
                      "extraction_status": "not_run", "reference_status": "not_annotated",
                      "measurement_duplication": "not_assessed", "api_calls": 0})
    counts = Counter(entry.status for entry in screening.documents)
    report = {
        "version": VERSION, "source_packet": str(packet), "source_fingerprint": audit["source_fingerprint"],
        "screening_author": screening.author, "screening_independence": screening.independence,
        "summary": {"documents": len(inventory), "screening_status_counts": dict(sorted(counts.items())),
                    "article_tasks": len(tasks),
                    "task_source_documents": sum(len(t["documents"]) for t in tasks),
                    "task_pdf_pages": sum(len(d["pages"]) for t in tasks for d in t["documents"]),
                    "task_selected_text_pages": sum(p["text_state"] == "selected_text" for t in tasks
                                                    for d in t["documents"] for p in d["pages"]),
                    "target_publications": {"minimum": 10, "maximum": 15},
                    "scientifically_eligible_independent_publications": None, "independent_split": "not_established",
                    "scientific_precision": None, "scientific_recall": None, "human_time_savings": None,
                    "new_model_calls": 0, "extraction_status": "not_run"},
        "identity_diagnostics": identity, "relations": [r.model_dump(mode="json") for r in screening.relations],
        "documents": [{"article_id": identifier, "title": row["title"], "doi": row["doi"],
                       "original_pdf_path": row["original_pdf_path"], "original_pdf_sha256": row["original_pdf_sha256"],
                       "pdf_pages": row["pdf_page_count"], "exposure": "development_exposed",
                       "scientific_eligibility": "not_established", "screening": entries[identifier].model_dump(mode="json"),
                       "diagnostics": row["diagnostics"], "source_type": "not_recorded_in_source_packet"}
                      for identifier, row in sorted(sources.items())],
        "tasks": tasks,
        "limitations": ["Screening interpretations are assistant proposals, not independent scientific labels.",
                        "Other-property context and unresolved documents are not negative measurement labels.",
                        "Proposed primary count is not eligible publication count or achievement of the 10–15 target.",
                        "Same PDF/recorded DOI and proposed supplement links do not establish independent measurements.",
                        "All inputs are development-exposed; no untouched split is created.",
                        "Stored text and page accounting do not establish complete figure/table/scientific-notation coverage.",
                        "Source type is absent in the historical region schema; original/ocr layer labels are retained.",
                        "No inference, article-wide extraction, scientific admission or human-time evaluation performed."],
    }
    (output_dir / "screening.json").write_bytes(screening_raw)
    (output_dir / "source_inventory.json").write_bytes((packet / "source_inventory.json").read_bytes())
    (output_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_dir / "review.html").write_text(_render(report, bundles), encoding="utf-8")
    source_manifest = json.loads((output_dir / "source_audit" / "manifest.json").read_bytes())
    inputs = source_manifest["inputs"] | {str(screening_path.resolve()): file_hash(screening_path)}
    if (output_dir / "screening.json").read_bytes() != screening_path.read_bytes():
        raise ValueError("Screening input changed during export")
    for name, expected in inputs.items():
        if file_hash(Path(name)) != expected:
            raise ValueError(f"Source/input changed during article export: {name}")
    code = source_manifest["code"] | {name: file_hash(source_root / name) for name in (
        "app/records/article_scope.py", "scripts/records_article_scope.py", "docs/records/article_scope_protocol_v0.1.md")}
    manifest = {"version": VERSION, "source_fingerprint": report["source_fingerprint"], "inputs": inputs, "code": code,
                "outputs": {p.relative_to(output_dir).as_posix(): file_hash(p)
                            for p in sorted(output_dir.rglob("*")) if p.is_file()}}
    (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report
