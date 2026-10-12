"""Conservative continuation and implicit summary proposals on frozen PDF text.

Every output remains an exact page slice. Summary passages do not assert that a
document contains a separately headed Conclusions section.
"""

from __future__ import annotations

import re
from typing import Any

from scripts.tac_front_matter import FRONT_NOISE, exact_span, join_lines, layout_lines, layout_stop

SUMMARY = re.compile(r"^\s*(?:In\s+summary|In\s+conclusion|To\s+summari[sz]e|В\s+заключение)\s*[,.:]", re.I)
TERMINAL = re.compile(r"[.!?][\s\"'’”)]*$")


def complete(text: str) -> bool:
    return bool(TERMINAL.search(text))


def continuation(pages: list[dict[str, Any]], proposal: dict[str, Any], stop: re.Pattern) -> list[dict[str, Any]]:
    """Extend only an unfinished proposal into an adjacent matching text flow."""
    result = [proposal]
    if complete(proposal["quote"]):
        return result
    index = next(i for i, p in enumerate(pages) if p["page"] == proposal["page"])
    page = pages[index]
    items = layout_lines(page)
    anchors = [line for line in items if proposal["start"] <= line["start"] < proposal["end"]]
    if not anchors:
        return result
    last = max(anchors, key=lambda line: line["start"])
    left = min(line["bbox"][0] for line in anchors)
    right = max(line["bbox"][2] for line in anchors)
    top = min(line["bbox"][1] for line in anchors)
    for current in pages[index : index + 2]:
        cross_page = current["page"] != page["page"]
        if cross_page and current["page"] != page["page"] + 1:
            break
        if cross_page and (complete(result[-1]["quote"]) or last["bbox"][3] < page.get("height", 842) * 0.7):
            break
        begin = 0 if cross_page else proposal["end"]
        candidates = []
        boundary_encountered = False
        for line in sorted(layout_lines(current), key=lambda line: line["start"]):
            if line["end"] <= begin:
                continue
            quote = current["text"][max(begin, line["start"]) : line["end"]]
            if cross_page and not candidates and (line["bbox"][1] < 35 or re.fullmatch(r"[\W\d]+", quote)):
                continue  # A running header is not appended to source evidence.
            if layout_stop(quote.lstrip("■•▪ "), stop) or FRONT_NOISE.search(quote):
                boundary_encountered = True
                break
            candidates.append({**line, "start": max(begin, line["start"]), "quote": quote})
        groups = join_lines(current, candidates, title=False)
        extended = False
        rejected = False
        for group in groups:
            same_font = abs(group["font_size"] - last["font_size"]) <= max(0.3, last["font_size"] * 0.03)
            same_style = group["bold"] == last["bold"]
            gap = group["bbox"][1] - last["bbox"][3]
            same_column = abs(group["bbox"][0] - left) <= 12 and -last["font_size"] <= gap <= 2 * last["font_size"]
            next_column = (
                right <= group["bbox"][0] <= right + max(80, (right - left) * 0.5)
                and group["bbox"][1] < last["bbox"][1]
                and (
                    abs(group["bbox"][1] - top) <= 2 * last["font_size"]
                    if proposal["kind"] == "A"
                    else last["bbox"][3] >= page.get("height", 842) * 0.6
                )
            )
            next_page = cross_page and group["bbox"][1] < current.get("height", 842) * 0.3 and abs(group["bbox"][0] - left) <= 12
            contiguous = cross_page or not current["text"][result[-1]["end"] : group["start"]].strip()
            if not (same_font and same_style and contiguous and (same_column or next_column or next_page)):
                rejected = True
                break
            end = group["end"]
            # A detached publisher copyright glyph can share the final prose line.
            suffix = re.search(r"(?<=[.!?])\s+[VC©]+\s*$", current["text"][group["start"] : end])
            if suffix and re.match(r"\s*(?:C|©)\s*\d{4}\b", current["text"][end : end + 100]):
                end = group["start"] + suffix.start()
            method = proposal["method"] + "_continued_exact_flow"
            if cross_page:
                result.append(exact_span(current, proposal["kind"], group["start"], end, method))
            else:
                result[-1] = exact_span(current, proposal["kind"], result[-1]["start"], end, method)
            extended = True
            last = {**group, "bbox": group["last_bbox"]}
            left, right = group["bbox"][0], group["bbox"][2]
            if complete(result[-1]["quote"]):
                return result
        if boundary_encountered or rejected or (not extended and cross_page):
            break
    return result


def summary_passages(pages: list[dict[str, Any]], stop: re.Pattern) -> tuple[list[dict[str, Any]], list[str]]:
    proposals, diagnostics = [], []
    references_started = False
    for page in pages:
        reference_positions = [
            match.start()
            for match in re.finditer(
                r"^\s*[■•▪]?\s*(?:references|literature cited|список литературы|литература)\s*[:.]?\s*$", page["text"], re.I | re.M
            )
        ]
        if references_started:
            continue
        if page["page"] < max(1, len(pages) // 2 + 1):
            references_started = bool(reference_positions)
            continue  # Do not interpret introductory mentions as article conclusions.
        for block in page.get("layout_blocks", []):
            if reference_positions and block["start"] >= min(reference_positions):
                continue
            raw = page["text"][block["start"] : block["end"]]
            if not SUMMARY.match(raw):
                continue
            end = block["end"]
            position = block["start"]
            for line in raw.splitlines(keepends=True):
                if position > block["start"] and layout_stop(line.strip().lstrip("■•▪ "), stop):
                    end = position
                    break
                position += len(line)
            quote = page["text"][block["start"] : end]
            if len(quote.split()) < 25 or len(quote) > 6000:
                diagnostics.append(f"C: PDF page {page['page']} summary marker rejected: unsupported passage size")
                continue
            initial = exact_span(page, "C", block["start"], end, "proposed_implicit_summary_passage")
            proposals.extend(continuation(pages, initial, stop))
        references_started = bool(reference_positions)
    if proposals:
        diagnostics.append("C: implicit summary passages; not a separately headed Conclusions section; review required")
        if any(not complete(s["quote"]) for s in proposals):
            diagnostics.append("C: summary passage has no terminal sentence boundary; continuation review required")
    return proposals, diagnostics
