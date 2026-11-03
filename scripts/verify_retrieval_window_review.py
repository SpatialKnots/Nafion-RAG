"""Static HTML, manifest, source and accounting checks for the offline review."""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import url2pathname

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import gigachat_answer_smoke as files  # noqa: E402


class TableAudit(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_tac = False
        self.rows: list[int] = []
        self.cells = 0
        self.links: list[str] = []
        self.search_input = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "table" and attributes.get("id") == "tac":
            self.in_tac = True
        if tag == "input" and attributes.get("id") == "q" and attributes.get("type") == "search":
            self.search_input = True
        if self.in_tac and tag == "tr":
            self.cells = 0
        if self.in_tac and tag in {"td", "th"}:
            self.cells += 1
        if tag == "a":
            href = attributes.get("href")
            if not href:
                raise ValueError("Empty HTML link")
            self.links.append(href)

    def handle_endtag(self, tag: str) -> None:
        if self.in_tac and tag == "tr":
            self.rows.append(self.cells)
        if tag == "table":
            self.in_tac = False


def verify(folder: Path, junit: Path) -> dict[str, object]:
    files.verify_manifest(folder)
    report = json.loads((folder / "report.json").read_bytes())
    files.verify(report["bindings"])
    summary = report["summary"]
    if summary["baseline_replays"] != 304 or summary["candidate_comparisons"] != 608:
        raise ValueError("Incomplete declared comparison")
    if not summary["corrupted_boundary_rejected"] or not summary["corrupted_raw_source_rejected"]:
        raise ValueError("Negative integrity controls missing")
    if any(summary[key] for key in ("db_calls", "embedding_calls", "model_calls", "oauth_calls", "slot_reservations")):
        raise ValueError("Unexpected operation accounting")
    if summary["network_denials"]:
        raise ValueError("Unexpected network attempt")
    html = (folder / "review.html").read_text(encoding="utf-8")
    audit = TableAudit()
    audit.feed(html)
    if audit.rows != [8] * 34:
        raise ValueError("Expected header plus all 33 eight-column TAC rows")
    if not audit.search_input or 'addEventListener("input"' not in html or "r.hidden=" not in html:
        raise ValueError("Missing static search implementation")
    columns = ("Title", "Authors", "Journal", "Year", "Abstract", "Conclusions", "Terms", "hyperlink to original file")
    if any("<th>" + column + "</th>" not in html for column in columns):
        raise ValueError("TAC columns differ")
    linked = []
    for href in audit.links:
        parsed = urlsplit(href)
        if parsed.scheme != "file":
            raise ValueError("Review link is not a local original file")
        path = Path(url2pathname(parsed.path))
        if not path.is_file() or path.suffix.lower() != ".pdf":
            raise ValueError("Broken/non-PDF source link: " + str(path))
        linked.append(str(path.resolve()))
    expected_pdfs = {str(Path(article["original_pdf_path"]).resolve()) for article in report["articles"]}
    if set(linked) != expected_pdfs or len(linked) != 41:
        raise ValueError("Incomplete source link coverage")
    visible_source = unescape(html)
    for article in report["articles"]:
        if article["title"] is not None and article["title"] not in visible_source:
            raise ValueError("Full TAC title absent")
        if article["abstract"] is not None and article["abstract"] not in visible_source:
            raise ValueError("Full TAC abstract absent")
    for row in report["scoped_records"]:
        for diagnosis in row["observations"]["source_diagnostics"].values():
            for region in diagnosis["regions"]:
                if region["end"] - region["start"] != len(region["exact_text"]):
                    raise ValueError("Invalid raw sentence span")
    xml = ET.parse(junit).getroot()
    suites = [xml] if xml.tag == "testsuite" else list(xml)
    if any(int(suite.get(key, "0")) for suite in suites for key in ("errors", "failures", "skipped")):
        raise ValueError("Test run incomplete or failing")
    return {"static_html_qa": "passed", "tac_rows": len(audit.rows) - 1, "tac_columns": 8,
            "existing_pdf_links": len(linked), "distinct_original_pdfs": len(set(linked)),
            "input_bindings_verified": len(report["bindings"]),
            "tests_passed": sum(int(suite.get("tests", "0")) for suite in suites),
            "browser_execution": "not_run", "pdf_visual_qa": "not_run"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", required=True, type=Path)
    parser.add_argument("--junit", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = verify(args.review, args.junit)
    result["bindings"] = files.bindings([Path(__file__), args.review / "manifest.json", args.review / "report.json", args.junit])
    files.write(args.output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
