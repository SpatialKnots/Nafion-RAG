"""Offline v0.2 explicit-reference candidate. Never reads reference answers."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import replace
from typing import Any

from app.generation.evidence_adequacy import LIGATURES
from app.retrieval.reranking import RUSSIAN_STOPWORDS, STOPWORDS
from app.retrieval.search import SearchResponse, SearchResult, make_snippet

VERSION = "explicit_reference_retrieval_v0.2"
SURNAME = r"[A-Z][a-z]+(?:[-'][A-Z]?[a-z]+)*"
CITATION = re.compile(
    rf"(?<![\w])(?P<first>{SURNAME})(?P<other>\s+(?:и|and|&)\s+{SURNAME}|"
    rf"\s+(?:et\s+al\.?|и\s+соавторы))?\s*\((?P<year>(?:19|20)\d{{2}})\)"
)
TOKEN = re.compile(r"\w+", re.UNICODE)


def tokens(value: str) -> set[str]:
    return set(TOKEN.findall(unicodedata.normalize("NFKC", value).casefold().translate(LIGATURES)))


def select(question: str, baseline: SearchResponse, corpus: dict[str, Any], articles: dict[str, Any],
           *, top_k: int) -> tuple[SearchResponse, dict[str, Any]]:
    if top_k <= 0:
        raise ValueError("top_k must be positive")
    diagnostic: dict[str, Any] = {"version": VERSION, "activated": False, "bibliographic_identity_verified": False}

    def unchanged(reason: str) -> tuple[SearchResponse, dict[str, Any]]:
        return baseline, {**diagnostic, "reason": reason}

    citations = list(CITATION.finditer(question))
    if len(citations) != 1:
        return unchanged("no_single_explicit_author_year")
    citation = citations[0]
    surname, year = citation["first"], citation["year"]
    diagnostic.update(surname=surname, year=year, source_question_span={"start": citation.start(), "end": citation.end(),
                                                                     "text": citation.group()})
    matched = []
    for article_id, article in articles.items():
        author_names = " ".join(a["name"] for a in (article.get("authors") or []) if isinstance(a, dict) and "name" in a)
        metadata_tokens = tokens(" ".join([article.get("title") or "", author_names, str(article.get("year") or "")]))
        if tokens(surname) <= metadata_tokens and year in metadata_tokens:
            matched.append(article_id)
    diagnostic["matching_article_ids"] = sorted(matched)
    if len(matched) != 1:
        return unchanged("ambiguous_metadata" if matched else "no_metadata_match")
    article_id = matched[0]
    chunks = [r for r in corpus.values() if r["article_id"] == article_id and r["full_text"].strip()]
    if not chunks:
        return unchanged("no_usable_source_chunks")
    chunks.sort(key=lambda r: (r["chunk_index"], r["chunk_id"]))
    # Body matching does not use the citation's names/year, or any gold-derived terms.
    topical_query = question[:citation.start()] + " " + question[citation.end():]
    query_tokens = {t for t in tokens(topical_query) - STOPWORDS - RUSSIAN_STOPWORDS if len(t) >= 2 and not t.isdigit()}
    scores = {r["chunk_id"]: len(tokens(r["full_text"]) & query_tokens) for r in chunks}
    ranked = [chunks[0], *sorted(chunks[1:], key=lambda r: (-scores[r["chunk_id"]], r["chunk_index"], r["chunk_id"]))]
    results = [SearchResult(
        article_id=article_id, chunk_id=r["chunk_id"], title=r["title"], doi=r["doi"],
        page_start=r["page_start"], page_end=r["page_end"], source_type=r["source_type"], text_layer=r["text_layer"],
        snippet=make_snippet(r["full_text"], question), full_text=r["full_text"], score=float(scores[r["chunk_id"]]),
        retrieval_method=VERSION, method_scores={"original_question_body_token_count": float(scores[r["chunk_id"]])},
        method_ranks={"explicit_reference_source_order": index},
    ) for index, r in enumerate(ranked[:top_k], 1)]
    diagnostic.update(activated=True, reason="unique_metadata_candidate", first_chunk_policy="stored_chunk_index",
                      selected_article_id=article_id, query_body_tokens=sorted(query_tokens),
                      original_top_k=top_k, raw_text_preserved=True,
                      coauthor_metadata_complete="not_established", source_statement_ownership="unverified")
    metadata = {**baseline.metadata, "offline_explicit_reference": diagnostic}
    return replace(baseline, results=results, metadata=metadata), diagnostic
