"""Synthetic representation/provenance counterexamples, not scientific gold labels."""

import hashlib
from dataclasses import replace
from pathlib import Path

import fitz
import pytest

from app.evaluation.context_compaction import ContextSlice, SourcePage
from app.evaluation.context_windows import read_registered_blocks
from app.evaluation.layout_groups import ProtectedGroup
from app.evaluation.source_gaps import bind_source_gaps, read_source_gaps


def fixture(tmp_path, *, overlay=False, duplicate=False, tiny=False, image=True, rotation=0, crop=False, text=True):
    path = tmp_path / "graphics.pdf"
    with fitz.open() as doc:
        page = doc.new_page(width=500, height=600)
        if text:
            page.insert_text((60, 80), "Figure 1. Synthetic source")
            page.insert_text((60, 480), "Unrelated retained paragraph")
        if image:
            pixmap = fitz.Pixmap(fitz.csRGB, (0, 0, 30, 20))
            pixmap.clear_with(128)
            xref = page.insert_image(fitz.Rect(60, 130, 360, 330), pixmap=pixmap)
            if duplicate:
                page.insert_image(fitz.Rect(60, 130, 360, 330), xref=xref)
            if tiny:
                page.insert_image(fitz.Rect(400, 100, 401.5, 101), xref=xref)
        if overlay:
            # Deliberately partial synthetic overlay: no claim to read raster pixels.
            page.insert_text((80, 180), "One label only")
        page.draw_line((70, 200), (300, 200))
        page.draw_line((70, 510), (300, 510))
        if crop:
            page.set_cropbox(fitz.Rect(20, 30, 480, 570))
        page.set_rotation(rotation)
        doc.save(path)
        source_text = page.get_text("text")
    checksum = hashlib.sha256(path.read_bytes()).hexdigest()
    source = SourcePage("article", "chunk", 1, "original", "layer", source_text, str(path), checksum)
    mapping = read_registered_blocks(source, path, checksum)
    return source, mapping


def span(source, start=0, end=None):
    end = len(source.text) if end is None else end
    return ContextSlice("W1", "E1", source.chunk_id, source.article_id, source.page, source.text_layer, source.layer_id,
                        source.pdf_path, source.pdf_sha256, start, end, start, end,
                        hashlib.sha256(source.text[start:end].encode()).hexdigest())


def group(source, mapping):
    block = mapping.blocks[0]
    return ProtectedGroup("synthetic_caption_proposal", source.article_id, 1, source.layer_id, (block.block_number,),
                          (block.block_number,), ((block.page_start, block.page_end),), (50, 50, 370, 350), ())


def test_image_without_text_is_unknown_content_with_exact_caption_binding(tmp_path):
    source, mapping = fixture(tmp_path)
    before = source.pdf_sha256
    registry = read_source_gaps(source, mapping)
    image = next(a for a in registry.assets if a.kind == "raster_image")
    assert registry.text_geometry_proven and image.text_overlap == "none"
    assert image.bbox == (60, 130, 360, 330) and image.metadata["width_pixels"] == 30
    assert all(source.text[line.page_start:line.page_end] == line.text for line in registry.lines)
    selection = span(source, 0, mapping.blocks[0].page_end)
    result = bind_source_gaps(registry, source, [selection], [group(source, mapping)])
    annotation = result["asset_annotations"][0]
    assert annotation["proposed_caption_citations"] == ["W1"]
    assert annotation["overlapping_selected_line_citations"] == []
    assert annotation["representation"] == "pixels_not_serialized"
    assert annotation["scientific_information_loss"] == "not_evaluated"
    assert result["selection_changed"] is False
    assert hashlib.sha256(Path(source.pdf_path).read_bytes()).hexdigest() == before


def test_partial_text_overlay_cannot_claim_complete_text_or_ocr(tmp_path):
    source, mapping = fixture(tmp_path, overlay=True)
    registry = read_source_gaps(source, mapping)
    image = registry.assets[0]
    assert image.text_overlap == "present"
    assert [registry.lines[i].text for i in image.overlapping_line_indices] == ["One label only\n"]
    result = bind_source_gaps(registry, source, [span(source)], [])
    annotation = result["asset_annotations"][0]
    assert annotation["overlapping_selected_line_citations"] == ["W1"]
    assert annotation["text_completeness"] == "not_evaluated"


def test_duplicate_occurrences_and_tiny_pieces_are_not_filtered_or_deduplicated(tmp_path):
    source, mapping = fixture(tmp_path, duplicate=True, tiny=True)
    images = [a for a in read_source_gaps(source, mapping).assets if a.kind == "raster_image"]
    assert len(images) == 3 and len({a.asset_id for a in images}) == 3
    assert images[0].bbox == images[1].bbox and images[0].metadata["xref"] == images[1].metadata["xref"]
    assert images[2].bbox[2] - images[2].bbox[0] == 1.5


