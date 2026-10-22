"""Versioned necessary mention constraints; not scientific answer sufficiency.

Opt-in guard, independent of the historical production adequacy policy. It never
upgrades a rejection. Finite grammar/catalogue; unknown query syntax is not NER.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import Any

from app.generation.providers import AnswerLanguage, AnswerProvider, AnswerStyle, Evidence, ProviderResult

VERSION = 'query_qualifiers_v0.1'
# Aliases express mention equivalence only, not interchangeability of experiments.
METHOD_ALIASES = {
    'differential_scanning_calorimetry': ('DSC', 'differential scanning calorimetry',
                                       'ДСК', 'дифференциальная сканирующая калориметрия'),
    'thermogravimetric_analysis': ('TGA', 'thermogravimetric analysis', 'ТГА', 'термогравиметрический анализ'),
    'electrochemical_impedance_spectroscopy': ('EIS', 'electrochemical impedance spectroscopy',
                                            'электрохимическая импедансная спектроскопия'),
    'conductivity': ('conductivity', 'conductivities', 'проводимость', 'проводимости', 'проводимостью'),
}
MATERIAL_MARKER = re.compile(r'\b(?:containing|doped\s+with|содержащ\w*|с\s+добавкой)\b\s*', re.IGNORECASE)
AUTHOR_YEAR = re.compile(
    r'\b(?:for|by|in\s+the\s+work\s+of|в\s+работе)\s+'
    r"(?P<author>[^\W\d_]+(?:[-'’][^\W\d_]+)*)(?:\s+et\s+al\.?)?\s+(?P<year>(?:19|20)\d{2})(?!\w)", re.IGNORECASE)


def _tokens(text: str) -> list[tuple[str, int, int]]:
    return [(unicodedata.normalize('NFKC', m.group()).casefold(), m.start(), m.end())
            for m in re.finditer(r'[^\W_]+', text)]


def occurrences(text: str, phrase: str) -> list[dict[str, Any]]:
    """Token boundaries, NFKC/case folding, whitespace/hyphen separators; exact raw offsets."""
    phrase_tokens = _tokens(phrase)
    wanted = [t for t, _, _ in phrase_tokens]
    if not wanted:
        return []
    tokens = _tokens(text)
    result = []
    for i in range(len(tokens) - len(wanted) + 1):
        window = tokens[i:i + len(wanted)]
        if [t for t, _, _ in window] != wanted:
            continue
        def separators(raw: str, spans: list[tuple[str, int, int]]) -> list[str]:
            return [re.sub(r'[\s\-‐‑–—]+', ' ', raw[left[2]:right[1]]).strip()
                    for left, right in zip(spans, spans[1:], strict=False)]
        if separators(text, window) != separators(phrase, phrase_tokens):
            continue
        start, end = window[0][1], window[-1][2]
        result.append({'start': start, 'end': end, 'text': text[start:end]})
    return result


@dataclass(frozen=True)
class Qualifier:
    kind: str
    key: str
    start: int
    end: int
    text: str
    aliases: tuple[str, ...]
    year: int | None = None


def extract_qualifiers(question: str) -> tuple[list[Qualifier], list[str]]:
    qualifiers, warnings = [], []
    for match in AUTHOR_YEAR.finditer(question):
        qualifiers.append(Qualifier('article', match['author'], match.start(), match.end(), match.group(),
                                    (match['author'],), int(match['year'])))
    for marker in MATERIAL_MARKER.finditer(question):
        tail = re.match(r'[^\n,;?.!:]*', question[marker.end():])
        assert tail is not None
        start, end = marker.end(), marker.end() + tail.end()
        while start < end and (question[start].isspace() or question[start] in '\"«“'):
            start += 1
        while end > start and (question[end - 1].isspace() or question[end - 1] in '\"»”'):
            end -= 1
        text = question[start:end]
        if not _tokens(text):
            warnings.append('material_marker_without_literal_phrase')
        else:
            qualifiers.append(Qualifier('material_literal', text, start, end, text, (text,)))
    for name, aliases in METHOD_ALIASES.items():
        hits = [span for alias in aliases for span in occurrences(question, alias)]
        if hits:
            first = min(hits, key=lambda h: (h['start'], -(h['end'] - h['start'])))
            qualifiers.append(Qualifier('method_or_property_mention', name, first['start'], first['end'], first['text'], aliases))
    return sorted(qualifiers, key=lambda q: (q.start, q.end, q.kind)), warnings


def assess_query_qualifiers(question: str, evidence: Sequence[Evidence], *, baseline_allowed: bool,
                            article_metadata: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    """Necessary constraints must occur within one selected article; no cross-article pooling.

    Bibliographic identity uses bound metadata only, never references/body/title
    guesses. Missing metadata is unknown. Presence (including negated presence)
    is only a mention and cannot establish a measurement or relation.
    """
    if not question.strip():
        raise ValueError('Qualifier assessment requires a nonempty question')
    if len({e.citation_id for e in evidence}) != len(evidence) or any(not e.citation_id.strip() for e in evidence):
        raise ValueError('Qualifier evidence citation IDs must be unique and nonempty')
    if any(not e.article_id.strip() for e in evidence):
        raise ValueError('Qualifier evidence article IDs must be nonempty')
    qualifiers, warnings = extract_qualifiers(question)
    groups = {e.article_id: [item for item in evidence if item.article_id == e.article_id] for e in evidence}
    rows = []
    for article_id, items in sorted(groups.items()):
        checks = []
        for qualifier in qualifiers:
            hits: list[dict[str, Any]] = []
            state = 'not_found'
            if qualifier.kind == 'article':
                meta = (article_metadata or {}).get(article_id)
                if meta is None or meta.get('authors') in (None, []) or meta.get('year') is None:
                    state = 'unknown_metadata'
                else:
                    authors = meta['authors']
                    if not isinstance(authors, list) or any(not isinstance(a, str) for a in authors):
                        raise ValueError('Qualifier article metadata authors must be a list of source strings')
                    if not isinstance(meta['year'], int) or isinstance(meta['year'], bool):
                        raise ValueError('Qualifier article metadata year must be an integer or null')
                    for index, author in enumerate(authors):
                        if meta['year'] == qualifier.year:
                            hits.extend({'metadata_field': 'authors', 'author_index': index, 'year': meta['year'], **span}
                                        for span in occurrences(author, qualifier.aliases[0]))
                    if hits:
                        state = 'mentioned'
            else:
                for item in items:
                    for alias in qualifier.aliases:
                        hits.extend({'citation_id': item.citation_id, 'chunk_id': item.chunk_id,
                                     'page_start': item.page_start, 'page_end': item.page_end,
                                     'alias': alias, **span} for span in occurrences(item.text, alias))
                if hits:
                    state = 'mentioned'
            checks.append({'qualifier': asdict(qualifier), 'state': state, 'occurrences': hits})
        rows.append({'article_id': article_id, 'checks': checks,
                     'all_required_mentions': bool(checks) and all(c['state'] == 'mentioned' for c in checks)})
    matching = [row['article_id'] for row in rows if row['all_required_mentions']]
    blocks = not evidence or bool(warnings) or bool(qualifiers) and not matching
    if not baseline_allowed:
        reason = 'baseline_rejection_preserved'
    elif not evidence:
        reason = 'no_evidence'
    elif warnings:
        reason = 'unresolved_explicit_qualifier'
    elif not qualifiers:
        reason = 'outside_finite_qualifier_scope'
    elif not matching:
        reason = 'no_single_article_covers_required_mentions'
    else:
        reason = 'necessary_mentions_only'
    return {'version': VERSION, 'question': question, 'baseline_allowed': baseline_allowed,
            'candidate_allowed': baseline_allowed and not blocks, 'reason': reason,
            'qualifiers': [asdict(q) for q in qualifiers], 'parse_warnings': warnings,
            'articles': rows, 'matching_article_ids': matching,
            'scientific_admission': 'not_evaluated',
            'limitations': ['finite_grammar_and_alias_catalogue', 'unparsed_constraints_not_validated',
                            'material_phrase_requires_literal_token_sequence', 'metadata_not_independently_validated',
                            'mentions_do_not_prove_measurements_or_relations', 'no_corpus_absence_claim']}


class QualifierGuardProvider:
    """Explicitly injectable provider guard, called only after the existing adequacy gate.

    Not installed as a production default. Diagnostic assessment remains on this
    instance; a blocked call returns the existing provider-abstention contract.
    """
    def __init__(self, provider: AnswerProvider, *, article_metadata: dict[str, dict[str, Any]] | None = None) -> None:
        self.provider = provider
        self.article_metadata = article_metadata
        self.assessment: dict[str, Any] | None = None

    def generate(self, question: str, evidence: list[Evidence], *, answer_style: AnswerStyle = 'claims',
                 answer_language: AnswerLanguage = 'auto') -> ProviderResult:
        self.assessment = assess_query_qualifiers(question, evidence, baseline_allowed=True, article_metadata=self.article_metadata)
        if not self.assessment['candidate_allowed']:
            return ProviderResult(False, [], VERSION, None)
        return self.provider.generate(question, evidence, answer_style=answer_style, answer_language=answer_language)
