"""Private, source-preserving TAC feasibility experiment; no production integration.

The extractor emits proposals, not verified section boundaries or scientific facts.
The replay compares a TAC shortlist with saved production full-text candidates.
It is not a restricted-index latency benchmark or an independent quality evaluation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from dataclasses import asdict, dataclass, is_dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from app.evaluation.retrieval import _evaluate_extended_question, load_extended_questions
from app.retrieval.cross_lingual import build_query_bundle
from app.retrieval.search import SearchResponse, SearchResult, search_chunks

RULE_VERSION = "tac_section_proposals_v0.5"
ABSTRACT = re.compile(
    r"^\s*(?:abstract|a\s+b\s+s\s+t\s+r\s+a\s+c\s+t|аннотация|реферат|full\s+paper)(?=\s|[:.–-]|$)\s*[:.–-]?\s*", re.I,
)
CONCLUSION = re.compile(
    r"^\s*(?:\d+(?:\.\d+)*[.)]?\s*)?(?:conclusions?(?:\s+and\s+(?:perspectives|outlook|summary))?|"
    r"concluding\s+remarks|summary\s+and\s+conclusions?|заключение|выводы|основные\s+выводы)\s*[.:]?\s*$", re.I,
)
STOP = re.compile(
    r"^\s*(?:\d+(?:\.\d+)*[.)]?\s*)?(?:introduction|введение|experimental(?:\s+.*)?|materials\s+and\s+methods|"
    r"results(?:\s+and\s+discussion)?|discussion|references(?:\s+and\s+notes)?|literature\s+cited|"
    r"литература|список\s+литературы|благодарности|"
    r"acknowledg(?:e)?ments?|author\s+contributions|funding|conflicts?\s+of\s+interest|methods|"
    r"финансирование\s+работы|конфликт\s+интересов|registry\s+no|"
    r"associated\s+content|additional\s+information|online\s+content|оглавление|место\s+выполнения\s+работы|"
    r"declaration\s+of\s+competing\s+interest|credit\s+authorship\s+contribution\s+statement|"
    r"data\s+availability(?:\s+.*)?|supporting\s+information|supplementary\s+(?:materials|information)|"
    r"keywords?\s*:.*|ключевые\s+слова\s*:.*)\s*(?:[.:]\s*.*)?$", re.I,
)
TITLE_NOISE = re.compile(
    r"(?:https?://|www\.|doi\s*:|journal\s+homepage|contents\s+lists|copyright|all\s+rights\s+reserved|"
    r"received\s|accepted\s|published\s|research\s+article|full\s+paper|electrochimica\s+acta$|"
    r"nature\s+energy$|rsc\s+advances$|polymers$|journal\s+of\s+|supporting\s+information|supplementary\s+materials|"
    r"федеральное\s+государственное|учреждение\s+высшего|electrochemical\s+society|"
    r"department\s+of|институт\s+|кафедра\s+|университет\s+|на\s+правах\s+рукописи)", re.I,
)


@dataclass(frozen=True)
class TACSpan:
    kind: Literal["T", "A", "C"]
    page: int
    start: int
    end: int
    quote: str
    method: str
    layer: str
    layer_id: str
    page_text_sha256: str


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def write_new(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2, default=json_default)
        stream.write("\n")


def json_default(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Unsupported experiment JSON value: {type(value).__name__}")


def span(page: dict[str, Any], kind: Literal["T", "A", "C"], start: int, end: int, method: str) -> TACSpan:
    text = str(page["text"])
    if not 0 <= start < end <= len(text):
        raise ValueError("TAC span outside source page")
    if digest(text.encode()) != page["text_sha256"]:
        raise ValueError("Source page checksum mismatch")
    return TACSpan(kind, int(page["page"]), start, end, text[start:end], method,
                   str(page["layer"]), str(page["layer_id"]), str(page["text_sha256"]))


def lines(page: dict[str, Any]) -> list[tuple[int, int, str]]:
    result = []
    position = 0
    for line in str(page["text"]).splitlines(keepends=True):
        result.append((position, position + len(line), line.strip().lstrip("■•▪ ")))
        position += len(line)
    return result


def abstract_layout_end(page: dict[str, Any], heading_start: int, begin: int) -> int | None:
    """Join adjacent exact blocks with matching typography, not neighbouring body columns."""
    if "layer_pdf_path" in page:
        from scripts.tac_front_matter import explicit_abstract_end

        complete = explicit_abstract_end(page, begin, STOP)
        if complete is not None:
            return complete
    blocks = sorted(page.get("layout_blocks", []), key=lambda b: b["start"])
    enclosing = [b for b in blocks if b["start"] <= heading_start < b["end"]]
    if not enclosing:
        return None
    current = enclosing[0]
    if not str(page["text"])[begin:current["end"]].strip():
        following = [b for b in blocks if b["start"] >= current["end"]]
        if not following or str(page["text"])[current["end"]:following[0]["start"]].strip():
            return None
        current = following[0]
    end = current["end"]
    for following in blocks:
        if following["start"] < end:
            continue
        gap = str(page["text"])[end:following["start"]]
        if gap.strip() or "bbox" not in current or "bbox" not in following:
            break
        # Blank blocks do not supply style; retain them only as source whitespace.
        if not str(page["text"])[following["start"]:following["end"]].strip():
            end = following["end"]
            continue
        same_font = abs(float(current["font_size"]) - float(following["font_size"])) <= 0.3
        same_style = current.get("font_names") == following.get("font_names")
        same_column = abs(current["bbox"][0] - following["bbox"][0]) <= 8
        vertical_gap = following["bbox"][1] - current["bbox"][3]
        if not (same_font and same_style and same_column and 0 <= vertical_gap <= 1.6 * float(current["font_size"])):
            break
        first_line = str(page["text"])[following["start"]:following["end"]].splitlines()[0].strip()
        if STOP.fullmatch(first_line):
            break
        end = following["end"]
        current = following
    return int(end)


def heading_spans(pages: list[dict[str, Any]], front_start: int = 1) -> tuple[list[TACSpan], list[str]]:
    """Conservative text-order proposals; no reconstruction of column reading order."""
    candidates: list[TACSpan] = []
    diagnostics = []
    active: Literal["A", "C"] | None = None
    for page in pages:
        page_lines = lines(page)
        begin: int | None = 0 if active else None
        for start, end, line in page_lines:
            abstract = ABSTRACT.match(line) if front_start <= int(page["page"]) <= front_start + 1 else None
            conclusion = CONCLUSION.fullmatch(line)
            stop = STOP.fullmatch(line)
            if abstract or conclusion or stop:
                if active and begin is not None and start > begin and str(page["text"])[begin:start].strip():
                    candidates.append(span(page, active, begin, start, "explicit_heading_text_order"))
                active = "A" if abstract else "C" if conclusion else None
                begin = end if active else None
                # Some publishers put Abstract and the opening sentence on one line.
                if abstract:
                    raw_line = str(page["text"])[start:end]
                    prefix = len(raw_line) - len(raw_line.lstrip("■•▪ \t"))
                    match = ABSTRACT.match(raw_line[prefix:])
                    if match and raw_line[match.end():].strip():
                        begin = start + prefix + match.end()
                    # Explicit layout boundaries prevent an unlabelled Introduction
                    # from making the entire article appear to be an abstract.
                    boundary = abstract_layout_end(page, start, begin) if begin is not None else None
                    if boundary is not None and begin is not None and str(page["text"])[begin:boundary].strip():
                        candidates.append(span(page, "A", begin, boundary, "explicit_heading_exact_layout_block"))
                        active, begin = None, None
        if active and begin is not None and len(str(page["text"])) > begin and str(page["text"])[begin:].strip():
            if active == "A":
                diagnostics.append("A: no supported ending boundary; excluded rather than absorbing body text")
                active = None
            else:
                candidates.append(span(page, active, begin, len(str(page["text"])), "explicit_heading_text_order"))
    for kind in ("A", "C"):
        if not any(item.kind == kind for item in candidates):
            diagnostics.append(f"{kind}: no supported explicit boundary")
    return candidates, diagnostics


def implicit_russian_abstract(pages: list[dict[str, Any]]) -> TACSpan | None:
    """Specific documented publisher pattern, kept separate from explicit headings."""
    if not pages:
        return None
    page = pages[0]
    page_lines = lines(page)
    starts = [end for _start, end, line in page_lines if re.match(r"^Принята\s+к\s+публикации\s+\d", line, re.I)]
    if len(starts) != 1:
        return None
    begin = starts[0]
    stops = [start for start, _end, line in page_lines if start > begin and (
        STOP.fullmatch(line) or re.match(r"^DOI\s*:", line, re.I))]
    if not stops or not str(page["text"])[begin:min(stops)].strip():
        return None
    return span(page, "A", begin, min(stops), "proposed_after_russian_acceptance_line")


def title_from_layout(page: dict[str, Any]) -> tuple[TACSpan | None, list[dict[str, Any]]]:
    """Largest eligible first-page text block; uncertainty remains explicit."""
    from scripts.tac_front_matter import geometry_title

    dissertation = dissertation_title(page)
    if dissertation is not None:
        return dissertation, []
    proposed, candidates = geometry_title(page, TITLE_NOISE, ABSTRACT, STOP)
    return TACSpan(**proposed) if proposed else None, candidates


def dissertation_title(page: dict[str, Any]) -> TACSpan | None:
    text = str(page["text"])
    if not re.search(r"Диссертация\s+на\s+соискание", text, re.I):
        return None
    stops = [start for start, _end, line in lines(page) if re.match(r"^Специальность\s+\d", line)]
    if len(stops) != 1:
        return None
    author_ends = [end for start, end, line in lines(page) if start < stops[0] and
                   re.fullmatch(r"[А-ЯЁ]+(?:\s+[А-ЯЁ]+){1,3}", line)]
    if not author_ends or not text[max(author_ends):stops[0]].strip():
        return None
    return span(page, "T", max(author_ends), stops[0], "proposed_dissertation_author_specialty_zone")


def add_layout_blocks(page: dict[str, Any]) -> dict[str, Any]:
    import fitz  # type: ignore[import-untyped]

    result = dict(page)
    result["layout_blocks"] = []
    result["layout_warnings"] = []
    with fitz.open(page["layer_pdf_path"]) as document:
        pdf_page = document[int(page["page"]) - 1]
        result["height"] = pdf_page.rect.height
        for block in pdf_page.get_text("dict")["blocks"]:
            if "lines" not in block:
                continue
            spans = [s for line in block["lines"] for s in line["spans"]]
            text = "\n".join("".join(s["text"] for s in line["spans"]) for line in block["lines"]) + "\n"
            positions = [m.start() for m in re.finditer(re.escape(text), str(page["text"]))]
            if len(positions) == 1:
                weight = sum(len(s["text"]) for s in spans)
                font_size = sum(len(s["text"]) * s["size"] for s in spans) / weight if weight else 0
                result["layout_blocks"].append({"start": positions[0], "end": positions[0] + len(text),
                                                "bbox": block["bbox"], "font_size": font_size,
                                                "font_names": sorted({s["font"] for s in spans})})
        warnings = fitz.TOOLS.mupdf_warnings()
        if warnings:
            result["layout_warnings"].append(warnings)
    return result


FRONT_PROSE = re.compile(
    r"\b(?:here\s+(?:we|a)|we\s+(?:report|investigat\w*|present|demonstrat\w*|show|have)|"
    r"this\s+(?:study|work|investigation)|our\s+(?:work|findings)|it\s+is\s+found)\b", re.I,
)


def unlabelled_abstract(page: dict[str, Any], title: TACSpan | None) -> tuple[TACSpan | None, str]:
    """Front-matter prose with a typography/width change; no title- or query-specific anchors."""
    if title is None:
        return None, "A: unlabelled front matter needs a title anchor"
    cutoffs = [start for start, _end, line in lines(page) if STOP.fullmatch(line)]
    cutoff = min((start for start in cutoffs if start > title.end), default=len(str(page["text"])))
    blocks = page.get("layout_blocks", [])
    groups: list[dict[str, Any]] = []
    for block in sorted(blocks, key=lambda b: b["start"]):
        if block["start"] < title.end or block["end"] > cutoff:
            continue
        if groups:
            previous = groups[-1]
            gap = block["bbox"][1] - previous["bbox"][3]
            same_font = abs(previous["font_size"] - block["font_size"]) <= 0.3
            same_style = previous.get("font_names") == block.get("font_names")
            same_column = abs(previous["bbox"][0] - block["bbox"][0]) <= 8
            whitespace = not str(page["text"])[previous["end"]:block["start"]].strip()
            if same_font and same_style and same_column and whitespace and 0 <= gap <= 1.6 * block["font_size"]:
                groups[-1] = {**previous, "end": block["end"],
                              "bbox": (previous["bbox"][0], previous["bbox"][1],
                                       max(previous["bbox"][2], block["bbox"][2]), block["bbox"][3])}
                continue
        groups.append(dict(block))
    candidates = []
    for block in groups:
        quote = str(page["text"])[block["start"]:block["end"]]
        if not title.end <= block["start"] < cutoff or not 150 <= len(quote) <= 3500 or not FRONT_PROSE.search(quote):
            continue
        if re.search(r"e-?mail|https?://|www\.|@|^Received|^Accepted|^Published", quote, re.I | re.M):
            continue
        if block["bbox"][1] > 0.7 * page.get("height", 842):
            continue
        lower = [b for b in blocks if b["bbox"][1] >= block["bbox"][3] and b["end"] - b["start"] >= 150]
        width = block["bbox"][2] - block["bbox"][0]
        narrower = [b for b in lower if b["bbox"][2] - b["bbox"][0] < width / 1.2]
        if not narrower:
            continue
        # A width transition is required; an opening body paragraph alone is insufficient.
        candidates.append(block)
    if len(candidates) != 1:
        return None, f"A: unlabelled layout candidates={len(candidates)}; no unique proposal"
    block = candidates[0]
    return span(page, "A", block["start"], min(block["end"], cutoff), "proposed_unlabelled_front_matter_layout"), \
        "A: unlabelled front-matter proposal; needs boundary review"


def validate_snapshot(snapshot: dict[str, Any]) -> None:
    ids = []
    for article in snapshot["articles"]:
        ids.append(article["article_id"])
        if len({page["page"] for page in article["pages"]}) != len(article["pages"]):
            raise ValueError("Duplicate source page")
        for item in (*article["pages"], *article["chunks"]):
            if digest(item["text"].encode()) != item["text_sha256"]:
                raise ValueError("Snapshot text checksum mismatch")
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate source article")


def validate_profiles(snapshot: dict[str, Any], profiles_doc: dict[str, Any], snapshot_sha256: str) -> None:
    validate_snapshot(snapshot)
    if profiles_doc["snapshot_sha256"] != snapshot_sha256:
        raise ValueError("TAC snapshot mismatch")
    articles = {a["article_id"]: a for a in snapshot["articles"]}
    ids = [p["article_id"] for p in profiles_doc["profiles"]]
    if len(set(ids)) != len(ids) or set(ids) != set(articles):
        raise ValueError("TAC article inventory mismatch")
    for profile in profiles_doc["profiles"]:
        conclusion_kind = profile.get('conclusion_kind')
        conclusions = [s for s in profile['sections'] if s['kind'] == 'C']
        if conclusion_kind is not None:
            if conclusion_kind not in {'section', 'summary_passages', 'not_detected'}:
                raise ValueError('Unknown TAC conclusion kind')
            if ((conclusion_kind == 'not_detected') != (not conclusions)
                    or (conclusion_kind == 'summary_passages' and
                        any(not s['method'].startswith('proposed_implicit_summary_passage') for s in conclusions))):
                raise ValueError('TAC conclusion kind differs from proposals')
        article = articles[profile["article_id"]]
        if profile["original_pdf_sha256"] != article["original_pdf_sha256"] or profile["original_pdf_path"] != article["original_pdf_path"]:
            raise ValueError("TAC original PDF identity mismatch")
        pages = {p["page"]: p for p in article["pages"]}
        for section in [*profile["sections"], *profile.get("document_type_evidence", [])]:
            source = pages[section["page"]]
            if not 0 <= section["start"] < section["end"] <= len(source["text"]):
                raise ValueError("TAC evidence span outside frozen page")
            if (source["text"][section["start"]:section["end"]] != section["quote"] or
                source["text_sha256"] != section["page_text_sha256"] or
                source["layer"] != section["layer"] or source["layer_id"] != section["layer_id"]):
                raise ValueError("TAC evidence differs from frozen page")


def extract(snapshot_path: Path, output: Path) -> None:
    from scripts.tac_front_matter import COVER, geometry_abstract
    from scripts.tac_section_flow import continuation, summary_passages
    if output.exists():
        raise FileExistsError(output)
    raw = snapshot_path.read_bytes()
    snapshot = json.loads(raw)
    validate_snapshot(snapshot)
    for name, checksum in snapshot["pdf_hashes"].items():
        if digest(Path(name).read_bytes()) != checksum:
            raise ValueError(f"Source PDF checksum mismatch: {name}")
    profiles = []
    for article in snapshot["articles"]:
        pages = [add_layout_blocks(page) for page in article["pages"]]
        front = pages[0] if pages else None
        title, title_candidates = title_from_layout(front) if front else (None, [])
        if front and COVER.search(front["text"]):
            for later in pages[1:3]:
                if COVER.search(later["text"]):
                    continue
                later_title, later_candidates = title_from_layout(later)
                if later_title:
                    front, title, title_candidates = later, later_title, later_candidates
                    break
        front_start = int(front["page"]) if front else 1
        type_evidence = []
        conference = re.search(r"\d+(?:st|nd|rd|th)\s+ECS Meeting,\s*Abstract[^\n]*", pages[0]["text"]) if pages else None
        if conference:
            item = asdict(span(pages[0], "T", conference.start(), conference.end(), "conference_abstract_label"))
            item.pop("kind")
            type_evidence.append(item)
        sections, diagnostics = heading_spans(pages, front_start)
        if front_start != 1:
            diagnostics.append(f"Front matter begins on PDF page {front_start}; publisher cover skipped")
        if not any(item.kind == "A" for item in sections):
            proposal = implicit_russian_abstract([front]) if front else None
            if proposal:
                sections.append(proposal)
                diagnostics.append("A: implicit Russian publisher pattern; needs boundary review")
        if not any(item.kind == "A" for item in sections) and pages and not conference:
            proposal_raw, diagnostic = geometry_abstract(front, asdict(title), STOP) if title and front else (
                None, "A: no title/byline geometry anchor")
            proposal = TACSpan(**proposal_raw) if proposal_raw else None
            diagnostics.append(diagnostic)
            if proposal:
                sections.append(proposal)
            elif title and front:
                legacy, legacy_diagnostic = unlabelled_abstract(front, title)
                diagnostics.append(legacy_diagnostic)
                if legacy:
                    sections.append(legacy)
        if conference and not any(item.kind == "A" for item in sections):
            diagnostics.append("A: conference abstract; no separately delimited A proposal; body is not relabelled as a section")
        continued = []
        for item in sections:
            if item.kind == "A":
                fragments = continuation(pages, asdict(item), STOP)
                continued.extend(TACSpan(**s) for s in fragments)
                if fragments != [asdict(item)]:
                    diagnostics.append('A: unfinished proposal extended through adjacent exact text flow; boundary review required')
            else:
                continued.append(item)
        sections = continued
        conclusion_kind = 'section' if any(s.kind == 'C' for s in sections) else 'not_detected'
        if conclusion_kind == 'not_detected' and not conference:
            passages, passage_diagnostics = summary_passages(pages, STOP)
            diagnostics.extend(passage_diagnostics)
            if passages:
                sections.extend(TACSpan(**s) for s in passages)
                conclusion_kind = 'summary_passages'
        for proposed in sections:
            if proposed.kind == "A" and not re.search(r"[.!?][\s\"'’”)]*$", proposed.quote):
                diagnostics.append(f"A: PDF page {proposed.page} proposal has no terminal sentence boundary; continuation review required")
        if title:
            sections.insert(0, title)
        else:
            diagnostics.append("T: no unique exact layout block; metadata title is not a verified PDF title")
        profiles.append({"article_id": article["article_id"], "metadata_title": article["title"],
                         "doi": article["doi"], "original_pdf_path": article["original_pdf_path"],
                         "original_pdf_sha256": article["original_pdf_sha256"],
                         "state": "needs_boundary_review", "sections": [asdict(item) for item in sections],
                         "front_page": front_start,
                         "document_type": "conference_abstract" if conference else "unclassified",
                         "document_type_evidence": type_evidence,
                         "conclusion_kind": conclusion_kind,
                         "section_status": {kind: "proposed" if any(s.kind == kind for s in sections) else
                                            "not_separately_delimited" if kind == "A" and conference else "not_detected"
                                            for kind in ("T", "A", "C")},
                         "title_candidates": title_candidates, "diagnostics": diagnostics,
                         "layout_warnings": [{"page": page["page"], "messages": page["layout_warnings"]}
                                             for page in pages if page["layout_warnings"]]})
    write_new(output, {"schema": RULE_VERSION, "created_at": datetime.now(UTC).isoformat(),
                       "component_sha256": {name: digest(Path(name).read_bytes()) for name in
                                            ("scripts/tac_front_matter.py", "scripts/tac_section_flow.py", "scripts/tac_metadata.py")},
                       "snapshot_sha256": digest(raw), "code_sha256": digest(Path(__file__).read_bytes()), "profiles": profiles})
    print(json.dumps({"output": str(output), "documents": len(profiles),
                      "with_sections": {kind: sum(any(s["kind"] == kind for s in p["sections"]) for p in profiles)
                                        for kind in ("T", "A", "C")}}))


def lexical_score(query: str, text: str) -> float:
    """Experiment-only token coverage. No claim of BM25 or semantic entailment."""
    terms = set(re.findall(r"[\w+-]+", query.casefold())) - {"and", "in", "or", "the", "using", "vs", "with"}
    terms = {term for term in terms if len(term) >= 2}
    normalized = text.casefold().translate(str.maketrans({"ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff"}))
    return sum(bool(re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", normalized)) for term in terms) / len(terms) if terms else 0.0


def rank_tac(query: str, profiles: list[dict[str, Any]], article_k: int) -> list[tuple[float, dict[str, Any]]]:
    variants = build_query_bundle(query).variants
    ranked = []
    for profile in profiles:
        # Include only exact-source section proposals. Never insert filename titles.
        text = "\n".join(item["quote"] for item in profile["sections"])
        score = max(lexical_score(variant.text, text) for variant in variants)
        if score > 0:
            ranked.append((score, profile))
    ranked.sort(key=lambda item: (-item[0], item[1]["article_id"]))
    return ranked[:article_k]


def tac_response(query: str, ranking: list[tuple[float, dict[str, Any]]]) -> SearchResponse:
    results = []
    for score, profile in ranking:
        sections = profile["sections"]
        pages = [item["page"] for item in sections]
        quote = "\n".join(item["quote"] for item in sections)
        results.append(SearchResult(article_id=profile["article_id"], chunk_id="tac:" + profile["article_id"],
                                    title=profile["metadata_title"], doi=profile["doi"],
                                    page_start=min(pages), page_end=max(pages), source_type="experimental_tac_proposals",
                                    snippet=quote, full_text=quote, score=score, retrieval_method="experimental_tac_lexical",
                                    text_layer="mixed" if len({item["layer"] for item in sections}) > 1 else sections[0]["layer"]))
    return SearchResponse(query, results, {"strategy": "experimental_tac_lexical", "proposed_boundaries": True})


def staged_replay(
    full: SearchResponse, selected_ids: set[str], *, top_k: int, rescue: bool,
) -> SearchResponse:
    selected = [result for result in full.results if result.article_id in selected_ids][:top_k]
    filled = []
    if rescue and len(selected) < top_k:
        kept = {item.chunk_id for item in selected}
        filled = [result for result in full.results if result.chunk_id not in kept][:top_k - len(selected)]
    return SearchResponse(full.query, [*selected, *filled], {
        "strategy": "tac_shortlist_replay", "pool_size": len(full.results), "rescue": rescue,
        "rescue_count": len(filled), "selected_article_ids": sorted(selected_ids),
        "limitation": "Filters a global production pool; does not measure restricted-index search latency.",
    })


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary = {}
    for name in ("production", "tac_only", "expanded_pool", "tac_deep", "tac_deep_rescue"):
        items = [row["methods"][name] for row in rows]
        answerable = [item for item in items if item["answerable"]]
        def mean(field: str, source: list[dict[str, Any]] = answerable) -> float | None:
            values = [float(item[field]) for item in source if item[field] is not None]
            return sum(values) / len(values) if values else None
        summary[name] = {"passed": sum(item["passed"] for item in items), "total": len(items),
                         "article_recall": mean("article_recall_at_k"), "chunk_recall": mean("chunk_recall_at_k"),
                         "judged_hit_fraction": mean("article_precision_at_k"), "mrr": mean("mrr"),
                         "false_answerable": sum(not item["passed"] for item in items if not item["answerable"]),
                         "regressions_vs_production": [row["id"] for row in rows if row["methods"]["production"]["passed"]
                                                       and not row["methods"][name]["passed"]]}
    return summary


def replay_saved(snapshot_path: Path, profiles_path: Path, baseline_path: Path, questions_path: Path, output: Path) -> None:
    """Re-evaluate a new parser against identical saved production search results."""
    snapshot_raw, profiles_raw = snapshot_path.read_bytes(), profiles_path.read_bytes()
    snapshot, profiles_doc = json.loads(snapshot_raw), json.loads(profiles_raw)
    validate_profiles(snapshot, profiles_doc, digest(snapshot_raw))
    baseline_raw = baseline_path.read_bytes()
    baseline = json.loads(baseline_raw)
    questions_raw = questions_path.read_bytes()
    if baseline["snapshot_sha256"] != digest(snapshot_raw) or baseline["questions_sha256"] != digest(questions_raw):
        raise ValueError("Frozen retrieval inputs differ from current replay inputs")
    questions = load_extended_questions(questions_path)
    previous = {q["id"]: q for q in baseline["questions"]}
    if len(previous) != len(baseline["questions"]) or set(previous) != {q.id for q in questions}:
        raise ValueError("Frozen retrieval question inventory mismatch")
    settings = baseline["settings"]
    top_k, article_k = settings["top_k"], settings["article_k"]
    checksum_map = {a["article_id"]: a["original_pdf_sha256"] for a in snapshot["articles"]}
    texts = {c["chunk_id"]: c["text"] for a in snapshot["articles"] for c in a["chunks"]}
    chunk_sources = {c["chunk_id"]: (a, c) for a in snapshot["articles"] for c in a["chunks"]}
    rows = []
    for question in questions:
        prior = previous[question.id]
        if prior["query"] != question.query or prior["answerable"] != question.answerable:
            raise ValueError("Frozen question semantics mismatch")
        results = [SearchResult(**item) for item in prior["full_pool"]]
        if len({r.chunk_id for r in results}) != len(results):
            raise ValueError("Duplicate frozen pool chunk")
        for result in results:
            article, source = chunk_sources[result.chunk_id]
            if (result.article_id != article["article_id"] or result.full_text != source["text"] or
                result.page_start != source["page_start"] or result.page_end != source["page_end"] or
                result.text_layer != source["text_layer"] or result.source_type != source["source_type"]):
                raise ValueError("Frozen retrieval evidence differs from corpus snapshot")
        full = SearchResponse(question.query, results)
        ranking = rank_tac(question.query, profiles_doc["profiles"], article_k)
        selected = {p["article_id"] for _score, p in ranking}
        responses = {"tac_only": tac_response(question.query, ranking),
                     "tac_deep": staged_replay(full, selected, top_k=top_k, rescue=False),
                     "tac_deep_rescue": staged_replay(full, selected, top_k=top_k, rescue=True)}
        # Preserve production controls byte-for-byte in the decoded JSON structure.
        methods = {name: prior["methods"][name] for name in ("production", "expanded_pool")}
        for name, response in responses.items():
            source_texts = texts if name != "tac_only" else {r.chunk_id: r.full_text or r.snippet for r in response.results}
            methods[name] = _evaluate_extended_question(question, response, checksum_map, source_texts, elapsed_ms=0, top_k=top_k)
        rows.append({"id": question.id, "query": question.query, "answerable": question.answerable,
                     "tac_candidates": [{"article_id": p["article_id"], "score": score} for score, p in ranking],
                     "methods": methods})
    output.mkdir(parents=True, exist_ok=False)
    write_new(output / "report.json", {"schema": "tac_frozen_search_replay_v0.1", "rule": profiles_doc["schema"],
                                       "created_at": datetime.now(UTC).isoformat(),
                                       "snapshot_sha256": digest(snapshot_raw), "profiles_sha256": digest(profiles_raw),
                                       "baseline_report_sha256": digest(baseline_raw), "questions_sha256": digest(questions_raw),
                                       "code_sha256": digest(Path(__file__).read_bytes()), "settings": settings,
                                       "limitations": ["No new live search or latency measurements.",
                                                        "Production controls copied from frozen baseline; same candidate pools.",
                                                        "Development inputs; no independent scientific gold.",
                                                        "No change to shortlist or rescue policy."],
                                       "summary": summarize(rows), "questions": rows})
    print(json.dumps(summarize(rows)))


def compare(snapshot_path: Path, profiles_path: Path, questions_path: Path, output: Path, article_k: int, top_k: int, pool_k: int) -> None:
    from sqlalchemy import select, text

    from app.core.config import get_settings
    from app.db.models import Article, Chunk, Page
    from app.db.session import SessionLocal

    if min(article_k, top_k, pool_k) <= 0 or pool_k < top_k:
        raise ValueError("Positive limits required; pool_k must be >= top_k")
    snapshot_raw = snapshot_path.read_bytes()
    snapshot = json.loads(snapshot_raw)
    validate_snapshot(snapshot)
    profiles_raw = profiles_path.read_bytes()
    profiles_doc = json.loads(profiles_raw)
    if profiles_doc["snapshot_sha256"] != digest(snapshot_raw):
        raise ValueError("TAC snapshot mismatch")
    articles = {item["article_id"]: item for item in snapshot["articles"]}
    profiles = profiles_doc["profiles"]
    if set(articles) != {item["article_id"] for item in profiles}:
        raise ValueError("TAC article inventory mismatch")
    for profile in profiles:
        pages = {p["page"]: p for p in articles[profile["article_id"]]["pages"]}
        for item in profile["sections"]:
            source = pages[item["page"]]
            if source["text"][item["start"]:item["end"]] != item["quote"] or source["text_sha256"] != item["page_text_sha256"]:
                raise ValueError("TAC evidence differs from frozen page")
    questions_raw = questions_path.read_bytes()
    questions = load_extended_questions(questions_path)
    if len({q.id for q in questions}) != len(questions) or any(not re.fullmatch(r"[A-Za-z0-9_-]+", q.id) for q in questions):
        raise ValueError("Question IDs must be unique safe filenames")
    checksums = {key: item["original_pdf_sha256"] for key, item in articles.items()}
    chunk_texts = {c["chunk_id"]: c["text"] for a in articles.values() for c in a["chunks"]}
    settings = get_settings()
    output.mkdir(parents=True, exist_ok=False)
    with (output / "questions.yaml").open("xb") as stream:
        stream.write(questions_raw)
    write_new(output / "run_started.json", {"created_at": datetime.now(UTC).isoformat(),
                                           "code_sha256": digest(Path(__file__).read_bytes()),
                                           "profiles_sha256": digest(profiles_raw), "question_count": len(questions),
                                           "settings": {"article_k": article_k, "top_k": top_k, "pool_k": pool_k},
                                           "completion": "Only report.json with all questions confirms completion."})
    rows = []
    with SessionLocal() as session:
        session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
        current = {str(a.id): a.checksum_sha256 for a in session.scalars(select(Article))}
        if current != checksums:
            raise ValueError("Live article inventory differs from snapshot")
        current_chunks = {str(c.id): c.text for c in session.scalars(select(Chunk))}
        if current_chunks != chunk_texts:
            raise ValueError("Live chunk text differs from snapshot")
        page_map = {(str(a["article_id"]), p["page"]): (p["text"], p["layer"]) for a in articles.values() for p in a["pages"]}
        current_pages = {(str(p.article_id), p.page_number): (p.text or "", p.selected_text_layer) for p in session.scalars(select(Page))}
        if current_pages != page_map:
            raise ValueError("Live selected pages differ from snapshot")
        for question in questions:
            begin = time.perf_counter()
            baseline = search_chunks(session, question.query, "literature", top_k, method="hybrid_cross_lingual", settings=settings)
            baseline_ms = (time.perf_counter() - begin) * 1000
            begin = time.perf_counter()
            full = search_chunks(session, question.query, "literature", pool_k, method="hybrid_cross_lingual", settings=settings)
            pool_ms = (time.perf_counter() - begin) * 1000
            begin = time.perf_counter()
            ranking = rank_tac(question.query, profiles, article_k)
            tac_ms = (time.perf_counter() - begin) * 1000
            selected_ids = {item[1]["article_id"] for item in ranking}
            responses = {
                "production": baseline, "tac_only": tac_response(question.query, ranking),
                "expanded_pool": SearchResponse(full.query, full.results[:top_k], full.metadata),
                "tac_deep": staged_replay(full, selected_ids, top_k=top_k, rescue=False),
                "tac_deep_rescue": staged_replay(full, selected_ids, top_k=top_k, rescue=True),
            }
            evaluated = {}
            for name, response in responses.items():
                texts = chunk_texts if name != "tac_only" else {r.chunk_id: r.full_text or r.snippet for r in response.results}
                evaluated[name] = _evaluate_extended_question(question, response, checksums, texts, elapsed_ms=0, top_k=top_k)
            row = {"id": question.id, "query": question.query, "answerable": question.answerable,
                   "timings_ms": {"production": baseline_ms, "expanded_pool": pool_ms, "tac_rank": tac_ms},
                   "tac_candidates": [{"article_id": profile["article_id"], "score": score} for score, profile in ranking],
                   "methods": evaluated, "full_pool": [asdict(result) for result in full.results]}
            write_new(output / (question.id + ".json"), row)
            rows.append(row)
            print(json.dumps({"question": question.id, "completed": len(rows), "total": len(questions)}), flush=True)
    # Recheck immutable source files after the actual experiment.
    for name, checksum in snapshot["pdf_hashes"].items():
        if digest(Path(name).read_bytes()) != checksum:
            raise ValueError(f"PDF changed during experiment: {name}")
    summary = summarize(rows)
    write_new(output / "report.json", {"schema": "tac_retrieval_replay_v0.1", "created_at": datetime.now(UTC).isoformat(),
                                       "code_sha256": digest(Path(__file__).read_bytes()), "snapshot_sha256": digest(snapshot_raw),
                                       "profiles_sha256": digest(profiles_raw), "questions_sha256": digest(questions_raw),
                                       "settings": {"article_k": article_k, "top_k": top_k, "pool_k": pool_k,
                                                    "method": "hybrid_cross_lingual", "rule": RULE_VERSION},
                                       "limitations": ["Development questions; no independent scientific annotation.",
                                                        "Unjudged hits are not established irrelevant articles.",
                                                        "TAC-only chunk recall is lexical coverage, not a measurement extraction metric.",
                                                        "Global-pool replay; not a restricted-search speed benchmark.",
                                                        "TAC boundaries are unreviewed proposals, with text-order/layout limitations."],
                                       "summary": summary, "questions": rows})
    print(json.dumps(summary))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    extraction = commands.add_parser("extract")
    extraction.add_argument("--snapshot", type=Path, required=True)
    extraction.add_argument("--output", type=Path, required=True)
    comparison = commands.add_parser("compare")
    comparison.add_argument("--snapshot", type=Path, required=True)
    comparison.add_argument("--profiles", type=Path, required=True)
    comparison.add_argument("--questions", type=Path, required=True)
    comparison.add_argument("--output", type=Path, required=True)
    comparison.add_argument("--article-k", type=int, default=5)
    comparison.add_argument("--top-k", type=int, default=10)
    comparison.add_argument("--pool-k", type=int, default=20)
    replay = commands.add_parser("replay")
    replay.add_argument("--snapshot", type=Path, required=True)
    replay.add_argument("--profiles", type=Path, required=True)
    replay.add_argument("--baseline-report", type=Path, required=True)
    replay.add_argument("--questions", type=Path, required=True)
    replay.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "extract":
        extract(args.snapshot, args.output)
    elif args.command == "replay":
        replay_saved(args.snapshot, args.profiles, args.baseline_report, args.questions, args.output)
    else:
        compare(args.snapshot, args.profiles, args.questions, args.output, args.article_k, args.top_k, args.pool_k)


if __name__ == "__main__":
    main()
