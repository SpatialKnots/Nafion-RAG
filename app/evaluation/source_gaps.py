"""Offline inventory of graphics absent from text-only evidence; no OCR or gating."""

from __future__ import annotations

import hashlib
import math
from dataclasses import asdict, dataclass
from pathlib import Path

import fitz  # type: ignore[import-untyped]

from app.evaluation.context_compaction import ContextSlice, SourcePage
from app.evaluation.context_windows import RegisteredBlocks
from app.evaluation.layout_groups import ProtectedGroup

VERSION = "source_visual_gaps_v0.1"
BBox = tuple[float, float, float, float]


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _valid(box: BBox, *, positive: bool = False) -> bool:
    return (all(math.isfinite(x) for x in box) and box[0] <= box[2] and box[1] <= box[3]
            and (not positive or (box[0] < box[2] and box[1] < box[3])))


def _intersects(first: BBox, second: BBox) -> bool:
    """Bounding-box intersection including touching edges and degenerate paths."""
    return (max(first[0], second[0]) <= min(first[2], second[2])
            and max(first[1], second[1]) <= min(first[3], second[3]))


@dataclass(frozen=True)
class RegisteredLine:
    block_number: int
    page_start: int
    page_end: int
    bbox: BBox
    text: str
    text_sha256: str


@dataclass(frozen=True)
class VisualAsset:
    asset_id: str
    kind: str
    bbox: BBox
    geometry_valid: bool
    metadata: dict[str, object]
    text_overlap: str
    overlapping_line_indices: tuple[int, ...]


@dataclass(frozen=True)
class SourceGaps:
    version: str
    article_id: str
    page: int
    layer_id: str
    text_layer: str
    text_sha256: str
    original_pdf_path: str
    original_pdf_sha256: str
    selected_pdf_path: str
    selected_pdf_sha256: str
    rotation: int
    media_box: BBox
    crop_box: BBox
    page_rect: BBox
    coordinate_system: str
    text_geometry_proven: bool
    lines: tuple[RegisteredLine, ...]
    assets: tuple[VisualAsset, ...]
    diagnostics: tuple[str, ...]


def read_source_gaps(page: SourcePage, mapping: RegisteredBlocks) -> SourceGaps:
    """Keep every displayed image occurrence and drawing, including tiny pieces.

    Geometry is from the selected PDF, in unrotated PyMuPDF coordinates. Image
    pixels and vector paths are not serialized into text. Their scientific role
    and the completeness of any overlapping text are deliberately unevaluated.
    File/PDF errors propagate; text alignment failures remain explicit unknowns.
    """
    if (page.page < 1 or (mapping.article_id, mapping.page, mapping.layer_id, mapping.text_sha256)
            != (page.article_id, page.page, page.layer_id, _sha(page.text))):
        raise ValueError("Source-gap registry requires an exact registered page identity")
    path = Path(mapping.selected_pdf_path)
    if hashlib.sha256(path.read_bytes()).hexdigest() != mapping.selected_pdf_sha256:
        raise ValueError("Source-gap selected PDF hash differs from registered input")
    lines: list[RegisteredLine] = []
    diagnostics: list[str] = []
    with fitz.open(path) as document:
        if page.page > len(document):
            raise ValueError("Source-gap page is outside selected PDF")
        pdf_page = document[page.page - 1]
        cursor = 0
        extracted_blocks = []
        # Match the text/block registry flags. Preserving images here changes
        # subsequent block numbers when a raster precedes an overlaid text label.
        for block in pdf_page.get_text("dict", flags=fitz.TEXTFLAGS_TEXT)["blocks"]:
            if block["type"] != 0:
                continue
            start = cursor
            for line in block["lines"]:
                text = "".join(span["text"] for span in line["spans"]) + "\n"
                lines.append(RegisteredLine(block["number"], cursor, cursor + len(text),
                                            tuple(line["bbox"]), text, _sha(text)))
                cursor += len(text)
            extracted_blocks.append((block["number"], start, cursor, tuple(block["bbox"])))
        expected_blocks = [(b.block_number, b.page_start, b.page_end, b.bbox) for b in mapping.blocks]
        proven = (mapping.diagnostic is None and pdf_page.get_text("text") == page.text
                  and "".join(line.text for line in lines) == page.text
                  and extracted_blocks == expected_blocks and all(_valid(line.bbox, positive=True) for line in lines))
        if not proven:
            diagnostics.append("registered_line_geometry_not_proven")
            lines = []
        if mapping.diagnostic is not None:
            diagnostics.append(mapping.diagnostic)
        assets: list[VisualAsset] = []

        def append(kind: str, index: int, bbox: BBox, metadata: dict[str, object]) -> None:
            valid = _valid(bbox, positive=kind == "raster_image")
            overlaps = tuple(i for i, line in enumerate(lines) if valid and _intersects(bbox, line.bbox))
            status = "unknown" if not proven or not valid else "present" if overlaps else "none"
            assets.append(VisualAsset(f"{kind}:{index}", kind, bbox, valid, metadata, status, overlaps))
            if not valid:
                diagnostics.append(f"{kind}:{index}:invalid_asset_geometry")

        for index, image in enumerate(pdf_page.get_image_info(hashes=True, xrefs=True)):
            append("raster_image", index, tuple(image["bbox"]), {
                "occurrence_index": index, "block_number": image["number"], "xref": image["xref"],
                "width_pixels": image["width"], "height_pixels": image["height"],
                "pixel_digest_hex": image["digest"].hex(), "transform": list(image["transform"]),
                "bits_per_component": image["bpc"], "colorspace": image["cs-name"],
            })
        for index, drawing in enumerate(pdf_page.get_drawings()):
            append("vector_drawing", index, tuple(drawing["rect"]), {
                "drawing_index": index, "type": drawing["type"], "path_item_count": len(drawing["items"]),
                "sequence_number": drawing.get("seqno"),
            })
        return SourceGaps(VERSION, page.article_id, page.page, page.layer_id, page.text_layer, _sha(page.text),
            page.pdf_path, page.pdf_sha256, str(path.resolve()), mapping.selected_pdf_sha256,
            pdf_page.rotation, tuple(pdf_page.mediabox), tuple(pdf_page.cropbox), tuple(pdf_page.rect),
            "unrotated_selected_pdf_pymupdf_points", proven, tuple(lines), tuple(assets), tuple(diagnostics))


