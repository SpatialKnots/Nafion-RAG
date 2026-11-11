"""Verify the consolidated local artifact, source versions and static HTML without inference."""

from __future__ import annotations

import argparse
import json
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

from scripts import audit_answer_series_20261111 as audit
from scripts import gigachat_answer_smoke as f


class ReviewParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.table = 0
        self.rows = {1: 0, 2: 0}
        self.headers = {1: 0, 2: 0}
        self.links = []
        self.search = False
        self.details = 0

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "table":
            self.table += 1
        if tag == "tr":
            self.rows[self.table] += 1
        if tag == "th":
            self.headers[self.table] += 1
        if tag == "a":
            self.links.append(values["href"])
        if tag == "input" and values.get("id") == "search":
            self.search = True
        if tag == "details":
            self.details += 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--freeze", type=Path)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    current = f.bindings(audit.app_paths())
    folders = [audit.BASE / n for n in ("review_v02", "replay_v04", "chain_v02", "wheel_v03", "regression_v01")]
    mapped = []
    for folder in folders:
        f.verify_manifest(folder)
        if (folder / "bindings.json").is_file():
            for name, digest in audit.read(folder / "bindings.json").items():
                path = Path(name)
                if f.sha(path.read_bytes()) != digest:
                    snapshot = folder / "executed_script.py"
                    audit.require(path == Path(audit.__file__) and snapshot.is_file()
                                  and f.sha(snapshot.read_bytes()) == digest, "Unexplained source drift: " + name)
                    mapped.append({"path": name, "historical_sha256": digest, "snapshot": str(snapshot),
                                   "current_sha256": f.sha(path.read_bytes()),
                                   "change": "report exporter only; source app unchanged"})
    review = audit.BASE / "review_v02"
    parsed = ReviewParser()
    parsed.feed((review / "review.html").read_text(encoding="utf-8"))
    audit.require(parsed.rows == {1: 31, 2: 4} and parsed.headers == {1: 5, 2: 8}
                  and parsed.search and parsed.details == 31, "Static HTML structure differs")
    for href in parsed.links:
        url = urlsplit(href)
        audit.require(not url.scheme and not url.netloc and (review / unquote(url.path)).is_file(),
                      "Missing/nonlocal HTML link")
    if args.freeze:
        f.verify_manifest(args.freeze)
        f.verify(audit.read(args.freeze / "bindings.json"))
    report = audit.read(review / "report.json")
    audit.require(report["pytest"] == {"tests": 5979, "failures": 0, "errors": 0, "skipped": 0},
                  "Full suite counts differ")
    f.verify(current)
    value = {"HTML_case_rows": 30, "HTML_article_rows": 3, "TAC_columns": 8, "HTML_details": parsed.details,
             "HTML_links_existing": len(parsed.links), "manifests_verified": len(folders),
             "current_app_files": len(current), "explicit_historical_source_mappings": mapped,
             "source_freeze_verified": bool(args.freeze), "real_model_calls": 0, "real_oauth_calls": 0,
             "scientific_accuracy": None, "plan_percent": 75}
    f.write(out / "result.json", value)
    f.write(out / "bindings.json", f.bindings([Path(__file__), f.ROOT / "AGENTS.md", *(p / "manifest.json" for p in folders)]))
    f.manifest(out)
    print(json.dumps(value), flush=True)


if __name__ == "__main__":
    main()
