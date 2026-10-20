"""Geometry-based front-matter proposals on immutable selected PDF text.

No source text is rewritten. Every title/abstract fragment retains exact offsets.
The rules use layout and article structure, never filenames or retrieval gold.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

COVER = re.compile(r"This is an Accepted Manuscript|PLEASE SCROLL DOWN FOR ARTICLE|Just Accepted", re.I)
FRONT_NOISE = re.compile(
    r"department|university|institute|faculty|school|laboratory|correspond(?:ing)?\s+author|e-?mail|@|https?://|www\.|"
    r"copyright|all rights|licen[cs]|article history|keywords?|key words|"
    r"институт|университет|кафедра|поступила|после доработки|принята|ключевые слова|doi\s*[:/]|"
    r"^\s*©\s*\d{4}\b|^\s*manuscript\s+(?:submitted|received)|"
    r"^\s*(?:received|accepted|published)(?:\s*:|\s+(?:online|on|by|\d))",
    re.I | re.M,
)


def layout_stop(text: str, stop: re.Pattern) -> bool:
    text = text.strip()
    if not stop.fullmatch(text):
        return False
    if re.match(r"^(?:\d+[.)]?\s*)?experimental\b", text, re.I):
        # A wrapped prose line beginning "experimental properties ..." is not a heading.
        return bool(re.fullmatch(r"(?:\d+[.)]?\s*)?experimental(?:\s+(?:section|methods|details|procedures|part))?[.:]?", text, re.I))
    return True


def exact_span(page: dict[str, Any], kind: str, start: int, end: int, method: str) -> dict[str, Any]:
    text = page["text"]
    if not 0 <= start < end <= len(text) or hashlib.sha256(text.encode()).hexdigest() != page["text_sha256"]:
        raise ValueError("Front matter evidence outside frozen source")
    return {
        "kind": kind,
        "page": page["page"],
        "start": start,
        "end": end,
        "quote": text[start:end],
        "method": method,
        "layer": page["layer"],
        "layer_id": page["layer_id"],
        "page_text_sha256": page["text_sha256"],
    }


def layout_lines(page: dict[str, Any]) -> list[dict[str, Any]]:
    import fitz  # type: ignore[import-untyped]

    result = []
    with fitz.open(page["layer_pdf_path"]) as document:
        pdf_page = document[int(page["page"]) - 1]
        blocks = pdf_page.get_text("dict")["blocks"]
        warnings = fitz.TOOLS.mupdf_warnings()
        if warnings:
            page.setdefault("layout_warnings", []).append(warnings)
    prior_line = None
    for block in blocks:
        if "lines" not in block:
            continue
        raw = "\n".join("".join(s["text"] for s in line["spans"]) for line in block["lines"]) + "\n"
        locations = [m.start() for m in re.finditer(re.escape(raw), page["text"])]
        offset = locations[0] if len(locations) == 1 else None
        local_cursor = None
        if prior_line:
            local_cursor = prior_line['end']
        for line in block["lines"]:
            text = "".join(s["text"] for s in line["spans"]) + "\n"
            positions = [m.start() for m in re.finditer(re.escape(text), page["text"])] if offset is None else [offset]
            adjacent = not prior_line or (
                abs(prior_line['bbox'][1] - line['bbox'][1]) <= 0.6 * prior_line['font_size']
                and -0.5 * prior_line['font_size'] <= line['bbox'][0] - prior_line['bbox'][2] <= 1.5 * prior_line['font_size']
            )
            if (len(positions) != 1 and adjacent and local_cursor is not None
                    and page["text"][local_cursor:local_cursor + len(text)] == text):
                positions = [local_cursor]
            if len(positions) != 1:
                continue
            position = positions[0]
            weighted = sorted((s["size"], len(s["text"])) for s in line["spans"] if s["text"].strip())
            total, cumulative, font = sum(n for _size, n in weighted), 0, 0.0
            for size, weight in weighted:
                cumulative += weight
                if cumulative >= total * 0.7:
                    font = size
                    break
            dominant = [s for s in line["spans"] if s["size"] >= font * 0.9 and len(s["text"].strip()) >= 2]
            bold_weight = sum(len(s["text"]) for s in dominant if s["flags"] & 16)
            style = bold_weight > sum(len(s["text"]) for s in dominant) / 2
            result.append(
                {"start": position, "end": position + len(text), "quote": text, "bbox": line["bbox"], "font_size": font, "bold": style}
            )
            local_cursor = position + len(text)
            prior_line = result[-1]
            if offset is not None:
                offset += len(text)
    return result


def join_lines(page: dict[str, Any], items: list[dict[str, Any]], *, title: bool) -> list[dict[str, Any]]:
    """Merge before length validation; short continuation lines remain eligible."""
    groups = []
    for item in sorted(items, key=lambda b: b["start"]):
        if not item["quote"].strip():
            continue
        if groups:
            previous = groups[-1]
            gap = item["bbox"][1] - previous["last_bbox"][3]
            overlap = min(previous["bbox"][2], item["bbox"][2]) - max(previous["bbox"][0], item["bbox"][0])
            same_font = abs(previous["font_size"] - item["font_size"]) <= max(0.3, previous["font_size"] * 0.03)
            align = overlap > 0 if title else abs(previous["bbox"][0] - item["bbox"][0]) <= max(12, 2 * item["font_size"])
            same_row = (
                abs(previous["last_bbox"][1] - item["bbox"][1]) <= item["font_size"] * 0.6
                and -item["font_size"] * 0.5 <= item["bbox"][0] - previous["last_bbox"][2] <= item["font_size"] * 1.5
            )
            contiguous = item["start"] >= previous["end"] and not page["text"][previous["end"] : item["start"]].strip()
            if (
                same_font
                and previous["bold"] == item["bold"]
                and contiguous
                and (same_row or (align and -0.7 * item["font_size"] <= gap <= 1.8 * item["font_size"]))
            ):
                groups[-1] = {
                    **previous,
                    "end": item["end"],
                    "quote": page["text"][previous["start"] : item["end"]],
                    "bbox": (
                        min(previous["bbox"][0], item["bbox"][0]),
                        previous["bbox"][1],
                        max(previous["bbox"][2], item["bbox"][2]),
                        max(previous["bbox"][3], item["bbox"][3]),
                    ),
                    "last_bbox": item["bbox"],
                }
                continue
        groups.append({**item, "last_bbox": item["bbox"]})
    return groups


def geometry_title(page: dict[str, Any], noise: re.Pattern, abstract: re.Pattern, stop: re.Pattern):
    from scripts.tac_metadata import author_blocks, parse_names

    items = layout_lines(page)
    boundaries = [b["bbox"][1] for b in items if abstract.match(b["quote"].strip()) or layout_stop(b["quote"], stop)]
    cutoff = min(boundaries, default=page.get("height", 842) * 0.65)
    eligible = [
        b
        for b in items
        if b["bbox"][1] < page.get("height", 842) * 0.7
        and b["font_size"] >= 8
        and not noise.search(b["quote"])
        and not re.search(r"\b(?:19|20)\d{2}\s*[.,]?\s*(?:т\.|vol\.?)\s*\d+|^\s*УДК\b", b["quote"], re.I)
        and not (re.search(r'\b[A-ZА-ЯЁ]\.\s*[A-ZА-ЯЁ]\.', b['quote']) and
                 len(parse_names(re.sub(r'(?<=[a-zа-яё])[A-ZА-ЯЁ](?=\s*(?:,|$))', '', b['quote'])) or []) >= 2)
        and re.search(r"[A-Za-zА-Яа-яЁё]", b["quote"])
    ]
    candidates = [
        b
        for b in join_lines(page, eligible, title=True)
        if 4 <= len(re.findall(r"\w+", b["quote"])) <= 70 and len(b["quote"]) <= 700 and len(re.findall(r"\b\w{3,}\b", b["quote"])) >= 3
    ]
    bylines = [b for b in author_blocks(page) if parse_names(b["cleaned"]) or parse_names(b["cleaned"].title())]
    candidates = [
        b
        for b in candidates
        if b["bbox"][1] < cutoff
        or any(
            0 <= author["bbox"][1] - b["bbox"][3] <= 80 and min(author["bbox"][2], b["bbox"][2]) > max(author["bbox"][0], b["bbox"][0])
            for author in bylines
        )
    ]
    candidates.sort(key=lambda b: (-b["font_size"], b["bbox"][1], b["start"]))
    if not candidates:
        return None, candidates
    best = candidates[0]
    return exact_span(page, "T", best["start"], best["end"], "proposed_geometry_complete_title"), candidates


def explicit_abstract_end(page: dict[str, Any], begin: int, stop: re.Pattern) -> int | None:
    items = layout_lines(page)
    clipped = []
    for item in sorted(items, key=lambda b: b["start"]):
        if item["end"] <= begin:
            continue
        start = max(begin, item["start"])
        quote = page["text"][start : item["end"]]
        if layout_stop(quote, stop) or FRONT_NOISE.search(quote):
            break
        clipped.append({**item, "start": start, "quote": quote})
    groups = join_lines(page, clipped, title=False)
    first = next((g for g in groups if g["quote"].strip()), None)
    return first["end"] if first and len(first["quote"].strip()) >= 100 else None


def geometry_abstract(page: dict[str, Any], title: dict[str, Any], stop: re.Pattern):
    # Reuse the separately tested byline parser; import at call time to keep module initialization acyclic.
    from scripts.tac_metadata import author_blocks, parse_names

    def tac_anchor_names(block):
        parsed = parse_names(block['cleaned']) or parse_names(block['cleaned'].title())
        if parsed or not block.get('affiliation_boundary'):
            return parsed
        # Matching view only; preserve the original byline/source and metadata.
        cleaned = re.sub(r'(?m)(?<=,)\s*[a-z]\s*$', '', block['cleaned'])
        cleaned = re.sub(r'(?<=[a-zà-öø-ÿ])-(?=[A-Z]\.)', ' ', cleaned)
        return parse_names(cleaned)

    items = layout_lines(page)
    title_lines = [b for b in items if title["start"] <= b["start"] < title["end"]]
    if not title_lines:
        return None, "A: title has no exact geometry anchor"
    title_end = max(b["bbox"][3] for b in title_lines)
    bylines = [
        b
        for b in author_blocks(page)
        if title_end <= b["bbox"][1] <= title_end + 100
        and tac_anchor_names(b) is not None
        and min(b["bbox"][2], max(t["bbox"][2] for t in title_lines)) > max(b["bbox"][0], min(t["bbox"][0] for t in title_lines))
    ]
    if not bylines:
        return None, "A: no supported byline after title; geometry fallback excluded"
    begin_y = max(b["last_bbox"][3] for b in bylines)
    headings = [
        b["bbox"][1] for b in items if b["bbox"][1] > begin_y and layout_stop(b["quote"], stop) and not FRONT_NOISE.search(b["quote"])
    ]
    boundary_y = min(headings, default=page.get("height", 842) * 0.85)
    prose = [
        b
        for b in items
        if begin_y < b["bbox"][1] < boundary_y and not FRONT_NOISE.search(b["quote"]) and not re.fullmatch(r"[\W\d]+", b["quote"])
    ]
    groups = join_lines(page, prose, title=False)
    candidates = []
    for block in groups:
        text = block["quote"]
        if not 150 <= len(text) <= 5000 or len(text.split()) < 25 or not re.search(r"[.!?]\s", text):
            continue
        narrower = [
            b
            for b in items
            if b["bbox"][1] >= block["bbox"][3]
            and not block["start"] <= b["start"] < block["end"]
            and len(b["quote"].split()) >= 8
            and b["bbox"][2] - b["bbox"][0] < (block["bbox"][2] - block["bbox"][0]) / 1.2
        ]
        if headings or narrower:
            candidates.append(block)
    if headings and len(candidates) > 1:
        ordered = sorted(candidates, key=lambda b: b["start"])
        compatible = all(abs(b["bbox"][0] - ordered[0]["bbox"][0]) <= 12 for b in ordered)
        safe_gaps = all(
            not FRONT_NOISE.search(page["text"][left["end"] : right["start"]]) for left, right in zip(ordered, ordered[1:], strict=False)
        )
        if compatible and safe_gaps:
            candidates = [{**ordered[0], "end": ordered[-1]["end"]}]
    if len(candidates) != 1:
        return None, f"A: geometry paragraph candidates={len(candidates)}; no unique complete proposal"
    block = candidates[0]
    return exact_span(
        page, "A", block["start"], block["end"], "proposed_byline_geometry_abstract"
    ), "A: geometry/byline proposal; requires boundary review"
