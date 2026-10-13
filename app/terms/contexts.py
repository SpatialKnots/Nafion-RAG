"""Build and validate exact contexts using already-frozen pages and term evidence."""
from __future__ import annotations

import json
from typing import Any, Literal

from app.records.schema import source_identity, text_hash
from app.terms.schema import (
    ArticleContexts,
    Context,
    LexicalContainment,
    LocalTerm,
    Mention,
    SectionGroup,
    SourceFragment,
    TermUse,
    Transition,
)


def identity(kind: str, *parts: str) -> str:
    return text_hash(json.dumps([kind, *parts], ensure_ascii=False, separators=(",", ":")))


def fragment(article: dict[str, Any], page: dict[str, Any], start: int, end: int) -> SourceFragment:
    text = page["text"]
    if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(text):
        raise ValueError("Terms source fragment outside frozen page")
    if text_hash(text) != page["text_sha256"]:
        raise ValueError("Terms frozen page hash mismatch")
    data = {"article_id": article["article_id"], "original_pdf_path": article["original_pdf_path"],
            "original_pdf_sha256": article["original_pdf_sha256"], "page_number": page["page"],
            "text_layer_id": page["layer_id"], "text_layer": page["layer"],
            "layer_pdf_path": page["layer_pdf_path"], "layer_pdf_sha256": page["layer_pdf_sha256"],
            "page_text_sha256": page["text_sha256"], "start": start, "end": end,
            "quote": text[start:end], "quote_sha256": text_hash(text[start:end])}
    return SourceFragment.model_validate({**data, "region_id": source_identity(data)})


def lexical_containment(uses: list[TermUse], mentions: list[Mention]) -> list[LexicalContainment]:
    """All proper containments within the same context/source, never string-only links."""
    sources = {m.mention_id: m.source for m in mentions}
    result = []
    by_context: dict[str, list[TermUse]] = {}
    for use in uses:
        by_context.setdefault(use.context_id, []).append(use)
    for members in by_context.values():
        for outer in members:
            a = sources[outer.mention_id]
            for inner in members:
                b = sources[inner.mention_id]
                same_source = all(getattr(a, key) == getattr(b, key) for key in (
                    "article_id", "original_pdf_sha256", "page_number", "text_layer_id", "text_layer",
                    "layer_pdf_sha256", "page_text_sha256"))
                if (same_source and outer.term_id != inner.term_id and a.start <= b.start and b.end <= a.end
                        and (a.start, a.end) != (b.start, b.end)):
                    offset = b.start - a.start
                    if a.quote[offset:offset + len(b.quote)] != b.quote:
                        raise ValueError("Terms containment source slices disagree")
                    result.append(LexicalContainment(outer_use_id=outer.use_id, inner_use_id=inner.use_id))
    return sorted(result, key=lambda r: (r.outer_use_id, r.inner_use_id))


def build_article(article: dict[str, Any], profile: dict[str, Any], inventory: dict[str, Any]) -> ArticleContexts:
    if article["article_id"] != profile["article_id"] or article["article_id"] != inventory["article_id"]:
        raise ValueError("Terms context article scope mismatch")
    pages = {p["page"]: p for p in article["pages"]}
    context_map: dict[tuple[str, int, int, int], Context] = {}
    mentions: dict[str, Mention] = {}
    uses: dict[str, TermUse] = {}
    terms = []
    for section in profile["sections"]:
        source = fragment(article, pages[section["page"]], section["start"], section["end"])
        if (source.quote != section["quote"] or source.page_text_sha256 != section["page_text_sha256"]
                or source.text_layer_id != section["layer_id"] or source.text_layer != section["layer"]):
            raise ValueError("Terms context differs from frozen section")
        key = (section["kind"], section["page"], section["start"], section["end"])
        if key in context_map:
            raise ValueError("Terms duplicate section context")
        statuses = {e["tac_boundary_status"] for t in inventory["inventory"] for e in t["evidence"]
                    if (e["kind"], e["page"], e["section_start"], e["section_end"]) == key}
        if len(statuses) > 1:
            raise ValueError("Terms context boundary statuses disagree")
        context_map[key] = Context(context_id=identity("tac_context", source.region_id, section["kind"]),
                                   kind=section["kind"], source=source, method=section["method"],
                                   boundary_status=next(iter(statuses), "unreviewed"))
    for term in inventory["inventory"]:
        term_uses = []
        for e in term["evidence"]:
            context = context_map[(e["kind"], e["page"], e["section_start"], e["section_end"])]
            source = fragment(article, pages[e["page"]], e["start"], e["end"])
            if (source.quote != e["quote"] or source.text_layer_id != e["layer_id"] or source.text_layer != e["layer"]
                    or source.page_text_sha256 != e["page_text_sha256"]
                    or not context.source.start <= source.start < source.end <= context.source.end):
                raise ValueError("Terms mention differs from inventory evidence/context")
            mention_id = identity("term_mention", source.region_id)
            mention = Mention(mention_id=mention_id, source=source)
            if mention_id in mentions and mentions[mention_id] != mention:
                raise ValueError("Terms mention identity collision")
            mentions[mention_id] = mention
            use_id = identity("term_use", term["candidate_id"], mention_id, context.context_id)
            if use_id in uses:
                raise ValueError("Terms duplicate use")
            uses[use_id] = TermUse(use_id=use_id, term_id=term["candidate_id"], mention_id=mention_id, context_id=context.context_id)
            term_uses.append(use_id)
        terms.append(LocalTerm(term_id=term["candidate_id"], term=term["term"], label=term["label"], use_ids=sorted(term_uses)))
    contexts = sorted(context_map.values(), key=lambda c: (c.kind, c.source.page_number, c.source.start, c.source.end))
    groups = []
    for kind in ("T", "A", "C"):
        members = [c for c in contexts if c.kind == kind]
        transitions = []
        for a, b in zip(members, members[1:], strict=False):
            gap = b.source.page_number - a.source.page_number
            geometry: Literal["same_page_disjoint", "same_page_overlap", "adjacent_pages", "page_gap"]
            geometry = ("same_page_overlap" if b.source.start < a.source.end else "same_page_disjoint") if gap == 0 else (
                "adjacent_pages" if gap == 1 else "page_gap")
            transitions.append(Transition(from_context_id=a.context_id, to_context_id=b.context_id, geometry=geometry))
        groups.append(SectionGroup(kind=kind, context_ids=[c.context_id for c in members], transitions=transitions))
    ordered_uses = sorted(uses.values(), key=lambda u: u.use_id)
    ordered_mentions = sorted(mentions.values(), key=lambda m: m.mention_id)
    return ArticleContexts(article_id=article["article_id"], terms=terms, mentions=ordered_mentions, contexts=contexts,
                           uses=ordered_uses, section_groups=groups, containment=lexical_containment(ordered_uses, ordered_mentions),
                           diagnostics=["Exact frozen TAC page contexts; paragraph/sentence segmentation is not performed.",
                                        "Section groups preserve separate regions; text continuity is not asserted.",
                                        "Lexical span containment does not establish scientific relations or synonymy."])


def validate_article(article: dict[str, Any], profile: dict[str, Any], inventory: dict[str, Any], data: dict[str, Any]) -> ArticleContexts:
    actual = ArticleContexts.model_validate(data)
    expected = build_article(article, profile, inventory)
    if actual != expected:
        raise ValueError("Terms context references/source/containment differ from authoritative frozen inputs")
    return actual
