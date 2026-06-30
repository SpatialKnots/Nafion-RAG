from __future__ import annotations

import shutil
from pathlib import Path


def stable_pdf_name(checksum_sha256: str, source_path: Path) -> str:
    suffix = source_path.suffix.lower() or ".pdf"
    stem = source_path.stem.strip().replace(" ", "_")[:80] or "document"
    return f"{checksum_sha256[:16]}_{stem}{suffix}"


def copy_original_pdf(source_path: Path, data_root: Path, checksum_sha256: str) -> Path:
    if source_path.suffix.lower() != ".pdf":
        raise ValueError(f"Only PDF files are supported in phase 1: {source_path}")
    target_dir = data_root / "pdf"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / stable_pdf_name(checksum_sha256, source_path)
    if not target_path.exists():
        shutil.copy2(source_path, target_path)
    return target_path


def ocr_pdf_path(source_path: Path, data_root: Path, checksum_sha256: str) -> Path:
    target_dir = data_root / "processed" / "ocr"
    return target_dir / stable_pdf_name(checksum_sha256, source_path)
