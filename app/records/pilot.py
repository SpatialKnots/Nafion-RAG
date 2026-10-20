"""Immutable source-only pilot packets; neither annotations nor scientific gold."""

from __future__ import annotations

import html
import json
import platform
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from app.records.schema import CandidateBundle, text_hash
from app.records.sources import file_hash

PILOT_VERSION = "records_pilot_source_packet_v0.1"
PRIORITIES = {"li_nafion_and_conductivity_in_chunk", "li_nafion_mention", "no_anchor"}


@dataclass(frozen=True)
class PilotDocument:
    article_id: UUID
    title: str | None
    doi: str | None
    original_pdf_path: str
    original_pdf_sha256: str
    pdf_page_count: int
    stored_page_numbers: tuple[int, ...]
    bundle: CandidateBundle | None
    diagnostics: tuple[str, ...] = ()

    def validate(self) -> None:
        if self.pdf_page_count < 1:
            raise ValueError("Original PDF must contain pages")
        if len(set(self.stored_page_numbers)) != len(self.stored_page_numbers):
            raise ValueError("Duplicate stored page")
        if any(page < 1 or page > self.pdf_page_count for page in self.stored_page_numbers):
            raise ValueError("Stored page outside original PDF")
        if self.bundle is not None:
            if self.bundle.records:
                raise ValueError("Source-only packet must not contain candidate records")
            pages = [region.page_number for region in self.bundle.regions]
            if len(set(pages)) != len(pages):
                raise ValueError("Duplicate exported page")
            for region in self.bundle.regions:
                if region.article_id != self.article_id or region.original_pdf_sha256 != self.original_pdf_sha256:
                    raise ValueError("Exported region belongs to different article/PDF")
                if region.original_pdf_path != self.original_pdf_path:
                    raise ValueError("Exported original PDF path differs from document")
                if region.page_number not in self.stored_page_numbers:
                    raise ValueError("Exported page is not a stored page")
                if region.start != 0 or region.end != len(region.page_text) or region.quote != region.page_text:
                    raise ValueError("Source-only packet requires complete stored pages")
            omitted = set(self.stored_page_numbers) - set(pages)
        else:
            omitted = set(self.stored_page_numbers)
        for page in omitted:
            if f"empty_selected_page:{page}" not in self.diagnostics:
                raise ValueError("Unexported stored page requires an explicit empty-page diagnostic")
        for page in set(range(1, self.pdf_page_count + 1)) - set(self.stored_page_numbers):
            if f"missing_stored_page:{page}" not in self.diagnostics:
                raise ValueError("Missing original-PDF page requires a diagnostic")


def selection_audit(profile: dict[str, Any], documents: tuple[PilotDocument, ...]) -> dict[str, Any]:
    """Retain lexical shortlist separately; do not turn no-hit cases into negatives."""
    if profile.get("schema_version") != 1 or not isinstance(profile.get("articles"), list):
        raise ValueError("Expected lexical corpus profile schema_version 1")
    rows = profile["articles"]
    identifiers = [UUID(row["article_id"]) for row in rows]
    if len(set(identifiers)) != len(identifiers) or set(identifiers) != {doc.article_id for doc in documents}:
        raise ValueError("Profile and source packet must account for identical document IDs")
    documents_by_id = {doc.article_id: doc for doc in documents}
    candidates: list[str] = []
    no_hits: list[str] = []
    for row in rows:
        identifier = UUID(row["article_id"])
        if row["pdf_sha256"] != documents_by_id[identifier].original_pdf_sha256:
            raise ValueError("Profile original PDF differs from exported source")
        priority = row["candidate_priority"]
        if priority not in PRIORITIES:
            raise ValueError(f"Unknown profile selection priority: {priority}")
        (no_hits if priority == "no_anchor" else candidates).append(str(identifier))
    return {
        "selection_status": "lexical_candidates_not_scientific_eligibility",
        "target_publications": {"minimum": 10, "maximum": 15},
        "lexical_candidate_ids": sorted(candidates),
        "lexical_candidate_count": len(candidates),
        "lexical_candidate_shortfall_to_ten": max(0, 10 - len(candidates)),
        "documents_without_lexical_hit": sorted(no_hits),
        "scientifically_eligible_publications": None,
        "annotation_status": "not_annotated",
        "split": "development_only_no_untouched_evaluation",
        "limitations": profile.get("limitations", []),
    }


