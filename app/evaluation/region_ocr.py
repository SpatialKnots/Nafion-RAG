"""Local, source-preserving region OCR candidates; no ingestion or answer activation."""

from __future__ import annotations

import csv
import hashlib
import io
import math
import re
import shutil
import subprocess
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

import fitz  # type: ignore[import-untyped]

from app.evaluation.context_compaction import SourcePage
from app.evaluation.context_windows import read_registered_blocks
from app.evaluation.source_gaps import BBox, SourceGaps, read_source_gaps
from app.extraction.ocr import _ocr_env

VERSION = "source_region_ocr_v0.1"
DPI = 300
CONFIDENCE_DIAGNOSTIC_CUTOFF = 50
_HEADER = "level page_num block_num par_num line_num word_num left top width height conf text".split()
_TOKENS = re.compile(r"\d+(?:[.,]\d+)?|[^\W\d_]+|[°%±*/†‡]", re.UNICODE)


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def text_sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class RenderedRegion:
    source: SourceGaps
    requested_bbox: BBox
    raster_bbox: BBox
    pixel_origin: tuple[int, int]
    width: int
    height: int
    dpi: int
    image_path: str
    image_sha256: str


@dataclass(frozen=True)
class OCREngine:
    command: str
    tessdata_dir: str
    languages: tuple[str, ...]
    version_stdout: str
    version_stderr: str
    file_hashes: dict[str, str]
    oem: int = 1
    psm: int = 11
    omp_thread_limit: int = 1


@dataclass(frozen=True)
class OCRWord:
    tsv_row: int
    layout: tuple[int, int, int, int, int]
    text: str
    raw_confidence: str
    confidence: float | None
    pixel_bbox: tuple[int, int, int, int]
    pdf_bbox: BBox


def verify_files(hashes: dict[str, str]) -> None:
    for name, checksum in hashes.items():
        if file_sha(Path(name)) != checksum:
            raise ValueError(f"Frozen file hash mismatch: {name}")


def inspect_engine(command: str, tessdata_dir: Path, languages: tuple[str, ...] = ("eng", "rus")) -> OCREngine:
    resolved = shutil.which(command, path=_ocr_env().get("PATH"))
    if resolved is None:
        raise RuntimeError(f"Region OCR command not found: {command}")
    if not languages or len(set(languages)) != len(languages) or any(not re.fullmatch(r"[a-z_]+", x) for x in languages):
        raise ValueError("Region OCR languages must be distinct traineddata names")
    executable = Path(resolved).resolve()
    data = tessdata_dir.resolve()
    files = [executable, *sorted(executable.parent.glob("*.dll")), *(data / (lang + ".traineddata") for lang in languages)]
    hashes = {str(path): file_sha(path) for path in files}
    result = subprocess.run([str(executable), "--version"], check=False, capture_output=True, timeout=30, env=_ocr_env())
    if result.returncode:
        raise RuntimeError("Region OCR version command failed: " + result.stderr.decode("utf-8", errors="replace"))
    return OCREngine(str(executable), str(data), languages, result.stdout.decode("utf-8"), result.stderr.decode("utf-8"), hashes)


