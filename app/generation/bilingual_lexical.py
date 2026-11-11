"""Conservative RU/EN field mention coverage, not answer or scientific validation."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from typing import Any

from app.generation.providers import Evidence
from app.generation.query_qualifiers import occurrences
from app.retrieval.source_reference import reference

VERSION = 'bilingual_field_mention_coverage_v0.2'
# Each pair is a lexical equivalence, not a class of scientifically interchangeable properties.
ALIASES = {
    'synthesis': ('синтез', 'синтеза', 'синтезировали', 'синтезирован', 'synthesis', 'synthesized', 'synthesised'),
    'yield': ('выход', 'выхода', 'yield'),
    'purity': ('чистота', 'чистоты', 'чистоту', 'purity'),
    'purification': ('очистка', 'очистки', 'очищали', 'purification', 'purified'),
    'viscosity': ('вязкость', 'вязкости', 'вязкостью', 'вязкого течения', 'viscosity', 'viscosities', 'viscous flow'),
    'activation_energy': ('энергия активации', 'энергии активации', 'энергию активации', 'activation energy'),
    'ordering': ('порядок', 'порядке', 'расположены', 'order', 'ordered'),
    'ether_class': ('эфир', 'эфира', 'эфиры', 'эфиров', 'ether', 'ethers'),
}
PRIMARY = frozenset(ALIASES) - {'ordering', 'ether_class'}
FUNCTION_WORDS = frozenset(('по статье в работе как какой какая какие каком каков какова каковы был были '
                            'и его ее её их после продукта продукт получены для the what how were was and of in').split())
COUNTS = {'два': 2, 'двух': 2, 'три': 3, 'трех': 3, 'трёх': 3, 'четыре': 4, 'четырех': 4, 'четырёх': 4,
          'пять': 5, 'пяти': 5, 'six': 6, 'five': 5, 'four': 4, 'three': 3, 'two': 2}
UNSUPPORTED_QUERY = re.compile(
    r'(?<!\w)(?:почему|объясняют|доказывает|подтвержден|подтверждён|подтвержденный|подтверждённый|'
    r'гипотеза|достаточно|гарантировать|не|нет|без|любых|универсаль\w*|why|prove\w*|confirm\w*|'
    r'hypothes\w*|not|no|without|all|any)(?!\w)', re.I)
EXCLUDED_CONTEXT = re.compile(
    r'\b(?:previous|prior|earlier|literature|hypothes\w*|may|might|could|'
    r'no|not|never|without)\b|'
    r'предыдущ\w*|ранее|гипотез\w*|не\s+(?:измер\w*|определ\w*|исслед\w*)|'
    r'(?im:^\s*(?:references|keywords|title|литература|ключевые слова)\s*[:.]?)', re.I)
CHAIN = re.compile(r'(?<!\w)[A-Za-z][A-Za-z0-9]*(?:\s*>\s*[A-Za-z][A-Za-z0-9]*)+(?!\w)')


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _context(text: str, start: int, end: int) -> tuple[int, int]:
    boundaries = list(re.finditer(r'[.!?](?:\d+)?(?=\s|$)', text))
    left = max((m.end() for m in boundaries if m.end() <= start), default=0)
    right = min((m.end() for m in boundaries if m.start() >= end), default=len(text))
    return left, right


def _source_matches(text: str, aliases: Sequence[str], identifiers: Sequence[str] = ()) -> list[dict[str, Any]]:
    hits = []
    bibliography = re.search(r'(?im)^\s*(?:references|bibliography|список литературы)\s*$', text)
    for alias in aliases:
        for hit in occurrences(text, alias):
            left, right = _context(text, hit['start'], hit['end'])
            if ((bibliography is None or hit['start'] < bibliography.start())
                    and not EXCLUDED_CONTEXT.search(text[left:right])
                    and all(occurrences(text[left:right], name) for name in identifiers)):
                hits.append({**hit, 'alias': alias, 'context_start': left, 'context_end': right,
                             'context_text': text[left:right]})
    return hits


def assess(question: str, evidence: Sequence[Evidence], metadata: object) -> dict[str, Any] | None:
    """Return None outside this finite vocabulary; never mutate evidence or the question."""
    citation = reference(question)
    if citation is None or not re.search('[а-яё]', question, re.I):
        return None
    if re.fullmatch(re.escape(citation.surname) + r'\s*\(' + citation.year + r'\)',
                    question[citation.start:citation.end]) is None:
        # The existing resolver proves only the first surname, not additional named coauthors.
        return None
    topical = question[:citation.start] + ' ' * (citation.end - citation.start) + question[citation.end:]
    query_hits = {key: [hit for alias in aliases for hit in occurrences(topical, alias)] for key, aliases in ALIASES.items()}
    requested = [key for key, hits in query_hits.items() if hits]
    if len(set(requested) & PRIMARY) < 2:
        return None
    result: dict[str, Any] = {'version': VERSION, 'eligible': False, 'reason': 'unresolved_explicit_article_scope',
        'requested_concepts': requested, 'unknown_query_tokens': [], 'missing_by_fragment': [],
        'witnesses': [], 'scientific_support': 'not_evaluated', 'query_rewritten': False}
    if not isinstance(metadata, Mapping):
        return result
    article_id = metadata.get('article_id')
    if (metadata.get('resolved') is not True or not isinstance(article_id, str) or not evidence
            or metadata.get('matching_article_ids') != [article_id]
            or metadata.get('surname') != citation.surname or str(metadata.get('year')) != citation.year
            or any(item.article_id != article_id for item in evidence)):
        return result
    if UNSUPPORTED_QUERY.search(topical):
        result['reason'] = 'unsupported_causal_epistemic_or_negative_query'
        return result
    covered = {i for hits in query_hits.values() for hit in hits for i in range(hit['start'], hit['end'])}
    identifiers, counts, unknown = [], [], []
    for match in re.finditer(r'[^\W_]+(?:[-‐‑][^\W_]+)*', question):
        word = match.group()
        if citation.start <= match.start() < citation.end or all(i in covered for i in range(match.start(), match.end())):
            continue
        if word.casefold() in FUNCTION_WORDS:
            continue
        if word.casefold() in COUNTS:
            counts.append(COUNTS[word.casefold()])
        elif re.fullmatch(r'[A-Za-z][A-Za-z0-9-]*', word) and re.search('[A-Z]', word):
            identifiers.append(word)
        else:
            unknown.append(word)
    result.update(unknown_query_tokens=unknown, required_identifiers=identifiers, required_item_counts=counts)
    if unknown or len(counts) > 1 or (counts and 'ordering' not in requested):
        result['reason'] = 'unrecognized_query_terms_or_constraints'
        return result
    for item in evidence:
        if item.source_type not in {'main_text', 'method', 'figure_caption'}:
            result['missing_by_fragment'].append({'citation_id': item.citation_id, 'reason': 'unsupported_source_type'})
            continue
        matches = {key: _source_matches(item.text, ALIASES[key], identifiers if key in PRIMARY else ()) for key in requested}
        named = {name: _source_matches(item.text, (name,)) for name in identifiers}
        chains = [{'start': m.start(), 'end': m.end(), 'text': m.group()} for m in CHAIN.finditer(item.text)
                  if (not counts or len(m.group().split('>')) == counts[0])
                  and not EXCLUDED_CONTEXT.search(item.text[slice(*_context(item.text, m.start(), m.end()))])]
        missing = [key for key, hits in {**matches, **named}.items() if not hits]
        if counts and not chains:
            missing.append('literal_ordered_item_count')
        result['missing_by_fragment'].append({'citation_id': item.citation_id, 'missing': missing})
        if missing:
            continue
        result['witnesses'].append({'citation_id': item.citation_id, 'article_id': item.article_id,
            'chunk_id': item.chunk_id, 'raw_text_sha256': _hash(item.text),
            'concept_matches': {key: hits[0] for key, hits in matches.items()},
            'identifier_matches': {key: hits[0] for key, hits in named.items()},
            'item_count_match': chains[0] if counts else None})
    result['eligible'] = bool(result['witnesses'])
    result['reason'] = 'all_requested_field_mentions_in_one_fragment' if result['eligible'] else 'source_field_mentions_unresolved'
    return result
