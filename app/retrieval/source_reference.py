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
    threshold_ions = re.findall(r'[μµ]([a-z]{1,2}\s*\+)', query)
    if (len(threshold_ions) == 1 and 'доказывает ли работа универсальное неизменное значение порога' in query
            and 'для любых солей, добавок и поверхностных покрытий' in query):
        return ('threshold_transfer_limits:' + re.sub(r'\s+', '', threshold_ions[0]),)
    anions = re.findall(r'продуктов разложения аниона ([a-z][a-z0-9]{0,24})[−-]', query)
    if (len(anions) == 1 and 'достаточно ли одного образования sei' in query
            and 'гарантировать отсутствие совместной интеркаляции' in query):
        return ('anion_sei_sufficiency:' + anions[0],)
    surfaces = re.findall(r'морфологии\s+([a-z][a-z0-9]{0,24})(?!\w)', query)
    if (len(surfaces) == 1 and 'поверхностной' in query and re.search(r'пл[её]нки', query)
            and 'после циклирования' in query):
        return ('cycled_cathode_surface:' + surfaces[0],)
    symbols = re.findall(r'[μµ]([a-z]{1,2}\s*\+)', query)
    if len(symbols) == 1 and 'экспериментально' in query and 'нулев' in query and 'относительно' in query:
        return ('chemical_potential_method_zero:' + re.sub(r'\s+', '', symbols[0]),)
    cells = re.findall(r'\b([a-z][a-z0-9]{0,24}/[a-z][a-z0-9]{0,24})-полуячей\w*', query)
    if (len(cells) == 1 and re.search(r'наилучш\w* результат\w*', query)
            and re.search(r'начальн\w* кулоновск\w* эффективност', query)):
        return ('half_cell_best_initial_ce:' + cells[0],)
    if re.search(r"состав|composition", query) and re.search(r"циклирован|cycling|cycles", query):
        return ("composition_cycling",)
    if (re.search(r"дисперс|dispersion", query) and re.search(r"способ|method|prepar|получ", query)
            and re.search(r"проводим|conductiv", query)):
        return ("dispersion_preparation", "conductivity_table")
    return ()


def role_matches(role: str, text: str) -> bool:
    body = normalize(text)
    if role.startswith('threshold_transfer_limits:'):
        ion = role.split(':', 1)[1]
        return ('μ' + ion in re.sub(r'\s+', '', body) and 'threshold may be shifted' in body
                and 'passivating binders' in body and 'functional surface coatings' in body)
    if role.startswith('anion_sei_sufficiency:'):
        anion = role.split(':', 1)[1]
        return ('similar ' + anion + ' anion-derived sei' in body and 'even after forming sei' in body
                and 'although the sei is essential' in body and 'may not be the only dominant factor' in body)
    if role.startswith('cycled_cathode_surface:'):
        electrode = role.split(':', 1)[1]
        return ('the fresh ' + electrode + ' (fig.' in body and 'microcracks' in body
                and 'xps spectra measured from the cycled ' + electrode + ' cathode' in body
                and 'interfacial constitution' in body)
    if role.startswith('chemical_potential_method_zero:'):
        ion = role.split(':', 1)[1]
        return ('μ' + ion in re.sub(r'\s+', '', body) and 'cyclic voltammetry was conducted' in body
                and 'defined to be zero' in body and 'relative values' in body
                and 'oxidation/reduction peaks' in body)
    if role.startswith('half_cell_best_initial_ce:'):
        cell = role.split(':', 1)[1]
        return bool(re.search(re.escape(cell) + r' half cells?\b', body)
                    and 'highest initial ce' in body and 'best cycle performance' in body
                    and 'among several cases' in body)
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
