"""Verify a frozen source-only packet and expose independent-pilot prerequisites."""

from __future__ import annotations

import hashlib
import html
import json
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

from app.records.pilot import PILOT_VERSION, PilotDocument, selection_audit, source_content
from app.records.schema import CandidateBundle, text_hash
from app.records.sources import file_hash

VERSION = "records_independent_pilot_readiness_v0.1"


def audit_packet(packet: Path, output_dir: Path, *, annotator_availability: Literal["unavailable", "not_declared"] = "not_declared",
                 source_root: Path) -> dict[str, Any]:
    if output_dir.exists():
        raise FileExistsError(f"Pilot audit output already exists: {output_dir}")
    packet = packet.resolve()
    manifest_path = packet / "manifest.json"
    manifest_raw = manifest_path.read_bytes()
    manifest = json.loads(manifest_raw)
    if manifest["schema_version"] != PILOT_VERSION:
        raise ValueError("Unsupported source-only pilot packet")
    snapshots: dict[Path, str] = {manifest_path: hashlib.sha256(manifest_raw).hexdigest()}
    for name, expected in manifest["artifacts_sha256"].items():
        path = (packet / name).resolve()
        if not path.is_relative_to(packet):
            raise ValueError("Source packet artifact escapes its directory")
        if file_hash(path) != expected:
            raise ValueError(f"Changed source packet artifact: {name}")
        snapshots[path] = expected
    inventory = json.loads((packet / "source_inventory.json").read_bytes())
    profile = json.loads((packet / "profile.json").read_bytes())
    documents = []
    pdfs: dict[Path, str] = {}
    for entry in inventory:
        article_id = UUID(entry["article_id"])
        bundle_path = packet / "sources" / f"{article_id}.json"
        bundle = CandidateBundle.model_validate_json(bundle_path.read_bytes()) if entry["regions"] else None
        if bundle is not None and [region.model_dump(mode="json") for region in bundle.regions] != entry["regions"]:
            raise ValueError(f"Inventory/source-bundle mismatch: {article_id}")
        document = PilotDocument(article_id=article_id, title=entry["title"], doi=entry["doi"],
                                 original_pdf_path=entry["original_pdf_path"], original_pdf_sha256=entry["original_pdf_sha256"],
                                 pdf_page_count=entry["pdf_page_count"], stored_page_numbers=tuple(entry["stored_page_numbers"]),
                                 bundle=bundle, diagnostics=tuple(entry["diagnostics"]))
        document.validate()
        documents.append(document)
        declared = [(document.original_pdf_path, document.original_pdf_sha256)]
        declared += [(region.layer_pdf_path, region.layer_pdf_sha256) for region in bundle.regions] if bundle else []
        for name, expected in declared:
            path = Path(name).resolve()
            if path in pdfs and pdfs[path] != expected:
                raise ValueError(f"Conflicting declared source PDF hashes: {path}")
            pdfs[path] = expected
    if not documents or len({doc.article_id for doc in documents}) != len(documents):
        raise ValueError("Packet requires nonempty distinct document IDs")
    content = source_content(tuple(documents))
    fingerprint = text_hash(json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    if fingerprint != manifest["source_fingerprint"]:
        raise ValueError("Source-content fingerprint mismatch")
    selection = selection_audit(profile, tuple(documents))
    if selection != json.loads((packet / "selection_audit.json").read_bytes()):
        raise ValueError("Source selection audit differs from frozen profile")
    if manifest["annotations"] != 0 or manifest["candidate_records"] != 0 or manifest["independent_gold"] is not False:
        raise ValueError("Source-only packet unexpectedly declares annotations/gold")
    if manifest["split"] != "development_only_no_untouched_evaluation":
        raise ValueError("This audit supports the declared development-only source packet")
    observed = {"documents": len(documents), "pdf_pages": sum(doc.pdf_page_count for doc in documents),
                "stored_pages": sum(len(doc.stored_page_numbers) for doc in documents),
                "exported_regions": sum(len(doc.bundle.regions) if doc.bundle else 0 for doc in documents),
                "lexical_candidate_count": selection["lexical_candidate_count"]}
    if any(manifest[key] != count for key, count in observed.items()):
        raise ValueError("Source packet summary differs from verified scope")
    snapshots.update(pdfs)
    for path, expected in snapshots.items():
        if file_hash(path) != expected:
            raise ValueError(f"Source/input changed during audit: {path}")
    priorities = {entry["article_id"]: entry["candidate_priority"] for entry in profile["articles"]}
    rows: list[dict[str, Any]] = [{"article_id": str(doc.article_id), "title": doc.title, "doi": doc.doi,
             "original_pdf_path": doc.original_pdf_path, "original_pdf_sha256": doc.original_pdf_sha256,
             "pdf_pages": doc.pdf_page_count, "candidate_priority": priorities[str(doc.article_id)],
             "scientific_eligibility": "not_established", "exposure": "development_exposed",
             "diagnostics": list(doc.diagnostics), "source_bundle": str(packet / "sources" / f"{doc.article_id}.json")}
            for doc in sorted(documents, key=lambda item: str(item.article_id))]
    report: dict[str, Any] = {
        "version": VERSION, "source_packet": str(packet), "source_fingerprint": fingerprint,
        "summary": observed | {"verified_pdf_files": len(pdfs), "independent_pilot": "not_ready",
                                "scientifically_eligible_publications": None, "independent_reference_records": None,
                                "independent_annotator_availability": annotator_availability,
                                "independent_split": "not_established", "scientific_precision": None,
                                "scientific_recall": None, "human_time_observations_in_this_audit": 0, "human_time_savings": None},
        "blockers": ["Independent annotator/reference not supplied", "Scientifically eligible 10–15-publication cohort not established",
                     "Work-level untouched evaluation split not established", "No comparable human-time observations supplied"],
        "documents": rows,
        "limitations": ["Lexical candidates are not independently eligible publications or unique experiments.",
                        "Audit describes the supplied historical snapshot, not a new database census.",
                        "No-hit documents are not scientific negatives; development exposure is not erased by a random split.",
                        "No new model inference, source repair, annotation or scientific acceptance is performed."],
    }
    sections = []
    for row, doc in zip(rows, sorted(documents, key=lambda item: str(item.article_id)), strict=True):
        uri = Path(doc.original_pdf_path).resolve().as_uri()
        pages = "".join(f'<details><summary>PDF p.{region.page_number} · {region.text_layer}</summary>'
                        f'<a href="{html.escape(uri, quote=True)}#page={region.page_number}">Оригинал</a>'
                        f'<pre>{html.escape(region.quote)}</pre></details>' for region in doc.bundle.regions) if doc.bundle else ""
        sections.append('<article><h2>' + html.escape(row["title"] or "Название отсутствует в snapshot") + '</h2>'
                        '<pre>' + html.escape(json.dumps(row, ensure_ascii=False, indent=2)) + '</pre>' + pages + '</article>')
    page = ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>ARIADNE — независимый пилот: готовность</title>'
            '<style>body{font:15px system-ui;margin:24px;max-width:1200px}pre{white-space:pre-wrap;overflow-wrap:anywhere}'
            'article{border-top:1px solid #ccd4df;padding:14px 0}details{margin:10px 0}[hidden]{display:none!important}</style>'
            f'<h1>Готовность независимого пилота: {VERSION}</h1><p>Источники проверены. Научный эталон и метрики не установлены.</p>'
            '<pre>' + html.escape(json.dumps(report["summary"], ensure_ascii=False, indent=2)) + '</pre>'
            '<ul>' + "".join('<li>' + html.escape(reason) + '</li>' for reason in report["blockers"]) + '</ul>'
            '<label>Поиск <input id="search" type="search"></label>' + "".join(sections)
            + '<script>document.getElementById("search").addEventListener("input",e=>{const q=e.target.value.toLocaleLowerCase();'
            'document.querySelectorAll("article").forEach(a=>a.hidden=!a.textContent.toLocaleLowerCase().includes(q));});</script></html>\n')
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_dir / "review.html").write_text(page, encoding="utf-8")
    output_manifest = {"version": VERSION, "inputs": {str(path): expected for path, expected in snapshots.items()},
                       "code": {name: file_hash(source_root / name) for name in
                                ("app/records/pilot_audit.py", "app/records/pilot.py", "app/records/schema.py",
                                 "app/records/sources.py", "scripts/records_pilot_evaluate.py", "pyproject.toml")},
                       "outputs": {path.name: file_hash(path) for path in sorted(output_dir.iterdir()) if path.is_file()}}
    (output_dir / "manifest.json").write_text(json.dumps(output_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report
