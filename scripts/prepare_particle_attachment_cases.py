"""Freeze predeclared markers/role annotations, never run the candidate."""

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

RECIPE = ROOT / "docs/records/particle_attachment_recipe_v0.7.json"
INSPECTION = ROOT / "output/particle_attachment_20261103/source_inspection_v02.json"
PROTOCOL = ROOT / "docs/records/particle_attachment_protocol_v0.7.md"


def prepare() -> dict[str, Any]:
    import fitz

    scan, recipe = json.loads(INSPECTION.read_bytes()), json.loads(RECIPE.read_bytes())
    files.verify(scan["bindings"])
    pages = {(p["article_id"], p["pdf_page"]): p for p in scan["pages"]}
    cases = []
    for row in recipe["cases"]:
        page = pages[row["article_id"], row["page"]]
        view = v1.matching_view(page["page_text"])
        markers = []
        for marker in (row["begin"], row["end"]):
            matches = list(re.finditer(r"\s+".join(re.escape(w) for w in marker.split()), view.text, re.I))
            if len(matches) != 1:
                raise ValueError("Ambiguous or absent frozen marker: " + row["id"] + ": " + marker)
            markers.append(matches[0])
        span = view.anchor(markers[0].start(), markers[1].end())
        with fitz.open(page["original_pdf_path"]) as pdf:
            fresh = pdf[row["page"] - 1].get_text()
        if files.sha(fresh.encode()) != page["page_text_sha256"] or span["text"] not in fresh:
            raise ValueError("Fresh PDF source differs")
        cases.append({"id": row["id"], "raw_span": span, "annotation": {k: row[k] for k in ("particle_owner", "dispersion", "note")},
                      "requested_complete": False, "page_text": page["page_text"], "page_text_sha256": page["page_text_sha256"],
                      "provenance": {k: page[k] for k in ("article_id", "title", "pdf_page", "original_pdf_path", "original_pdf_sha256")},
                      "page_diagnostics": [w for w in scan["extraction_diagnostics"]
                                           if w["article_id"] == row["article_id"] and w["pdf_page"] == row["page"]]})
    return {"version": "particle_attachment_cases_v0.7", "origin": recipe["origin"], "cases": cases,
            "pdfs": len({c["provenance"]["article_id"] for c in cases}),
            "extraction_diagnostics": scan["extraction_diagnostics"],
            "bindings": files.bindings([Path(__file__), RECIPE, INSPECTION, PROTOCOL])}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = prepare()
    files.write(args.output, result)
    print(json.dumps({"cases": len(result["cases"]), "pdfs": result["pdfs"],
                      "selected_window_diagnostics": sum(bool(c["page_diagnostics"]) for c in result["cases"])}, ensure_ascii=False))