def source_content(documents: tuple[PilotDocument, ...]) -> list[dict[str, Any]]:
    """Repeatable source payload excludes run timestamps and random run IDs."""
    return [
        {
            "article_id": str(doc.article_id), "title": doc.title, "doi": doc.doi,
            "original_pdf_path": doc.original_pdf_path, "original_pdf_sha256": doc.original_pdf_sha256,
            "pdf_page_count": doc.pdf_page_count, "stored_page_numbers": list(doc.stored_page_numbers),
            "regions": [region.model_dump(mode="json") for region in doc.bundle.regions] if doc.bundle else [],
            "diagnostics": list(doc.diagnostics),
        }
        for doc in sorted(documents, key=lambda item: str(item.article_id))
    ]


def render_source_html(documents: tuple[PilotDocument, ...], fingerprint: str) -> str:
    blocks = []
    for doc in sorted(documents, key=lambda item: str(item.article_id)):
        pdf_uri = Path(doc.original_pdf_path).resolve().as_uri()
        title = doc.title or "Название отсутствует в БД"
        pages = []
        for region in doc.bundle.regions if doc.bundle else ():
            pages.append(
                '<details class="page"><summary>'
                f'Страница {region.page_number} · {html.escape(region.text_layer)}</summary>'
                f'<p><a href="{html.escape(pdf_uri, quote=True)}#page={region.page_number}">Оригинал: страница '
                f'{region.page_number}</a> · region ID: <code>{region.region_id}</code></p>'
                f'<p>Text layer ID: <code>{region.text_layer_id}</code> · '
                f'page text SHA-256: <code>{region.page_text_sha256}</code><br>'
                f'Layer PDF: {html.escape(region.layer_pdf_path)} · SHA-256: <code>{region.layer_pdf_sha256}</code></p>'
                f'<pre>{html.escape(region.quote)}</pre></details>'
            )
        diagnostics = "; ".join(doc.diagnostics) or "Пропуски страниц не обнаружены"
        blocks.append(
            '<article class="document">'
            f'<h2>{html.escape(title)}</h2><p>Article ID: <code>{doc.article_id}</code> · '
            f'DOI: {html.escape(doc.doi or "не указан в БД")}</p>'
            f'<p><a href="{html.escape(pdf_uri, quote=True)}">Оригинальный PDF</a> · '
            f'{doc.pdf_page_count} страниц в PDF / {len(doc.stored_page_numbers)} в хранилище</p>'
            f'<p>PDF SHA-256: <code>{doc.original_pdf_sha256}</code></p>'
            f'<p class="diagnostic">Диагностика: {html.escape(diagnostics)}</p>'
            + "".join(pages) + '</article>'
        )
    return '''<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ARIADNE — source-only corpus для пилота записей</title>
<style>body{font:16px/1.5 system-ui,sans-serif;max-width:1120px;margin:24px auto;padding:0 18px;color:#20312f}
input{font:inherit;padding:10px;width:100%;box-sizing:border-box}article{border-top:1px solid #bbc9c2;margin-top:24px}
h2{font-size:21px}details{margin:10px 0;padding:10px;background:#f3f6f4}summary{cursor:pointer}
pre{white-space:pre-wrap;overflow-wrap:anywhere;font:14px/1.6 ui-monospace,monospace}
code{overflow-wrap:anywhere}a{color:#245743}.diagnostic{color:#614321}[hidden]{display:none!important}</style></head><body>
<h1>Li-Nafion: исходный корпус пилота записей</h1>
<p>Только источники. Нет аннотаций, предложений записей, модельных ответов или подтверждённых научных значений.
Этот development корпус не является независимым gold или untouched evaluation.</p>
''' + f'<p>{len(documents)} документов · версия {PILOT_VERSION} · source fingerprint: <code>{fingerprint}</code></p>' + '''
<p>Каждая страница раскрывает полный сохранённый текст выбранного слоя. OCR, пустые страницы и отсутствующие страницы
не исправлены. Ссылки открывают локальные исходные PDF. Названия и DOI — текущие значения БД.</p>
<label for="search">Поиск документов по названию или article ID</label><input id="search" type="search">
<p id="count" aria-live="polite"></p>
''' + "".join(blocks) + '''<script>
const input=document.getElementById('search');
const docs=[...document.querySelectorAll('.document')];
function filter(){const query=input.value.toLocaleLowerCase();let count=0;
for(const doc of docs){doc.hidden=!doc.querySelector('h2').textContent.toLocaleLowerCase().includes(query)&&
!doc.querySelector('p').textContent.toLocaleLowerCase().includes(query);if(!doc.hidden)count++;}
document.getElementById('count').textContent='Документов: '+count+' / '+docs.length;}
input.addEventListener('input',filter);filter();</script></body></html>'''


