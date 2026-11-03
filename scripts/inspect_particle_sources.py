"""Read-only inspection of frozen original PDFs; no production search/provider."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import cross_lingual_relation_audit as v1  # noqa: E402
from scripts import gigachat_answer_smoke as files  # noqa: E402

PREVIOUS = ROOT / "output/source_reference_chain_20261103/review_v06"


def inspect() -> dict[str, Any]:
    import fitz

    files.verify_manifest(PREVIOUS)
    report = json.loads((PREVIOUS / "report.json").read_bytes())
    files.verify(report["bindings"])
    pages, total, diagnostics = [], 0, []
    fitz.TOOLS.mupdf_warnings()
    for article in report["articles"]:
        path = Path(article["original_pdf_path"])
        if files.sha(path.read_bytes()) != article["original_pdf_sha256"]:
            raise ValueError("Frozen original PDF changed")
        with fitz.open(path) as pdf:
            for index, page in enumerate(pdf):
                total += 1
                raw = page.get_text()
                warning = fitz.TOOLS.mupdf_warnings()
                if warning:
                    diagnostics.append({"article_id": article["article_id"], "title": article["title"],
                                        "pdf_page": index + 1, "mupdf_diagnostics": warning})
                text = v1.matching_view(raw).text
                if (re.search(v1.TARGET, text, re.I) and re.search(r"morpholog\w*|морфолог\w*|shapes?", text, re.I)
                        and re.search(v1.PARTICLE + "|" + v1.DISPERSION, text, re.I)):
                    pages.append({"article_id": article["article_id"], "title": article["title"], "pdf_page": index + 1,
                                  "original_pdf_path": str(path), "original_pdf_sha256": article["original_pdf_sha256"],
                                  "page_text": raw, "page_text_sha256": files.sha(raw.encode())})
    return {"version": "particle_source_inspection_v0.7", "selection": "all frozen pages: target + morphology/shape + particle/dispersion",
            "pages_scanned": total, "pdfs_scanned": len(report["articles"]), "pages": pages, "extraction_diagnostics": diagnostics,
            "bindings": files.bindings([Path(__file__), PREVIOUS / "report.json", PREVIOUS / "manifest.json"])}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result = inspect()
    files.write(args.output, result)
    print(json.dumps({"pages_scanned": result["pages_scanned"], "pdfs_scanned": result["pdfs_scanned"],
                      "matching_pages": len(result["pages"]),
                      "inventory": [{"title": p["title"], "page": p["pdf_page"]} for p in result["pages"]]},
                     ensure_ascii=False, indent=2))