def test_vector_only_page_retains_decorative_and_diagram_paths_without_classification(tmp_path):
    source, mapping = fixture(tmp_path, image=False)
    registry = read_source_gaps(source, mapping)
    assert len(registry.assets) == 2
    assert all(a.kind == "vector_drawing" and a.geometry_valid and a.bbox[1] == a.bbox[3] for a in registry.assets)
    assert all(a.text_overlap == "none" for a in registry.assets)
    result = bind_source_gaps(registry, source, [span(source)], [])
    assert all(a["representation"] == "paths_not_serialized" for a in result["asset_annotations"])


@pytest.mark.parametrize("change", ["diagnostic", "offset", "box", "text"])
def test_unproven_line_mapping_retains_assets_with_unknown_overlap(tmp_path, change):
    source, mapping = fixture(tmp_path)
    if change == "diagnostic":
        mapping = replace(mapping, diagnostic="previous_geometry_mismatch")
    elif change == "offset":
        mapping = replace(mapping, blocks=(replace(mapping.blocks[0], page_start=1), *mapping.blocks[1:]))
    elif change == "box":
        mapping = replace(mapping, blocks=(replace(mapping.blocks[0], bbox=(0, 0, 1, 1)), *mapping.blocks[1:]))
    else:
        source = replace(source, text=source.text + "changed")
        mapping = replace(mapping, text_sha256=hashlib.sha256(source.text.encode()).hexdigest())
    registry = read_source_gaps(source, mapping)
    assert registry.assets and not registry.text_geometry_proven and not registry.lines
    assert "registered_line_geometry_not_proven" in registry.diagnostics
    assert all(a.text_overlap == "unknown" for a in registry.assets)


@pytest.mark.parametrize("change", ["hash", "article", "layer", "page_zero", "page_outside", "text_hash", "missing_file"])
def test_invalid_source_provenance_fails_explicitly(tmp_path, change):
    source, mapping = fixture(tmp_path)
    error = ValueError
    if change == "hash":
        mapping = replace(mapping, selected_pdf_sha256="incorrect")
    elif change == "article":
        mapping = replace(mapping, article_id="other")
    elif change == "layer":
        mapping = replace(mapping, layer_id="other")
    elif change in {"page_zero", "page_outside"}:
        value = 0 if change == "page_zero" else 2
        source, mapping = replace(source, page=value), replace(mapping, page=value)
    elif change == "text_hash":
        mapping = replace(mapping, text_sha256="incorrect")
    else:
        mapping = replace(mapping, selected_pdf_path=str(tmp_path / "absent.pdf"))
        error = FileNotFoundError
    with pytest.raises(error):
        read_source_gaps(source, mapping)


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_rotated_cropped_pdf_records_unrotated_coordinates_separately(tmp_path, rotation):
    source, mapping = fixture(tmp_path, rotation=rotation, crop=True)
    registry = read_source_gaps(source, mapping)
    assert registry.rotation == rotation and registry.crop_box == (20, 30, 480, 570)
    assert registry.assets[0].bbox == (40, 100, 340, 300)
    assert registry.text_geometry_proven and registry.coordinate_system == "unrotated_selected_pdf_pymupdf_points"
    assert registry.page_rect == ((0, 0, 540, 460) if rotation in {90, 270} else (0, 0, 460, 540))


def test_image_only_scan_like_page_does_not_invent_registered_text(tmp_path):
    source, mapping = fixture(tmp_path, text=False)
    registry = read_source_gaps(source, mapping)
    assert source.text == "" and registry.text_geometry_proven and registry.lines == ()
    assert registry.assets[0].text_overlap == "none"
    assert bind_source_gaps(registry, source, [], [])["selected_slices"] == []


@pytest.mark.parametrize("change", ["source", "slice_hash", "slice_bounds", "slice_pdf", "group_page", "group_bounds"])
def test_context_binding_rejects_false_provenance(tmp_path, change):
    source, mapping = fixture(tmp_path)
    registry = read_source_gaps(source, mapping)
    selected, proposal = span(source), group(source, mapping)
    if change == "source":
        source = replace(source, pdf_sha256="changed")
    elif change == "slice_hash":
        selected = replace(selected, text_sha256="changed")
    elif change == "slice_bounds":
        selected = replace(selected, page_start=-1)
    elif change == "slice_pdf":
        selected = replace(selected, pdf_sha256="changed")
    elif change == "group_page":
        proposal = replace(proposal, page=2)
    else:
        proposal = replace(proposal, page_ranges=((-1, 2),))
    with pytest.raises(ValueError):
        bind_source_gaps(registry, source, [selected], [proposal])


def test_unselected_remote_image_is_not_assigned_relevance_from_page_presence(tmp_path):
    source, mapping = fixture(tmp_path)
    registry = read_source_gaps(source, mapping)
    block = mapping.blocks[1]
    selected = span(source, block.page_start, block.page_end)
    result = bind_source_gaps(registry, source, [selected], [])
    assert result["scientific_relevance"] == "not_evaluated"
    assert all(not item["proposed_caption_citations"] and not item["overlapping_selected_line_citations"]
               for item in result["asset_annotations"])
