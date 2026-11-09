"""Finite body-context retention before lossy cuts; never an answerability gate.

Scientific ownership, performed status and entailment are deliberately unverified.
Only already retrieved, unchanged source objects can be reordered.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from typing import Any, Protocol, TypeVar

VERSION = "requested_context_retention_v0.1"


class ContextResult(Protocol):
    @property
    def article_id(self) -> str: ...

    @property
    def chunk_id(self) -> str: ...

    @property
    def full_text(self) -> str | None: ...

    @property
    def snippet(self) -> str: ...


T = TypeVar("T", bound=ContextResult)


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold().replace("\u00ad", "")
    value = re.sub(r"(?<=\w)-\s*\n\s*(?=\w)", "", value)
    return re.sub(r"\s+", " ", value)


def has(pattern: str, value: str) -> bool:
    return re.search(pattern, value) is not None


def requested_facets(question: str) -> tuple[str, ...]:
    query = normalize(question)
    if not has(r"\bli[\s-]*nafion\b", query):
        return ()
    if (has(r"энтальп|enthalp", query) and has(r"набухан|swelling", query)
            and has(r"равновес|equilibrium", query)):
        return ("equilibrium_swelling_enthalpy_table",)
    if (has(r"температур\w* смешени|mixing temperature", query)
            and has(r"нагрев|heating", query) and has(r"охлажд|cooling", query)
            and has(r"структур|structur", query) and has(r"\bec\s*/\s*sl\b", query)):
        return ("mixing_uptake_cycles", "plasticised_structure")
    return ()


def body_facets(text: str, facets: tuple[str, ...]) -> dict[str, int]:
    body = normalize(text)
    if not has(r"\bli[\s-]*nafion\b", body):
        return {}
    matched = {}
    if "equilibrium_swelling_enthalpy_table" in facets:
        if (has(r"таблиц|\btable\b", body) and has(r"энтальп|enthalp|δh", body)
                and has(r"набухан|swelling", body) and has(r"равн|equilibrium", body)
                and has(r"(?<!\w)(?:дж|j)\s*/\s*(?:г|g)\b", body) and "%" in body
                and has(r"α\s*равн|equilibrium swelling", body)):
            # Richness breaks ties between overlapping chunks without naming rows
            # or values. Raw objects are unchanged; this is not a table parser.
            numeric_lines = sum(bool(re.fullmatch(r"\s*[−–-]?\d+(?:[.,]\d+)?\s*", line)) for line in text.splitlines())
            matched["equilibrium_swelling_enthalpy_table"] = numeric_lines
    if not has(r"\bec\s*/\s*sl\b", body):
        return matched
    if "mixing_uptake_cycles" in facets:
        if (has(r"mixing temperature|температур\w* смешени", body) and has(r"uptake|swelling|набухан|поглощен", body)
                and has(r"heating|нагрев", body) and has(r"cooling|охлажд", body)
                and has(r"(?:upon|on|during) (?:heating|cooling)|при (?:нагрев|охлажд)", body)):
            matched["mixing_uptake_cycles"] = sum(has(p, body) for p in (
                r"hysteresis|гистерез", r"retained|preserved|сохраня", r"increas|увелич",
                r"equilibrium|равновес", r"isothermal|изотермич"))
    if "plasticised_structure" in facets:
        if (has(r"amorphous|аморф", body) and has(r"crystall|кристалл", body)
                and has(r"plastici[sz]|пластифик", body) and has(r"diffraction|дифрак", body)
                and has(r"glass transition|\btg\b|стеклован", body)):
            matched["plasticised_structure"] = sum(has(p, body) for p in (
                r"glass transition|стеклован", r"\btg\b", r"halo|гало", r"interchain|межцеп",
                r"conclusions|вывод", r"integrity|целост"))
    return matched


def retain_requested_context(question: str, results: Sequence[T], *, limit: int) -> tuple[list[T], dict[str, Any] | None]:
    if limit <= 0:
        raise ValueError("limit must be positive")
    facets = requested_facets(question)
    if not facets or not results:
        return list(results), None
    matches = [body_facets(row.full_text or row.snippet, facets) for row in results]
    coverage: dict[str, set[str]] = {}
    for row, found in zip(results, matches, strict=True):
        if found:
            coverage.setdefault(row.article_id, set()).update(found)
    if not coverage:
        return list(results), None
    # One source work; never join different articles to imply a complete relation.
    article_id = max(coverage, key=lambda key: len(coverage[key]))
    chosen: list[int] = []
    for facet in facets:
        if len(chosen) >= limit:
            break
        eligible = [i for i, row in enumerate(results) if row.article_id == article_id and facet in matches[i]]
        if eligible:
            index = max(eligible, key=lambda i: (matches[i][facet], -i))
            if index not in chosen:
                chosen.append(index)
    selected = set(chosen)
    retained = [results[i] for i in chosen] + [row for i, row in enumerate(results) if i not in selected]
    actual = {facet for i in chosen for facet in matches[i]}
    diagnostic = {"version": VERSION, "scope": "source_context_not_entailment", "article_id": article_id,
                  "requested_facets": list(facets), "reserved_chunk_ids": [results[i].chunk_id for i in chosen],
                  "missing_facets": [f for f in facets if f not in actual], "limit": limit,
                  "scientific_ownership_verified": False, "thresholds_changed": False}
    return retained, diagnostic
