"""Bind visually reviewed capacity minus and four chemical-name ligatures to exact PDFs."""

from __future__ import annotations

import json
from pathlib import Path

import fitz

from scripts import gigachat_answer_smoke as f

BASE = f.ROOT / "output/answer_priorities_20261111"
SOURCES = f.ROOT / "output/answer_series_live_20261111/prepared_v01"


def main():
    f.verify_manifest(BASE / "pdf_probe_v01")
    pages = json.loads((BASE / "pdf_probe_v01/pages.json").read_bytes())
    fixtures = {}
    for cid in ("Kondo_04", "Nambu_10", "Peng_01"):
        fixtures[cid] = {key: json.loads((SOURCES / cid / (name + ".json")).read_bytes()) for key, name in
                         (("api", "api_request"), ("trace", "trace"))}
    fixture = f.ROOT / "tests/fixtures/answer_completeness_source_v01.json"
    f.write(fixture, fixtures)
    out = BASE / "catalogue_audit_v01"
    out.mkdir()
    results = []
    for cid, label, resource in (
        ("Nambu_10", "Nambu", "reviewed_capacity_film_glyph_aliases_v01.json"),
        ("Peng_01", "Peng", "reviewed_formulation_identity_glyph_aliases_v01.json"),
    ):
        page_info = next(p for p in pages if p["name"] == label)
        source = next(e for e in fixtures[cid]["trace"]["evidence"] if e["citation_id"] == ("E2" if label == "Nambu" else "E1"))
        pdf = Path(page_info["pdf"])
        if f.sha(pdf.read_bytes()) != page_info["sha256"]:
            raise ValueError("Original visually reviewed PDF changed")
        operations = []
        with fitz.open(pdf) as doc:
            page = doc[page_info["page"] - 1]
            text = page.get_text()
            if text != (BASE / "pdf_probe_v01" / (label + ".txt")).read_text(encoding="utf-8"):
                raise ValueError("Fresh page extraction differs from visual-review input")
            if label == "Nambu":
                start = text.index("was as high as 120")
                end = text.index("50th cycle.", start)
                targets = {i for i in range(start, end) if text[i] == "¹"}
                decoded, expected = "−", 1
            else:
                start = text.index("Battery-grade")
                end = text.index("All the electrolytes", start)
                targets = {i for i in range(start, end) if text[i] == "\ue104"}
                decoded, expected = "fl", 4
            if len(targets) != expected or source["text"].count(text.strip()) != 1:
                raise ValueError("Unexpected glyph count or nonunique raw page membership")
            raw_base = source["text"].index(text.strip()) - (len(text) - len(text.lstrip()))
            position, seen = 0, set()
            for block in page.get_text("rawdict")["blocks"]:
                for line in block.get("lines", []):
                    for span in line["spans"]:
                        for char in span["chars"]:
                            offset = text.find(char["c"], position)
                            if offset < 0:
                                raise ValueError("Positioned character mapping failed")
                            position = offset + len(char["c"])
                            if offset not in targets:
                                continue
                            fonts = [r for r in page.get_fonts() if r[3].split("+", 1)[-1] == span["font"]]
                            if len(fonts) != 1:
                                raise ValueError("Nonunique glyph font")
                            xref, left = fonts[0][0], raw_base + offset
                            if source["text"][left:left + 1] != char["c"]:
                                raise ValueError("Positioned raw address differs")
                            operations.append({"pdf_page": page_info["page"], "pdf_text_offset": offset,
                                "raw_character": char["c"], "decoded": decoded, "font": span["font"], "font_xref": xref,
                                "bbox": char["bbox"], "font_program_sha256": f.sha(doc.extract_font(xref)[3]),
                                "raw_start": left, "raw_end": left + 1})
                            seen.add(offset)
            if seen != targets:
                raise ValueError("Unbound reviewed glyph")
        path = f.ROOT / "app/resources" / resource
        f.write(path, {"policy": "reviewed_pdf_glyph_aliases_v0.1", "pdf_sha256": page_info["sha256"],
            "reviewer": "agent_source_visual_review", "automatic_font_name_semantics": False,
            "review_basis": "fresh full Poppler page visually reviewed; finite raw glyph operations only",
            "entries": [{**{k: source[k] for k in ("article_id", "chunk_id", "page_start", "page_end", "source_type")},
                         "raw_sha256": f.sha(source["text"].encode()), "operations": operations}]})
        results.append({"resource": str(path), "sha256": f.sha(path.read_bytes()), "operations": len(operations)})
    f.write(out / "result.json", {"resources": results, "new_interpretations": 5, "old_catalogues_modified": False})
    f.write(out / "bindings.json", f.bindings([Path(__file__), fixture, BASE / "pdf_probe_v01/manifest.json",
        *(Path(p["pdf"]) for p in pages), *(Path(r["resource"]) for r in results)]))
    f.manifest(out)
    print(json.dumps(results))


if __name__ == "__main__":
    main()
