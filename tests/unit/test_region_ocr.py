"""Region provenance, exact pixels/raw outputs, and OCR failure counterexamples."""

import subprocess
from dataclasses import replace
from pathlib import Path

import fitz
import pytest

from app.evaluation import region_ocr
from app.evaluation.context_compaction import SourcePage
from app.evaluation.context_windows import read_registered_blocks
from app.evaluation.region_ocr import (
    OCREngine,
    file_sha,
    inspect_engine,
    native_comparison,
    parse_tsv,
    render_region,
    run_region_ocr,
)
from app.evaluation.source_gaps import read_source_gaps

HEADER = "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
WORD = "5\t1\t1\t1\t1\t1\t10\t20\t40\t15\t95.25\tNafion\n"


def fixture(tmp_path, rotation=0):
    path = tmp_path / "source.pdf"
    with fitz.open() as doc:
        page = doc.new_page(width=400, height=300)
        page.insert_text((60, 70), "Nafion 30 C 1.25 mS/cm")
        page.insert_text((60, 150), "* Note: 40 C")
        page.set_rotation(rotation)
        doc.save(path)
        text = page.get_text("text")
    source = SourcePage("article", "chunk", 1, "original", "layer", text, str(path), file_sha(path))
    return read_source_gaps(source, read_registered_blocks(source, path, source.pdf_sha256))


def render(tmp_path):
    source = fixture(tmp_path)
    return render_region(source, (50.13, 40.27, 300.19, 180.31), tmp_path / "region")


def engine():
    return OCREngine("synthetic-test-engine", "synthetic-data", ("eng", "rus"), "synthetic", "", {})


def test_fractional_crop_uses_actual_pixel_origin_and_retains_original_pdf(tmp_path):
    rendered = render(tmp_path)
    assert rendered.source.original_pdf_sha256 == file_sha(Path(rendered.source.original_pdf_path))
    assert rendered.raster_bbox != rendered.requested_bbox
    assert rendered.raster_bbox[0] == rendered.pixel_origin[0] / (300 / 72)
    pixmap = fitz.Pixmap(rendered.image_path)
    assert (pixmap.width, pixmap.height, pixmap.xres, pixmap.yres) == (rendered.width, rendered.height, 300, 300)
    word = parse_tsv(HEADER + WORD, rendered)[0]
    assert word.pdf_bbox[0] == (rendered.pixel_origin[0] + 10) / (300 / 72)
    assert word.pixel_bbox == (10, 20, 50, 35) and word.text == "Nafion" and word.tsv_row == 2


@pytest.mark.parametrize("change", ["source_hash", "selected_hash", "line", "page_zero", "page_outside",
                                  "bbox_nan", "bbox_inverted", "bbox_outside", "rotation"])
def test_render_rejects_false_provenance_or_unsupported_geometry(tmp_path, change):
    source = fixture(tmp_path, rotation=90 if change == "rotation" else 0)
    box = (50, 40, 300, 180)
    if change == "source_hash":
        source = replace(source, original_pdf_sha256="incorrect")
    elif change == "selected_hash":
        source = replace(source, selected_pdf_sha256="incorrect")
    elif change == "line":
        source = replace(source, lines=(replace(source.lines[0], text="tampered"), *source.lines[1:]))
    elif change in {"page_zero", "page_outside"}:
        source = replace(source, page=0 if change == "page_zero" else 2)
    elif change == "bbox_nan":
        box = (float("nan"), 40, 300, 180)
    elif change == "bbox_inverted":
        box = (300, 40, 50, 180)
    elif change == "bbox_outside":
        box = (50, 40, 500, 180)
    with pytest.raises(ValueError):
        render_region(source, box, tmp_path / "candidate")
    assert not (tmp_path / "candidate").exists()


@pytest.mark.parametrize("field,value", [
    ("page_num", "2"), ("left", "-1"), ("width", "100000"), ("height", "-3"),
    ("conf", "nan"), ("conf", "inf"), ("conf", "101"), ("conf", "-2"),
    ("word_num", "-1"), ("level", "6"), ("left", "1.5"),
])
def test_invalid_tsv_fails_instead_of_dropping_words(tmp_path, field, value):
    rendered = render(tmp_path)
    names = HEADER.strip().split("\t")
    parts = WORD.rstrip("\n").split("\t")
    parts[names.index(field)] = value
    with pytest.raises(ValueError):
        parse_tsv(HEADER + "\t".join(parts) + "\n", rendered)


@pytest.mark.parametrize("raw", ["wrong\theader\n", HEADER + WORD.replace("\tNafion", ""), HEADER + WORD.rstrip() + "\textra\n"])
def test_tsv_schema_errors_are_not_repaired(tmp_path, raw):
    with pytest.raises(ValueError):
        parse_tsv(raw, render(tmp_path))