def render_region(source: SourceGaps, bbox: BBox, output: Path) -> RenderedRegion:
    """Render a copy after reproving the frozen source registry; never edit PDFs."""
    if not all(math.isfinite(x) for x in bbox) or not (bbox[0] < bbox[2] and bbox[1] < bbox[3]):
        raise ValueError("Region rectangle must be finite and positive")
    verify_files({source.original_pdf_path: source.original_pdf_sha256})
    selected = Path(source.selected_pdf_path)
    verify_files({str(selected): source.selected_pdf_sha256})
    with fitz.open(selected) as document:
        if not 1 <= source.page <= len(document):
            raise ValueError("Region page is outside selected PDF")
        page = document[source.page - 1]
        text = page.get_text("text")
        registered = SourcePage(source.article_id, "source_registry_verification", source.page, source.text_layer,
                                source.layer_id, text, source.original_pdf_path, source.original_pdf_sha256)
        mapping = read_registered_blocks(registered, selected, source.selected_pdf_sha256)
        if source != read_source_gaps(registered, mapping):
            raise ValueError("Region source-gap registry differs from current exact source")
        if page.rotation != 0:
            raise ValueError("Region OCR v0.1 does not support rotated pages")
        if not page.rect.contains(fitz.Rect(bbox)):
            raise ValueError("Region rectangle is outside the visible selected page")
        pixmap = page.get_pixmap(matrix=fitz.Matrix(DPI / 72, DPI / 72), clip=fitz.Rect(bbox),
                                 colorspace=fitz.csRGB, alpha=False)
        output.mkdir(parents=True, exist_ok=False)
        path = output / "source.png"
        pixmap.set_dpi(DPI, DPI)
        pixmap.save(path)
        scale = DPI / 72
        raster_bbox = (pixmap.x / scale, pixmap.y / scale, (pixmap.x + pixmap.width) / scale,
                       (pixmap.y + pixmap.height) / scale)
        return RenderedRegion(source, bbox, raster_bbox, (pixmap.x, pixmap.y), pixmap.width, pixmap.height,
                              DPI, str(path.resolve()), file_sha(path))


def parse_tsv(raw: str, rendered: RenderedRegion) -> list[OCRWord]:
    reader = csv.DictReader(io.StringIO(raw), delimiter="\t", quoting=csv.QUOTE_NONE)
    if reader.fieldnames != _HEADER:
        raise ValueError("Region OCR TSV header differs from declared schema")
    words = []
    scale = rendered.dpi / 72
    for row in reader:
        index = reader.line_num
        if None in row or any(value is None for value in row.values()):
            raise ValueError(f"Region OCR TSV field count mismatch at row {index}")
        level = int(row["level"])
        layout = tuple(int(row[name]) for name in _HEADER[1:6])
        if level not in range(1, 6) or layout[0] != 1 or any(x < 0 for x in layout):
            raise ValueError(f"Region OCR TSV layout invalid at row {index}")
        if level != 5:
            continue
        left, top, width, height = (int(row[name]) for name in ("left", "top", "width", "height"))
        confidence = float(row["conf"])
        if not math.isfinite(confidence) or (confidence != -1 and not 0 <= confidence <= 100):
            raise ValueError(f"Region OCR TSV confidence invalid at row {index}")
        if min(left, top, width, height) < 0 or left + width > rendered.width or top + height > rendered.height:
            raise ValueError(f"Region OCR TSV word outside raster at row {index}")
        box = ((rendered.pixel_origin[0] + left) / scale, (rendered.pixel_origin[1] + top) / scale,
               (rendered.pixel_origin[0] + left + width) / scale, (rendered.pixel_origin[1] + top + height) / scale)
        words.append(OCRWord(index, (layout[0], layout[1], layout[2], layout[3], layout[4]), row["text"], row["conf"],
                             None if confidence == -1 else confidence, (left, top, left + width, top + height), box))
    return words


def native_comparison(rendered: RenderedRegion, text: str) -> dict[str, object]:
    box = fitz.Rect(rendered.requested_bbox)
    lines = [{**asdict(line), "fully_inside_requested_region": box.contains(fitz.Rect(line.bbox))}
             for line in rendered.source.lines if box.intersects(fitz.Rect(line.bbox))]
    native = "".join(str(line["text"]) for line in lines)
    native_tokens = Counter(x.group().casefold() for x in _TOKENS.finditer(native))
    ocr_tokens = Counter(x.group().casefold() for x in _TOKENS.finditer(text))
    return {"native_lines": lines, "native_text": native,
            "status": "discrepancy_diagnostic_only" if native else "unavailable_no_native_text",
            "native_tokens_absent_from_ocr": dict(native_tokens - ocr_tokens) if native else None,
            "ocr_tokens_absent_from_native": dict(ocr_tokens - native_tokens) if native else None,
            "native_text_is_scientific_gold": False, "scientific_accuracy": "not_evaluated"}


