"""Bounded explicit bibliography lookup and source-role retention, not admission."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, TypeVar

from app.retrieval.requested_context import ContextResult

VERSION = "explicit_source_reference_v0.1"
SURNAME = r"[A-Z][a-z]+(?:[-'][A-Z]?[a-z]+)*"
CITATION = re.compile(
    rf"(?<!\w)(?P<first>{SURNAME})(?P<other>\s+(?:и|and|&)\s+{SURNAME}|"
    rf"\s+(?:et\s+al\.?|и\s+соавторы))?\s*\((?P<year>(?:19|20)\d{{2}})\)"
)
T = TypeVar("T", bound=ContextResult)


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold().replace("\u00ad", "")
    value = re.sub(r"(?<=\w)-\s*\n\s*(?=\w)", "", value)
    return re.sub(r"\s+", " ", value)


def tokens(value: str) -> set[str]:
    return set(re.findall(r"\w+", normalize(value)))


@dataclass(frozen=True)
class Reference:
    surname: str
    year: str
    start: int
    end: int


def reference(question: str) -> Reference | None:
    matches = list(CITATION.finditer(question))
    if len(matches) != 1:
        return None
    match = matches[0]
    return Reference(match["first"], match["year"], match.start(), match.end())


def resolve(citation: Reference, articles: Mapping[str, Mapping[str, Any]]) -> list[str]:
    matches = []
    for article_id, article in articles.items():
        names = " ".join(a["name"] for a in (article.get("authors") or []) if isinstance(a, dict) and "name" in a)
        words = tokens(" ".join([article.get("title") or "", names, str(article.get("year") or "")]))
        if tokens(citation.surname) <= words and citation.year in words:
            matches.append(article_id)
    return sorted(matches)


def roles(question: str) -> tuple[str, ...]:
    query = normalize(question)
    if re.search(r"состав|composition", query) and re.search(r"циклирован|cycling|cycles", query):
        return ("composition_cycling",)
    if (re.search(r"дисперс|dispersion", query) and re.search(r"способ|method|prepar|получ", query)
            and re.search(r"проводим|conductiv", query)):
        return ("dispersion_preparation", "conductivity_table")
    return ()


def role_matches(role: str, text: str) -> bool:
    body = normalize(text)
    if role == "composition_cycling":
        return bool(re.search(r"\babstract\b", body) and "electrolyte" in body and re.search(r"cycles|times", body))
    if role == "dispersion_preparation":
        return bool(re.search(r"ethanol[ -]free|без этанола", body)
                    and re.search(r"distillation|дистилляц", body) and re.search(r"nafion", body))
    return bool(re.search(r"(?:\btab\.|\btable\b|таблиц)", body) and re.search(r"conductiv|проводим", body))


def rank_context(question: str, rows: Sequence[T], *, top_k: int) -> tuple[list[T], dict[str, Any]]:
    if top_k <= 0:
        raise ValueError("top_k must be positive")
    required = roles(question)
    citation = reference(question)
    topical = question if citation is None else question[:citation.start] + " " + question[citation.end:]
    query_words = {word for word in tokens(topical) if len(word) >= 2 and not word.isdigit()}
    chosen: list[int] = []
    for role in required:
        eligible = [i for i, row in enumerate(rows) if role_matches(role, row.full_text or row.snippet)]
        if eligible and len(chosen) < top_k:
            index = min(eligible, key=lambda i: (-len(tokens(rows[i].full_text or rows[i].snippet) & query_words),
                                               len(rows[i].full_text or rows[i].snippet), i))
            if index not in chosen:
                chosen.append(index)
    if rows and 0 not in chosen and len(chosen) < top_k:
        chosen.append(0)
    remaining = [i for i in range(len(rows)) if i not in chosen]
    remaining.sort(key=lambda i: (-len(tokens(rows[i].full_text or rows[i].snippet) & query_words), i))
    selected = [rows[i] for i in [*chosen, *remaining][:top_k]]
    return selected, {"version": VERSION, "requested_roles": list(required),
                      "missing_roles": [role for role in required if not any(role_matches(role, r.full_text or r.snippet)
                                                                             for r in selected)],
                      "source_statement_ownership_verified": False, "query_rewritten": False}