def test_empty_low_and_unavailable_confidence_words_and_physical_row_numbers_survive(tmp_path):
    rendered = render(tmp_path)
    words = parse_tsv(HEADER + "\n" + WORD.replace("95.25", "0")
                      + WORD.replace("95.25", "-1").replace("Nafion", ""), rendered)
    assert words[0].tsv_row == 3 and words[0].confidence == 0
    assert words[1].text == "" and words[1].confidence is None and words[1].raw_confidence == "-1"


def test_raw_text_bytes_words_and_discrepancies_remain_separate_candidates(tmp_path, monkeypatch):
    rendered = render(tmp_path)
    raw_text = b"Nafion\r\n125 mS/cm\r\n"
    def fake_run(args, **kwargs):
        assert kwargs["env"]["OMP_THREAD_LIMIT"] == "1"
        assert args[args.index("--psm") + 1] == "11"
        Path(args[2] + ".txt").write_bytes(raw_text)
        Path(args[2] + ".tsv").write_bytes((HEADER + WORD.replace("95.25", "20")).encode())
        return subprocess.CompletedProcess(args, 0, b"raw stdout", b"raw stderr")
    monkeypatch.setattr(region_ocr.subprocess, "run", fake_run)
    result = run_region_ocr(rendered, engine())
    assert result["text"].encode() == raw_text and result["status"] == "candidate_only"
    assert result["diagnostics"]["low_confidence_tsv_rows"] == [2]
    assert result["diagnostics"]["automatic_promotion"] is False
    comparison = result["native_comparison"]
    assert comparison["native_tokens_absent_from_ocr"]["1.25"] == 1
    assert comparison["native_tokens_absent_from_ocr"]["*"] == 1
    assert comparison["native_text_is_scientific_gold"] is False
    assert (Path(rendered.image_path).parent / "stderr.bin").read_bytes() == b"raw stderr"
    with pytest.raises(FileExistsError):
        run_region_ocr(rendered, engine())


@pytest.mark.parametrize("failure", ["timeout", "exit", "missing_output", "launch", "malformed_tsv"])
def test_process_failures_preserve_diagnostics_and_propagate(tmp_path, monkeypatch, failure):
    rendered = render(tmp_path)
    def fake_run(args, **kwargs):
        if failure == "timeout":
            raise subprocess.TimeoutExpired(args, 120, output=b"partial", stderr=b"timeout detail")
        if failure == "launch":
            raise OSError("synthetic launch failure")
        if failure == "malformed_tsv":
            Path(args[2] + ".txt").write_bytes(b"text")
            Path(args[2] + ".tsv").write_bytes(b"bad header")
        return subprocess.CompletedProcess(args, 7 if failure == "exit" else 0, b"stdout", b"stderr")
    monkeypatch.setattr(region_ocr.subprocess, "run", fake_run)
    with pytest.raises((RuntimeError, OSError, ValueError)):
        run_region_ocr(rendered, engine())
    folder = Path(rendered.image_path).parent
    assert (folder / "process.json").is_file()
    if failure != "launch":
        assert (folder / "stderr.bin").read_bytes() == (b"timeout detail" if failure == "timeout" else b"stderr")
    assert file_sha(Path(rendered.source.original_pdf_path)) == rendered.source.original_pdf_sha256


def test_mutated_render_or_engine_input_prevents_process_launch(tmp_path, monkeypatch):
    rendered = render(tmp_path)
    def forbidden(*args, **kwargs):
        pytest.fail("OCR must not launch after input hash mismatch")
    monkeypatch.setattr(region_ocr.subprocess, "run", forbidden)
    with pytest.raises(ValueError):
        run_region_ocr(rendered, replace(engine(), file_hashes={rendered.image_path: "wrong"}))
    Path(rendered.image_path).write_bytes(b"changed image")
    with pytest.raises(ValueError):
        run_region_ocr(rendered, engine())


def test_no_native_text_is_unavailable_comparison_not_false_perfect_match(tmp_path):
    rendered = render(tmp_path)
    result = native_comparison(replace(rendered, source=replace(rendered.source, lines=())), "125 mS/cm")
    assert result["status"] == "unavailable_no_native_text" and result["native_tokens_absent_from_ocr"] is None


def test_partial_native_line_keeps_exact_source_text_and_diagnostic(tmp_path):
    rendered = render(tmp_path)
    comparison = native_comparison(replace(rendered, requested_bbox=(65, 40, 80, 100)), "Nafion")
    assert comparison["native_lines"][0]["fully_inside_requested_region"] is False
    assert comparison["native_text"] == rendered.source.lines[0].text


def test_engine_missing_or_invalid_language_configuration_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(region_ocr.shutil, "which", lambda *args, **kwargs: None)
    with pytest.raises(RuntimeError, match="command not found"):
        inspect_engine("missing-tesseract", tmp_path)
    monkeypatch.setattr(region_ocr.shutil, "which", lambda *args, **kwargs: "synthetic")
    with pytest.raises(ValueError, match="distinct traineddata"):
        inspect_engine("tesseract", tmp_path, ("eng", "eng"))