def run_region_ocr(rendered: RenderedRegion, engine: OCREngine, *, timeout_seconds: int = 120) -> dict[str, object]:
    """Save raw process evidence before parsing. Errors propagate without retry."""
    if file_sha(Path(rendered.image_path)) != rendered.image_sha256:
        raise ValueError("Region OCR image hash differs from frozen render")
    verify_files(engine.file_hashes)
    folder = Path(rendered.image_path).parent
    if any((folder / name).exists() for name in ("ocr.txt", "ocr.tsv", "process.json", "stdout.bin", "stderr.bin")):
        raise FileExistsError("Region OCR output already exists; use a fresh region directory")
    args = [engine.command, rendered.image_path, str(folder / "ocr"), "--tessdata-dir", engine.tessdata_dir,
            "-l", "+".join(engine.languages), "--oem", str(engine.oem), "--psm", str(engine.psm),
            "--dpi", str(rendered.dpi), "-c", "tessedit_create_tsv=1", "-c", "tessedit_create_txt=1"]
    env = _ocr_env()
    env["OMP_THREAD_LIMIT"] = str(engine.omp_thread_limit)
    process: dict[str, object] = {"arguments": args, "timeout_seconds": timeout_seconds,
                                  "omp_thread_limit": engine.omp_thread_limit, "status": "started"}
    try:
        completed = subprocess.run(args, check=False, capture_output=True, env=env, timeout=timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        (folder / "stdout.bin").write_bytes(exc.stdout or b"")
        (folder / "stderr.bin").write_bytes(exc.stderr or b"")
        process.update(status="timeout", returncode=None)
        (folder / "process.json").write_text(json_dump(process), encoding="utf-8")
        raise RuntimeError(f"Region OCR timed out after {timeout_seconds} seconds") from exc
    except OSError as exc:
        process.update(status="launch_failed", error=str(exc))
        (folder / "process.json").write_text(json_dump(process), encoding="utf-8")
        raise
    (folder / "stdout.bin").write_bytes(completed.stdout)
    (folder / "stderr.bin").write_bytes(completed.stderr)
    process.update(status="completed" if completed.returncode == 0 else "failed", returncode=completed.returncode)
    (folder / "process.json").write_text(json_dump(process), encoding="utf-8")
    if completed.returncode:
        raise RuntimeError(f"Region OCR failed with exit code {completed.returncode}; see saved stderr.bin")
    text_path, tsv_path = folder / "ocr.txt", folder / "ocr.tsv"
    # read_bytes + strict decode keeps original CR/LF; Path.read_text would normalize it.
    text = text_path.read_bytes().decode("utf-8")
    words = parse_tsv(tsv_path.read_bytes().decode("utf-8"), rendered)
    verify_files(engine.file_hashes)
    if file_sha(Path(rendered.image_path)) != rendered.image_sha256:
        raise ValueError("Region OCR changed its source image")
    diagnostics = {"confidence_cutoff_diagnostic_only": CONFIDENCE_DIAGNOSTIC_CUTOFF,
        "low_confidence_tsv_rows": [w.tsv_row for w in words if w.confidence is not None
                                    and w.confidence < CONFIDENCE_DIAGNOSTIC_CUTOFF],
        "unavailable_confidence_tsv_rows": [w.tsv_row for w in words if w.confidence is None],
        "empty_word_tsv_rows": [w.tsv_row for w in words if not w.text], "empty_text": not text.strip(),
        "scientific_acceptance": "not_evaluated", "automatic_promotion": False}
    return {"version": VERSION, "status": "candidate_only", "render": asdict(rendered), "engine": asdict(engine),
            "text": text, "text_sha256": text_sha(text), "words": [asdict(w) for w in words],
            "native_comparison": native_comparison(rendered, text), "diagnostics": diagnostics,
            "artifact_hashes": {str(p.resolve()): file_sha(p) for p in
                                (text_path, tsv_path, folder / "stdout.bin", folder / "stderr.bin", folder / "process.json")}}


def json_dump(value: object) -> str:
    import json

    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)