def write_pilot_packet(
    documents: tuple[PilotDocument, ...], profile_path: Path, destination: Path,
    *, protocol_path: Path, baseline_manifest_path: Path, source_root: Path,
) -> dict[str, Any]:
    if not documents or len({doc.article_id for doc in documents}) != len(documents):
        raise ValueError("Pilot requires nonempty, distinct documents")
    for doc in documents:
        doc.validate()
    profile_raw = profile_path.read_bytes()
    audit = selection_audit(json.loads(profile_raw), documents)
    baseline_raw = baseline_manifest_path.read_bytes()
    baseline = json.loads(baseline_raw)
    protocol_raw = protocol_path.read_bytes()
    content = source_content(documents)
    fingerprint = text_hash(json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    destination.mkdir(parents=True, exist_ok=False)
    (destination / "sources").mkdir()
    (destination / "profile.json").write_bytes(profile_raw)
    (destination / "protocol.md").write_bytes(protocol_raw)
    (destination / "baseline_manifest.json").write_bytes(baseline_raw)
    for doc in documents:
        if doc.bundle:
            (destination / "sources" / f"{doc.article_id}.json").write_text(
                doc.bundle.model_dump_json(indent=2) + "\n", encoding="utf-8",
            )
    (destination / "source_inventory.json").write_text(json.dumps(content, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (destination / "selection_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (destination / "ARIADNE_records_source_only.html").write_text(render_source_html(documents, fingerprint), encoding="utf-8")
    root = source_root.resolve()
    paths = sorted((root / "app" / "records").glob("*.py")) + [
        root / "scripts" / "records_pilot.py", root / "scripts" / "profile_li_nafion.py", root / "pyproject.toml",
    ]
    code = {path.relative_to(root).as_posix(): file_hash(path) for path in paths}
    artifacts = {path.relative_to(destination).as_posix(): file_hash(path) for path in sorted(destination.rglob("*")) if path.is_file()}
    manifest = {
        "schema_version": PILOT_VERSION, "created_at": datetime.now(UTC).isoformat(),
        "source_fingerprint": fingerprint, "baseline_fingerprint": baseline["source_fingerprint"],
        "inputs": {"profile_sha256": text_hash(profile_raw.decode("utf-8")),
                   "protocol_sha256": text_hash(protocol_raw.decode("utf-8")),
                   "baseline_manifest_sha256": text_hash(baseline_raw.decode("utf-8"))},
        "code_sha256": code, "python": platform.python_version(), "artifacts_sha256": artifacts,
        "documents": len(documents), "pdf_pages": sum(doc.pdf_page_count for doc in documents),
        "stored_pages": sum(len(doc.stored_page_numbers) for doc in documents),
        "exported_regions": sum(len(doc.bundle.regions) if doc.bundle else 0 for doc in documents),
        "document_diagnostics": {str(doc.article_id): list(doc.diagnostics) for doc in documents if doc.diagnostics},
        "candidate_records": 0, "annotations": 0, "scientific_admission": "not_evaluated",
        "independent_gold": False, "split": audit["split"],
        "lexical_candidate_count": audit["lexical_candidate_count"],
        "limitations": ["Private source-only corpus; not a public release or scientific reference.",
                        "Full stored selected pages, not a new extraction/OCR pass.",
                        "No scientific eligibility, record quality or independent accuracy measured."],
    }
    (destination / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest
