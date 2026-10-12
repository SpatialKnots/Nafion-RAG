"""Extract reviewable local bibliographic metadata with exact PDF-text evidence.

Publication year prefers printed issue/citation data over online/copyright dates.
PDF creation/modification dates, filenames and references are never year sources.
This sidecar does not update PostgreSQL or modify TAC section proposals.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts.tac_experiment import add_layout_blocks, digest, lines, span, validate_profiles, write_new

VERSION = "tac_file_metadata_v0.1"
YEAR = r"(?:18|19|20)\d{2}"
JOURNAL = r"[A-Za-zА-Яа-яЁё][A-Za-zА-Яа-яЁё .&–-]{2,95}?"
CITATIONS = [
    re.compile(rf"(?P<journal>{JOURNAL})\s*,?\s+(?P<year>{YEAR})\s*,\s*(?:том\s+)?\d+", re.I),
    re.compile(rf"(?P<journal>{JOURNAL})\s+\d+\s*\((?P<year>{YEAR})\)\s*\d+", re.I),
    re.compile(rf"(?P<journal>{JOURNAL})\s*,?\s+\d+(?:\s*\(\d+\))?\s*,?\s*\d+[–−±-]\s*\d+\s*\((?P<year>{YEAR})\)", re.I),
    re.compile(rf"(?P<journal>{JOURNAL})\s*\|\s*(?:VOL(?:UME)?)\s+\d+\s*\|[^|]{{0,35}}(?P<year>{YEAR})\s*\|", re.I),
    re.compile(rf"(?P<journal>{JOURNAL}),\s*Vol\.\s*\d+,\s*\d+[–−-]\d+\s*\((?P<year>{YEAR})\)", re.I),
    re.compile(rf"(?P<journal>{JOURNAL}),\s*\d+:\d+[–−-]\d+,\s*(?P<year>{YEAR})", re.I),
    re.compile(rf"(?P<journal>{JOURNAL}),\s*(?P<year>{YEAR}),\s*DOI:", re.I),
]
BAD_JOURNAL = re.compile(
    r"copyright|wiley|elsevier|received|accepted|published|download|author|verlag|chemistry peer|society|J\. Name|et al", re.I
)
BAD_BYLINE = re.compile(
    r"department|university|institute|laboratory|faculty|school|center|centre|division|received|accepted|published|"
    r"copyright|journal|article|abstract|introduction|keywords|supporting|royal society|chemical society|"
    r"институт|университет|кафедра|научный руководитель|профессор|доктор|диссертация|реферат|электрохимия|"
    r"http|@|\bdoi\s*[:/]|correspond|commission|research article|read online|metrics|view article|access|key words",
    re.I,
)
NAME_TOKEN = re.compile(
    r"(?:[A-ZА-ЯЁÀ-ÖØ-Þ][a-zа-яёà-öø-ÿ’']*(?:[‐-][A-ZÀ-ÖØ-Þ]?[a-zà-öø-ÿ]+)*|"
    r"[A-ZА-ЯЁÀ-ÖØ-Þ]{2,}|[A-ZА-ЯЁ][a-z]?\.)$"
)


def normalized_view(text: str) -> tuple[str, list[int]]:
    """Collapse whitespace for detection while preserving a map to Unicode source offsets."""
    chars, offsets = [], []
    for offset, char in enumerate(text):
        if char.isspace():
            if chars and chars[-1] != " ":
                chars.append(" ")
                offsets.append(offset)
        else:
            chars.append(char)
            offsets.append(offset)
    return "".join(chars), offsets


def evidence(page: dict[str, Any], start: int, end: int, method: str) -> dict[str, Any]:
    result = asdict(span(page, "T", start, end, method))
    result.pop("kind")
    result["source_type"] = "pdf_selected_text"
    return result


def candidate(field: str, value: Any, priority: int, source: dict[str, Any], method: str) -> dict[str, Any]:
    return {"field": field, "value": value, "priority": priority, "method": method, "evidence": source}


def parse_names(raw: str) -> list[str] | None:
    """Conservative byline parser; affiliation markers are not personal-name tokens."""
    text = re.sub(rf"^\s*©\s*{YEAR}\s*(?:г\.)?", "", raw)
    text = re.sub(r"[\x00-\x1f*†‡§∥⊥✉∗]", " ", text)
    text = re.sub(r"(?<=[A-Za-zА-Яа-яЁё.])\d+", "", text)
    # Uppercase surnames followed by a lowercase affiliation marker.
    text = re.sub(r"\b([A-ZА-ЯЁ]{2,})[a-e]+(?=\s|,|$)", r"\1", text)
    text = re.sub(r"^\s*(?:and|и|&)\s+|\s+(?:and|и|&)\s*$", "", text)
    parts = re.split(r"[,;]|\s+(?:and|и|&)\s+", " ".join(text.split()))
    names = []
    for part in parts:
        value = part.strip(" ,;")
        if value in ("III", "II", "Jr.", "Sr.", "111") and names:
            names[-1] += ", " + value
            continue
        if not value or re.fullmatch(r"[a-e\d ]+", value):
            continue
        # Detached affiliation markers and numeric superscripts.
        value = re.sub(r"\s+[a-z](?:\s+[a-z])*\s*$", "", value)
        value = re.sub(r"\s+\d+\s*$", "", value)
        value = re.sub(r"^(?:and|и|&)\s+", "", value)
        tokens = value.split()
        if BAD_BYLINE.search(value) or not 2 <= len(tokens) <= 6:
            return None
        if not all((len(token) > 1 and NAME_TOKEN.fullmatch(token)) or token in ("de", "van", "von", "da", "del") for token in tokens):
            return None
        names.append(value)
    return names if names else None


def author_blocks(page: dict[str, Any]) -> list[dict[str, Any]]:
    """Exact layout blocks with small raised affiliation glyphs excluded from display values."""
    import fitz  # type: ignore[import-untyped]

    result = []
    with fitz.open(page["layer_pdf_path"]) as document:
        blocks = document[int(page["page"]) - 1].get_text("dict")["blocks"]
    for block in blocks:
        if "lines" not in block:
            continue
        text = "\n".join("".join(s["text"] for s in line["spans"]) for line in block["lines"]) + "\n"
        positions = [m.start() for m in re.finditer(re.escape(text), page["text"])]
        if len(positions) != 1:
            continue
        offset = positions[0]
        for line in block["lines"]:
            raw = "".join(s["text"] for s in line["spans"]) + "\n"
            runs = [s for s in line["spans"] if s["text"].strip()]
            weights = sorted((s["size"], len(s["text"])) for s in runs)
            total = sum(weight for _size, weight in weights)
            font, cumulative = 0.0, 0
            for size, weight in weights:
                cumulative += weight
                if cumulative >= total * 0.6:
                    font = size
                    break
            # Preserve small capitals and name glyphs; remove only small marker-shaped runs.
            cleaned = "".join(
                " " if s["size"] < font * 0.85 and re.fullmatch(r"[a-e\d,*†‡§∥⊥∗ ]+", s["text"]) else s["text"] for s in line["spans"]
            )
            result.append(
                {
                    "start": offset,
                    "end": offset + len(raw),
                    "bbox": line["bbox"],
                    "font_size": font,
                    "cleaned": cleaned,
                    "font_names": sorted({s["font"] for s in runs if s["size"] >= font * 0.85}),
                }
            )
            offset += len(raw)
    groups = []
    for item in sorted(result, key=lambda b: b["start"]):
        if not item["cleaned"].strip() or re.fullmatch(r"[a-e\d,*†‡§∥⊥∗ ]+", item["cleaned"]):
            continue
        if groups:
            previous = groups[-1]
            gap = page["text"][previous["end"] : item["start"]]
            nearby = -2 * item["font_size"] <= item["bbox"][1] - previous["last_bbox"][3] <= 2 * item["font_size"]
            if (
                abs(previous["font_size"] - item["font_size"]) < 0.3
                and previous["font_names"] == item["font_names"]
                and re.fullmatch(r"[\s,a-e\d*†‡]*", gap)
                and nearby
                and not BAD_BYLINE.search(item["cleaned"])
            ):
                groups[-1] = {
                    **previous,
                    "end": item["end"],
                    "cleaned": previous["cleaned"] + re.sub(r"[^,;]", " ", gap) + "\n" + item["cleaned"],
                    "last_bbox": item["bbox"],
                }
                continue
        groups.append({**item, "last_bbox": item["bbox"]})
    for group in groups:
        following = page["text"][group["end"] : group["end"] + 180].lstrip()
        first = following.splitlines()[0] if following else ""
        group["affiliation_boundary"] = bool(BAD_BYLINE.search(first))
    return groups


def extract_authors(page: dict[str, Any], titles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    blocks = author_blocks(page)
    groups = []
    for block in blocks:
        if block["bbox"][1] > page["height"] * 0.65:
            continue
        names = parse_names(block["cleaned"])
        if names is None:
            continue
        prior = [
            b
            for b in page["layout_blocks"]
            for t in titles
            if t["page"] == page["page"]
            and b["start"] <= t["start"] < b["end"]
            and 0 <= block["bbox"][1] - b["bbox"][3] <= 80
            and min(block["bbox"][2], b["bbox"][2]) > max(block["bbox"][0], b["bbox"][0])
        ]
        if not prior and not block["affiliation_boundary"]:
            continue
        if (
            prior
            and not block["affiliation_boundary"]
            and any(abs(b["font_size"] - block["font_size"]) < 0.3 and b["font_names"] == block["font_names"] for b in prior)
        ):
            continue  # Possible title continuation, not established byline.
        groups.append({**block, "names": names, "priority": (100 if prior else 90) + (10 if page["page"] == 1 else 0)})
    merged = []
    for block in sorted(groups, key=lambda b: b["start"]):
        if merged:
            previous = merged[-1]
            gap = page["text"][previous["end"] : block["start"]]
            nearby = -2 * block["font_size"] <= block["bbox"][1] - previous["last_bbox"][3] <= 2 * block["font_size"]
            if nearby and abs(previous["font_size"] - block["font_size"]) < 0.3 and re.fullmatch(r"[\s,a-e\d*†‡]*", gap):
                merged[-1] = {
                    **previous,
                    "end": block["end"],
                    "names": previous["names"] + block["names"],
                    "bbox": block["bbox"],
                    "last_bbox": block["last_bbox"],
                    "priority": max(previous["priority"], block["priority"]),
                }
                continue
        merged.append(block)
    candidates = []
    for block in merged:
        priority = block["priority"]
        names = block["names"]
        candidates.append(
            candidate(
                "authors", names, priority, evidence(page, block["start"], block["end"], "byline_exact_layout"), "byline_exact_layout"
            )
        )
    return candidates


def extract_bibliography(page: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = []
    for block in page["layout_blocks"]:
        raw = page["text"][block["start"] : block["end"]]
        view, offsets = normalized_view(raw)
        for pattern in CITATIONS:
            for match in pattern.finditer(view):
                begin, end = block["start"] + offsets[match.start()], block["start"] + offsets[match.end() - 1] + 1
                journal = match["journal"].strip(" .,-")
                journal = re.sub(r"^(?:Cite (?:This|this):\s*|Communication\s+)", "", journal, flags=re.I)
                journal = re.sub(r"^[a-z]\s+(?=[A-Z])", "", journal)
                if BAD_JOURNAL.search(journal) or not journal:
                    continue
                # Restrict evidence to header/footer or explicit front-matter citation.
                top = block["bbox"][1]
                front_citation = "Cite" in raw[:30]
                cover_citation = "can be cited before page numbers" in raw
                if not (top < page["height"] * 0.12 or top > page["height"] * 0.85 or front_citation or cover_citation):
                    continue
                source = evidence(page, begin, end, "printed_issue_citation")
                priority = 110 if page["page"] == 1 else 100
                candidates.extend(
                    [
                        candidate("journal", journal, priority, source, "printed_issue_citation"),
                        candidate("year", int(match["year"]), priority, source, "printed_issue_citation"),
                    ]
                )
    # Explicit publication dates, never submission/acceptance/PDF filesystem dates.
    for start, end, line in lines(page):
        masthead = re.match(rf"^({JOURNAL})\s+is published by\b", line)
        accepted = re.match(rf"^({JOURNAL}),\s*Just Accepted Manuscript", line)
        if masthead or accepted:
            found_journal = masthead or accepted
            candidates.append(
                candidate(
                    "journal",
                    found_journal[1],
                    105 if masthead else 95,
                    evidence(page, start, end, "publisher_front_matter"),
                    "publisher_front_matter",
                )
            )
        volume_year = re.fullmatch(rf"\d+[,，]\s*No\.\s*\d+[（(]({YEAR})[）)]", line)
        containing = [b for b in page["layout_blocks"] if b["start"] <= start < b["end"]]
        if volume_year and containing and containing[0]["bbox"][1] < page["height"] * 0.12:
            candidates.append(
                candidate("year", int(volume_year[1]), 100, evidence(page, start, end, "running_issue_header"), "running_issue_header")
            )
        if re.search(r"^(?:Published(?:\s+online|\s+on)?\s*:?|Publication Date \(Web\))", line, re.I):
            found = re.search(YEAR, line)
            if found:
                candidates.append(
                    candidate(
                        "year", int(found[0]), 70, evidence(page, start, end, "explicit_publication_date"), "explicit_publication_date"
                    )
                )
        elif "Publication Date (Web):" in line:
            found = re.search(YEAR, line.split("Publication Date (Web):", 1)[1])
            if found:
                candidates.append(
                    candidate(
                        "year", int(found[0]), 70, evidence(page, start, end, "explicit_publication_date"), "explicit_publication_date"
                    )
                )
    return candidates


def choose(field: str, candidates: list[dict[str, Any]]) -> dict[str, Any]:
    applicable = [c for c in candidates if c["field"] == field]
    if not applicable:
        return {
            "value": None,
            "status": "not_found",
            "selected": [],
            "candidates": [],
            "diagnostics": ["No supported candidate recognized in inspected PDF pages; filenames and PDF dates excluded."],
        }
    highest = max(c["priority"] for c in applicable)
    selected = [c for c in applicable if c["priority"] == highest]
    values = {json.dumps(c["value"], ensure_ascii=False) for c in selected}
    if len(values) != 1:
        return {
            "value": None,
            "status": "ambiguous",
            "selected": [],
            "candidates": applicable,
            "diagnostics": ["Conflicting candidates at the same evidence priority; no silent choice."],
        }
    chosen = selected[0]["value"]
    other = [c["value"] for c in applicable if c["value"] != chosen]
    diagnostics = ["Lower-priority alternatives retained; issue year takes precedence over online date."] if other else []
    if field == "authors" and any(", 111" in name for name in chosen):
        diagnostics.append("Possible source-text anomaly in a name suffix; raw 111 retained without an inferred correction.")
    return {
        "value": chosen,
        "status": "proposed",
        "selected": selected,
        "candidates": applicable,
        "diagnostics": diagnostics,
    }


def extract_article(article: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    pages = [add_layout_blocks(p) for p in article["pages"][:2]]
    candidates = []
    titles = [s for s in profile["sections"] if s["kind"] == "T"]
    anchors = []
    for page in pages:
        page_titles = [t for t in titles if t["page"] == page["page"]]
        if not page_titles:
            eligible = [
                b
                for b in page["layout_blocks"]
                if b["bbox"][1] < page["height"] * 0.5
                and 6 <= len(page["text"][b["start"] : b["end"]].split()) <= 60
                and b["font_size"] >= 13
                and not BAD_BYLINE.search(page["text"][b["start"] : b["end"]])
            ]
            if eligible:
                best = max(eligible, key=lambda b: b["font_size"])
                anchor = asdict(span(page, "T", best["start"], best["end"], "metadata_only_front_title_anchor"))
                page_titles.append(anchor)
                anchors.append(anchor)
        candidates.extend(extract_authors(page, page_titles))
        candidates.extend(extract_bibliography(page))
    # Alternating running headers can put the journal and issue date on different pages.
    if pages and any(c["method"] == "running_issue_header" for c in candidates):
        page = pages[0]
        for block in page["layout_blocks"]:
            raw = page["text"][block["start"] : block["end"]]
            match = re.fullmatch(rf"\s*\d+\s*\n\s*({JOURNAL})\s*", raw)
            if match and block["bbox"][1] < page["height"] * 0.12 and not BAD_JOURNAL.search(match[1]):
                candidates.append(
                    candidate(
                        "journal",
                        match[1].strip(),
                        100,
                        evidence(page, block["start"], block["end"], "running_journal_header"),
                        "running_journal_header",
                    )
                )
    thesis = bool(pages and re.search(r"Диссертация\s+на\s+соискание", pages[0]["text"], re.I))
    if thesis:
        page = pages[0]
        title_start = min((t["start"] for t in titles if t["page"] == 1), default=len(page["text"]))
        bylines = [
            (start, end, line)
            for start, end, line in lines(page)
            if end <= title_start and re.fullmatch(r"[А-ЯЁ]+(?:\s+[А-ЯЁ]+){1,3}", line)
        ]
        if bylines:
            start, end, line = bylines[-1]
            candidates.append(candidate("authors", [line], 120, evidence(page, start, end, "thesis_title_page"), "thesis_title_page"))
        for start, end, line in lines(page):
            found = re.fullmatch(rf"[А-ЯЁ][а-яё -]+\s+[–-]\s*({YEAR})", line)
            if found:
                candidates.append(
                    candidate("year", int(found[1]), 120, evidence(page, start, end, "thesis_place_year"), "thesis_place_year")
                )
    fields = {field: choose(field, candidates) for field in ("authors", "journal", "year")}
    if thesis:
        fields["journal"] = {
            "value": None,
            "status": "not_applicable",
            "selected": [],
            "candidates": [],
            "diagnostics": ["Dissertation title page; journal field is not applicable."],
        }
    conference = bool(pages and re.search(r"\d+(?:st|nd|rd|th)\s+ECS Meeting,\s*Abstract", pages[0]["text"]))
    if conference and fields["journal"]["value"] is None:
        fields["journal"] = {
            "value": None,
            "status": "not_applicable",
            "selected": [],
            "candidates": [],
            "diagnostics": ["ECS Meeting conference abstract; no journal printed as publication venue."],
        }
    return {
        "article_id": article["article_id"],
        "checksum_sha256": article["original_pdf_sha256"],
        **{field: result["value"] for field, result in fields.items()},
        "fields": fields,
        "document_type": "dissertation" if thesis else "conference_abstract" if conference else "unclassified",
        "state": "needs_metadata_review",
        "metadata_only_title_anchors": anchors,
        "layout_warnings": [{"page": p["page"], "messages": p["layout_warnings"]} for p in pages if p["layout_warnings"]],
    }


def validate_metadata(snapshot: dict[str, Any], metadata: dict[str, Any], snapshot_sha: str) -> None:
    if metadata.get("schema") != VERSION or metadata["snapshot_sha256"] != snapshot_sha:
        raise ValueError("Metadata version or snapshot mismatch")
    articles = {a["article_id"]: a for a in snapshot["articles"]}
    ids = [a["article_id"] for a in metadata["articles"]]
    if len(set(ids)) != len(ids) or set(ids) != set(articles):
        raise ValueError("Metadata article inventory mismatch")
    for item in metadata["articles"]:
        article = articles[item["article_id"]]
        if item["checksum_sha256"] != article["original_pdf_sha256"]:
            raise ValueError("Metadata PDF checksum mismatch")
        pages = {p["page"]: p for p in article["pages"]}
        if set(item["fields"]) != {"authors", "journal", "year"}:
            raise ValueError("Metadata field inventory mismatch")
        for field, result in item["fields"].items():
            if result["status"] not in {"not_found", "ambiguous", "not_applicable", "proposed"}:
                raise ValueError("Metadata status unsupported")
            value = result["value"]
            if value is not None and (
                (field == "year" and (type(value) is not int or not 1800 <= value <= 2099))
                or (field == "journal" and (not isinstance(value, str) or not value.strip()))
                or (
                    field == "authors"
                    and (not isinstance(value, list) or not value or any(not isinstance(n, str) or not n.strip() for n in value))
                )
            ):
                raise ValueError("Metadata value type invalid")
            if item[field] != result["value"] or (result["value"] is not None and not result["selected"]):
                raise ValueError("Metadata value lacks selected evidence")
            for c in result["candidates"]:
                if c["field"] != field:
                    raise ValueError("Metadata candidate field mismatch")
                e = c["evidence"]
                p = pages[e["page"]]
                if (
                    not 0 <= e["start"] < e["end"] <= len(p["text"])
                    or p["text"][e["start"] : e["end"]] != e["quote"]
                    or p["text_sha256"] != e["page_text_sha256"]
                    or p["layer"] != e["layer"]
                    or p["layer_id"] != e["layer_id"]
                ):
                    raise ValueError("Metadata evidence differs from frozen page")
            if any(c not in result["candidates"] or c["value"] != result["value"] for c in result["selected"]):
                raise ValueError("Metadata selection differs from candidates")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--profiles", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    snapshot_raw, profiles_raw = args.snapshot.read_bytes(), args.profiles.read_bytes()
    snapshot, profiles = json.loads(snapshot_raw), json.loads(profiles_raw)
    validate_profiles(snapshot, profiles, digest(snapshot_raw))
    for name, sha in snapshot["pdf_hashes"].items():
        if digest(Path(name).read_bytes()) != sha:
            raise ValueError(f"Source PDF checksum mismatch: {name}")
    by_id = {p["article_id"]: p for p in profiles["profiles"]}
    result = {
        "schema": VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "source": "local frozen PDF selected text",
        "snapshot_sha256": digest(snapshot_raw),
        "profiles_sha256": digest(profiles_raw),
        "code_sha256": digest(Path(__file__).read_bytes()),
        "articles": [extract_article(a, by_id[a["article_id"]]) for a in snapshot["articles"]],
    }
    validate_metadata(snapshot, result, digest(snapshot_raw))
    write_new(args.output, result)
    print(
        json.dumps(
            {
                "documents": len(result["articles"]),
                "filled": {f: sum(a[f] is not None for a in result["articles"]) for f in ("authors", "journal", "year")},
            }
        )
    )


if __name__ == "__main__":
    main()
