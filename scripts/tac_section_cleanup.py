"""Layout-backed exclusions from Conclusions; all retained text remains exact source slices."""
from __future__ import annotations

import re
from typing import Any

from scripts.tac_front_matter import exact_span, layout_lines

CAPTION = re.compile(r"^\s*(?:figure|fig\.?|рис\.?)\s*\d+\s*[.:|]", re.I)
ADMIN = re.compile(r"^\s*(?:авторы\s+(?:выражают\s+благодарность|благодарят)\b|"
                   r"(?:работа|исследование)\s+выполнен[ао]\s+(?:при\s+поддержке|в\s+рамках|в\s+соответствии)\b)", re.I)
RECOMMENDATIONS = re.compile(r"^\s*рекомендации\s+и\s+перспективы\s+дальнейшей\s+разработки\s+темы\s*$", re.I)
ASSIGNMENT = re.compile(r"\b(?:изучались|исследовались|выполнен[аыо])\s+в\s+рамках\s+государственного\s+задания\b", re.I)


def marginal(box: list[float], height: float) -> bool:
    return box[3] < height * 0.09 or box[1] > height * 0.9


def title_without_footnote(page: dict[str, Any], title: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Trim a trailing dagger only when a smaller, lower matching footnote is mapped."""
    match = re.search(r"[†‡]\s*$", title["quote"])
    if not match:
        return title, []
    items = layout_lines(page)
    title_lines = [r for r in items if title["start"] <= r["start"] < title["end"]]
    if not title_lines:
        return title, []
    marker = title["quote"][match.start()]
    font = max(r["font_size"] for r in title_lines)
    bottom = max(r["bbox"][3] for r in title_lines)
    notes = [r for r in items if re.match(r"^\s*" + re.escape(marker) + r"\s+\w", r["quote"])
             and r["bbox"][1] > bottom and 0 < r["font_size"] < font * 0.85]
    if len(notes) != 1:
        return title, ["T: trailing dagger retained; no unique smaller matching footnote"]
    end = title["start"] + match.start()
    return exact_span(page, "T", title["start"], end, title["method"] + "_without_mapped_footnote"), [
        f"T: PDF page {page['page']} offsets [{end}, {title['end']}) excluded: trailing dagger bound to a mapped footnote"]


def clean_conclusions(pages: list[dict[str, Any]], sections: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    page_map = {p["page"]: p for p in pages}
    # Repeated mapped marginal text is a header, not body prose. Numbers also
    # require marginal geometry; numerical scientific rows in the body remain.
    geometries = {number: layout_lines(page_map[number]) for number in {s["page"] for s in sections if s["kind"] == "C"}}
    margin_texts: dict[str, set[int]] = {}
    for page in pages:
        for block in page.get("layout_blocks", []):
            if marginal(block["bbox"], page["height"]):
                text = page["text"][block["start"]:block["end"]].strip()
                if text:
                    for line in text.splitlines():
                        if line.strip():
                            margin_texts.setdefault(line.strip(), set()).add(page["page"])
    result, diagnostics = [], []
    stopped = False
    for section in sections:
        if section["kind"] != "C":
            result.append(section)
            continue
        if stopped:
            diagnostics.append(f"C: PDF page {section['page']} later fragment excluded after administrative/subsection boundary")
            continue
        page = page_map[section["page"]]
        items = geometries[section["page"]]
        begin, end = section["start"], section["end"]
        for block in page.get('layout_blocks', []):
            # A separately mapped paragraph must explicitly state government
            # assignment within its opening; ordinary property prose is retained.
            if begin <= block['start'] < block['end'] <= end and ASSIGNMENT.search(
                    ' '.join(page['text'][block['start']:block['end']].split())[:200]):
                end = block['start']
                stopped = not section['method'].startswith('proposed_implicit_summary_passage')
                diagnostics.append(f"C: PDF page {page['page']} offsets [{end}, {section['end']}) excluded: "
                                   "separately mapped government-assignment paragraph")
                break
        owned = [r for r in items if begin <= r["start"] and r["end"] <= end]
        for item in owned:
            if ADMIN.match(item["quote"]) or (item["bold"] and RECOMMENDATIONS.fullmatch(item["quote"])):
                end = item["start"]
                stopped = not section["method"].startswith("proposed_implicit_summary_passage")
                diagnostics.append(f"C: PDF page {page['page']} offsets [{end}, {section['end']}) excluded: "
                                   "explicit administrative paragraph or separately headed recommendations")
                break
        margins = []
        for item in owned:
            text = item["quote"].strip()
            if marginal(item['bbox'], page['height']) and (text.isdecimal() or len(margin_texts.get(text, set())) > 1):
                margins.append(item)
        # Remove only marginal prefixes/suffixes, not an interior scientific row.
        changed = True
        while changed:
            changed = False
            for item in margins:
                if item["end"] <= begin or item["start"] >= end:
                    continue
                if not page["text"][begin:item["start"]].strip():
                    diagnostics.append(f"C: PDF page {page['page']} offsets [{begin}, {item['end']}) excluded: mapped marginal prefix")
                    begin = item["end"]
                    changed = True
                elif not page["text"][item["end"]:end].strip():
                    diagnostics.append(f"C: PDF page {page['page']} offsets [{item['start']}, {end}) excluded: mapped marginal suffix")
                    end = item["start"]
                    changed = True
        owned = [r for r in owned if begin <= r["start"] and r["end"] <= end and r["quote"].strip()]
        if owned:
            anchor = owned[0]
            captions = [r for r in items if CAPTION.match(r["quote"]) and r["bbox"][3] < anchor["bbox"][1]]
            if captions:
                last = anchor
                for item in owned[1:]:
                    # A source-order tail returning physically above a preceding
                    # figure caption cannot continue the Conclusions paragraph.
                    if (item["bbox"][3] < max(c["bbox"][3] for c in captions)
                            and item["bbox"][1] + 2 * anchor["font_size"] < last["bbox"][1]
                            and (re.fullmatch(r"\(?[a-z]\)?|[+-]?\d+(?:[.,]\d+)?", item["quote"].strip(), re.I)
                                 or (len(item["quote"].strip()) <= 50 and
                                     abs(item["font_size"] - anchor["font_size"]) > anchor["font_size"] * 0.15))):
                        end = last["end"]
                        diagnostics.append(f"C: PDF page {page['page']} offsets [{end}, {section['end']}) excluded: "
                                           "source-order tail maps above preceding figure caption")
                        break
                    last = item
        if begin < end and page["text"][begin:end].strip():
            changed = (begin, end) != (section["start"], section["end"])
            method = section["method"] + "_layout_boundary_cleanup" if changed else section["method"]
            result.append(exact_span(page, "C", begin, end, method))
        else:
            diagnostics.append(f"C: PDF page {page['page']} empty/marginal-only fragment excluded")
    return result, diagnostics
