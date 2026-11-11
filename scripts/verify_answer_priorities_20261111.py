"""Independent artifact checks for the bounded schema and completeness patch."""

from __future__ import annotations

import argparse
import json
import tomllib
import xml.etree.ElementTree as ET
from copy import deepcopy
from pathlib import Path
from urllib.parse import unquote, urlsplit

import fitz

from app.generation import answer_completeness as complete
from app.generation import answer_facts
from app.generation.providers import Evidence
from app.generation.required_fields_guard_routes import render
from app.ui import _prepared_statement_text
from scripts import audit_answer_priorities_20261111 as audit
from scripts import gigachat_answer_smoke as f
from scripts.verify_answer_series_freeze_20261111 import ReviewParser


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--candidate-freeze", type=Path)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    for stage in ("pre_edit_v01", "pdf_probe_v01", "catalogue_audit_v01", "comparison_v01", "history_v01", "wheel_v01", "review_v01"):
        f.verify_manifest(audit.BASE / stage)
    before = audit.read(audit.BASE / "pre_edit_v01/bindings.json")
    current = f.bindings(audit.series.app_paths())
    old_app = {k: v for k, v in before.items() if Path(k).is_relative_to(f.ROOT / "app")}
    changed = {k for k in old_app if old_app[k] != current.get(k)}
    expected_changed = {str(f.ROOT / "app/generation" / n) for n in ("gigachat.py", "service.py", "quantitative_facts.py")}
    audit.require(changed == expected_changed, "Unexpected existing application patch")
    expected_added = {str(f.ROOT / n) for n in ("app/generation/answer_completeness.py",
        "app/resources/reviewed_capacity_film_glyph_aliases_v01.json",
        "app/resources/reviewed_formulation_identity_glyph_aliases_v01.json")}
    audit.require(set(current) - set(old_app) == expected_added, "Unexpected added application files")
    old_project = tomllib.loads((audit.BASE / "pre_edit_v01/source_snapshot/pyproject.toml").read_text(encoding="utf-8"))
    project = tomllib.loads((f.ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    normalized = deepcopy(project)
    normalized["project"]["optional-dependencies"]["dev"].remove("jsonschema>=4.23")
    for resource in ("resources/reviewed_capacity_film_glyph_aliases_v01.json",
                     "resources/reviewed_formulation_identity_glyph_aliases_v01.json"):
        normalized["tool"]["setuptools"]["package-data"]["app"].remove(resource)
    audit.require(normalized == old_project, "Unrelated configuration changed")
    glyphs = 0
    for binding in (complete.CAPACITY_GLYPHS, complete.FORMULATION_GLYPHS):
        path, digest = binding
        audit.require(f.sha(path.read_bytes()) == digest, "New catalogue hash differs")
        catalogue = audit.read(path)
        pdf, = [p for p in audit.read(audit.BASE / "pdf_probe_v01/pages.json") if p["sha256"] == catalogue["pdf_sha256"]]
        with fitz.open(pdf["pdf"]) as document:
            for entry in catalogue["entries"]:
                for op in entry["operations"]:
                    page = document[op["pdf_page"] - 1]
                    audit.require(page.get_text()[op["pdf_text_offset"]] == op["raw_character"]
                        and f.sha(document.extract_font(op["font_xref"])[3]) == op["font_program_sha256"], "Glyph offset/font drift")
                    chars = [char for block in page.get_text("rawdict")["blocks"] for line in block.get("lines", [])
                        for span in line["spans"] for char in span["chars"] if span["font"] == op["font"]
                        and char["c"] == op["raw_character"] and list(char["bbox"]) == op["bbox"]]
                    audit.require(len(chars) == 1, "Nonunique positioned glyph")
                    glyphs += 1
    comparison = audit.read(audit.BASE / "comparison_v01/result.json")
    target_anchors, ui = 0, 0
    for row in comparison["cases"]:
        old = audit.OLD / "prepared_v01" / row["id"]
        f.verify_manifest(old)
        f.verify_manifest(audit.OLD / "live" / row["id"])
        if row["id"] not in audit.TARGETS:
            continue
        after = audit.read(audit.BASE / "comparison_v01" / row["id"] / "after.json")
        parent = Evidence(**after["trace"]["evidence"][0])
        payload = json.loads(parent.text)
        registered = next(e for e in audit.read(old / "trace.json")["evidence"] if e["chunk_id"] == parent.chunk_id)
        audit.require(payload["raw_source"] == registered["text"] and payload["raw_source_type"] == registered["source_type"]
                      and all(getattr(parent, k) == registered[k] for k in
                              ("article_id", "chunk_id", "citation_id", "page_start", "page_end")), "Original raw parent changed")
        records = answer_facts.selection_records([parent])
        text = records["F1"]["allowed_claim"]
        audit.require(text in _prepared_statement_text(parent.text, parent.source_type), "Main UI lost complete text")
        selected = next(r for r in row["synthetic_API_controls"] if r["mode"] == "select")
        audit.require(text in render(selected["body"]), "Experimental UI lost complete text")
        target_anchors += row["raw_anchors"]
        ui += 2
    review = audit.BASE / "review_v01"
    parsed = ReviewParser()
    parsed.feed((review / "review.html").read_text(encoding="utf-8"))
    audit.require(parsed.rows == {1: 31, 2: 4} and parsed.headers == {1: 4, 2: 8} and parsed.search,
                  "Review rows/headers/search differ")
    for href in parsed.links:
        value = urlsplit(href)
        audit.require(not value.scheme and not value.netloc and (review / unquote(value.path)).is_file(), "Broken local link")
    suites = list(ET.parse(audit.BASE / "full_v02.xml").getroot().iter("testsuite"))
    audit.require(not any(int(s.get(k, "0")) for s in suites for k in ("errors", "failures")), "Full suite failed")
    if args.candidate_freeze:
        f.verify_manifest(args.candidate_freeze)
        f.verify(audit.read(args.candidate_freeze / "bindings.json"))
    result = {"changed_app_files": sorted(changed), "added_app_files": sorted(expected_added),
        "old_eight_catalogues_unchanged": True, "configuration_only_declared_changes": True,
        "positioned_new_glyphs": glyphs, "target_raw_anchors": target_anchors, "UI_adapter_checks": ui,
        "HTML_case_rows": 30, "HTML_article_rows": 3, "TAC_columns": 8, "local_links_checked": len(parsed.links),
        "tests_passed": sum(int(s.get("tests", "0")) for s in suites), "candidate_freeze_verified": bool(args.candidate_freeze),
        "independent_cases": 0, "independent_accuracy": None, "plan_percent": 75, "real_model_calls": 0, "new_slots": 0}
    f.write(out / "result.json", result)
    f.write(out / "bindings.json", f.bindings([Path(__file__), f.ROOT / "AGENTS.md", review / "manifest.json",
        audit.BASE / "comparison_v01/manifest.json", audit.BASE / "full_v02.xml"]))
    f.manifest(out)
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