def bind_source_gaps(registry: SourceGaps, page: SourcePage, slices: list[ContextSlice],
                     groups: list[ProtectedGroup]) -> dict[str, object]:
    """Attach exact selected text and proposed caption relations; never infer relevance.

    A group bounding-box intersection is a proposal, not ownership or evidence
    that an image's scientific content is understood. Text overlap never proves
    complete OCR. No result here changes selection or grants inference approval.
    """
    if ((registry.article_id, registry.page, registry.layer_id, registry.text_sha256,
         registry.original_pdf_path, registry.original_pdf_sha256, registry.text_layer)
            != (page.article_id, page.page, page.layer_id, _sha(page.text), page.pdf_path, page.pdf_sha256, page.text_layer)):
        raise ValueError("Source-gap binding identity differs from registered page")
    selected = [s for s in slices if (s.article_id, s.page, s.layer_id) == (page.article_id, page.page, page.layer_id)]
    for span in selected:
        if not (0 <= span.page_start < span.page_end <= len(page.text)
                and _sha(page.text[span.page_start:span.page_end]) == span.text_sha256
                and (span.pdf_path, span.pdf_sha256, span.text_layer) == (page.pdf_path, page.pdf_sha256, page.text_layer)):
            raise ValueError("Source-gap binding requires exact selected source slices")
    relations: list[dict[str, object]] = []
    captions_by_asset: dict[str, set[str]] = {}
    for group in groups:
        if (group.article_id, group.page, group.layer_id) != (page.article_id, page.page, page.layer_id):
            raise ValueError("Source-gap group belongs to another page")
        if (not _valid(group.bbox, positive=True)
                or any(not 0 <= start < end <= len(page.text) for start, end in group.page_ranges)):
            raise ValueError("Source-gap group has invalid source geometry or ranges")
        caption_lines = [line for line in registry.lines if line.block_number in group.caption_blocks]
        citations = sorted({s.citation_id for s in selected for line in caption_lines
                            if max(s.page_start, line.page_start) < min(s.page_end, line.page_end)})
        assets = [a.asset_id for a in registry.assets if a.geometry_valid and _intersects(a.bbox, group.bbox)]
        for asset_id in assets:
            captions_by_asset.setdefault(asset_id, set()).update(citations)
        relations.append({"group": asdict(group), "relation": "proposal_bbox_intersection_not_ownership",
                          "asset_ids": assets, "selected_caption_citations": citations,
                          "caption_lines": [asdict(line) for line in caption_lines]})
    annotations = []
    for asset in registry.assets:
        citations = sorted({s.citation_id for i in asset.overlapping_line_indices for s in selected
            if max(s.page_start, registry.lines[i].page_start) < min(s.page_end, registry.lines[i].page_end)})
        caption_citations = sorted(captions_by_asset.get(asset.asset_id, set()))
        annotations.append({"asset_id": asset.asset_id, "overlapping_selected_line_citations": citations,
                            "proposed_caption_citations": caption_citations,
                            "representation": "pixels_not_serialized" if asset.kind == "raster_image" else "paths_not_serialized",
                            "scientific_information_loss": "not_evaluated", "text_completeness": "not_evaluated"})
    return {"selected_slices": [asdict(s) for s in selected], "group_relations": relations, "asset_annotations": annotations,
            "diagnostic_only": True, "selection_changed": False, "scientific_relevance": "not_evaluated"}
