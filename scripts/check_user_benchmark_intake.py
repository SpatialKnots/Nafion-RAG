"""Fresh local source/HTML verification of the frozen benchmark intake packet."""

from __future__ import annotations

import argparse
import json
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse

import fitz

from scripts import gigachat_answer_smoke as files
from scripts.prepare_user_benchmark_intake import BASE, DRAW, ORIGINAL, pre, read
from scripts.user_benchmark_intake import VERSION, parse_document, quote_match, registered_pdf


class Structure(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []
        self.headers = 0
        self.rows = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "a" and values.get("href"):
            self.links.append(str(values["href"]))
        self.headers += tag == "th"
        self.rows += tag == "tr"


def check() -> dict:
    sys.addaudithook(files.NetworkPolicy())
    folder = BASE / "review_v01"
    files.verify_manifest(folder)
    files.verify(read(folder / "bindings.json"))
    report = read(folder / "report.json")
    raw = ORIGINAL.read_bytes()
    if raw != Path(report["receipt"]["source_path"]).read_bytes():
        raise ValueError("Supplied original drift")
    if raw != (folder / "original.md").read_bytes():
        raise ValueError("Review original differs")
    if files.sha(raw) != report["receipt"]["sha256"]:
        raise ValueError("Original hash drift")
    cases = parse_document(raw.decode("utf-8"))
    selected = read(DRAW)["selected"]
    registered = {str(Path(s["original_pdf_path"]).resolve()) for s in selected}
    pages = {}
    for case, frozen in zip(cases, report["cases"], strict=True):
        registered_pdf(case["source_pdf_path_verbatim"], selected)
        for key, value in case.items():
            if key != "quotes" and value != frozen[key]:
                raise ValueError("Verbatim case drift: " + key)
        with fitz.open(case["source_pdf_path_verbatim"]) as pdf:
            for row in report["source_pages"]:
                if row["case_id"] != case["id"]:
                    continue
                fresh = pdf[row["pdf_page"] - 1].get_text()
                if (folder / row["raw_text_file"]).read_bytes() != fresh.encode("utf-8"):
                    raise ValueError("Fresh PDF text differs")
                if files.sha(fresh.encode("utf-8")) != row["sha256"]:
                    raise ValueError("Page hash differs")
                pages[case["id"], row["pdf_page"]] = fresh
        for quote, frozen_quote in zip(case["quotes"], frozen["quotes"], strict=True):
            fresh = pages[case["id"], quote["pdf_page"]]
            if {**quote, **quote_match(fresh, quote["matching_quote"])} != frozen_quote:
                raise ValueError("Quote replay differs")
    anchors = 0
    for case in report["cases"]:
        for quote in case["quotes"]:
            span = quote["span"]
            if span is not None:
                text = pages[case["id"], quote["pdf_page"]]
                if text[span["start"]:span["end"]] != span["text"]:
                    raise ValueError("Quote raw anchor differs")
                anchors += 1
    for note in report["source_notes"]:
        text, span = pages[note["case_id"], note["pdf_page"]], note["raw_span"]
        if text[span["start"]:span["end"]] != span["text"]:
            raise ValueError("Note raw anchor differs")
        anchors += 1
    packet = read(folder / "questions_only.json")
    if packet["cases"] != [{"id": c["id"], "question": c["question"]} for c in cases]:
        raise ValueError("Questions-only packet differs")
    if packet["live_authorization"] is not False:
        raise ValueError("Unexpected authorization")
    html = (folder / "review.html").read_text(encoding="utf-8")
    parser = Structure()
    parser.feed(html)
    if parser.headers != 8 or parser.rows != 6 or pre(raw.decode("utf-8")) not in html:
        raise ValueError("HTML table/original structure differs")
    for link in parser.links:
        url = urlparse(link)
        path = Path(unquote(url.path).lstrip("/"))
        if url.scheme != "file" or str(path.resolve()) not in registered or not path.is_file():
            raise ValueError("HTML link outside registered PDFs")
    return {"version": VERSION, "manifest_and_bindings": "passed", "cases": len(cases),
            "fresh_pdf_pages": len(pages), "verified_raw_spans": anchors, "quote_counts": report["quote_counts"],
            "tac_works": parser.rows - 1, "tac_columns": parser.headers, "existing_pdf_links": len(parser.links),
            "browser_execution": "untested", "scientific_scores": None, "model_oauth_calls": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-only", action="store_true", help="Read-only replay; keep the original QA file unchanged")
    arguments = parser.parse_args()
    result = check()
    if not arguments.verify_only:
        files.write(BASE / "qa_v01.json", result)
    print(json.dumps(result, ensure_ascii=False))
