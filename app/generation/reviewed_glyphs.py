"""Reviewed, exact-source PDF glyph aliases; never a global text correction."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from app.generation.fact_types import FactPatternError, SourceView, Value
from app.generation.providers import Evidence

POLICY = 'reviewed_pdf_glyph_aliases_v0.1'
CATALOGUE = Path(__file__).resolve().parents[1] / 'resources/reviewed_pdf_glyph_aliases_v01.json'
CATALOGUE_SHA256 = 'bf9c66bc8e65caeb34cb567a591b412e319e9075e45e883430a0cf3e1c65b8aa'


def _catalogue(binding: tuple[Path, str] | None = None) -> dict[str, Any]:
    path, digest = binding if binding is not None else (CATALOGUE, CATALOGUE_SHA256)
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise FactPatternError('reviewed_glyph_catalogue_unavailable') from exc
    if hashlib.sha256(data).hexdigest() != digest:
        raise FactPatternError('reviewed_glyph_catalogue_integrity_failed')
    catalogue: dict[str, Any] = json.loads(data)
    if catalogue['policy'] != POLICY:
        raise FactPatternError('reviewed_glyph_catalogue_policy_mismatch')
    return catalogue


def operations(source: Evidence, *, catalogue_binding: tuple[Path, str] | None = None) -> list[dict[str, Any]]:
    catalogue = _catalogue(catalogue_binding)
    digest = hashlib.sha256(source.text.encode()).hexdigest()
    matches = [entry for entry in catalogue['entries'] if entry['raw_sha256'] == digest
               and all(entry[k] == getattr(source, k) for k in
                       ('article_id', 'chunk_id', 'page_start', 'page_end', 'source_type'))]
    if not matches:
        return []
    if len(matches) != 1:
        raise FactPatternError('nonunique_reviewed_glyph_binding')
    result: list[dict[str, Any]] = matches[0]['operations']
    for operation in result:
        start, end = operation['raw_start'], operation['raw_end']
        if (end != start + 1 or source.text[start:end] != operation['raw_character']
                or not source.page_start <= operation['pdf_page'] <= source.page_end):
            raise FactPatternError('reviewed_glyph_raw_address_mismatch')
    return result


class ReviewedGlyphView(SourceView):
    def __init__(self, source: Evidence, *, catalogue_binding: tuple[Path, str] | None = None):
        super().__init__(source, join_soft_hyphen_lines=True)
        self.catalogue_binding = catalogue_binding
        self.operations = operations(source, catalogue_binding=catalogue_binding)
        by_offset = {o['raw_start']: o for o in self.operations}
        chars, addresses = [], []
        for char, address in zip(self.text, self.addresses, strict=True):
            operation = by_offset.get(address[0])
            decoded = operation['decoded'] if operation and address == (operation['raw_start'], operation['raw_end']) else char
            for character in decoded:
                chars.append(character)
                addresses.append(address)
        self.text, self.addresses = ''.join(chars), addresses

    def value(self, match: Any, group: str, *, power_of_ten: bool = False, word_number: bool = False) -> Value:
        value = super().value(match, group, power_of_ten=power_of_ten, word_number=word_number)
        if any(value.source.start < op['raw_end'] and op['raw_start'] < value.source.end for op in self.operations):
            return replace(value, normalization=POLICY + '_then_nfkc_dehyphenation_whitespace')
        return value

    def provenance(self) -> dict[str, Any] | None:
        if not self.operations:
            return None
        return {'policy': POLICY, 'catalogue_sha256': self.catalogue_binding[1] if self.catalogue_binding else CATALOGUE_SHA256,
                'original_pdf_sha256': _catalogue(self.catalogue_binding)['pdf_sha256'],
                'operations': self.operations, 'reviewer': 'agent_source_visual_review', 'scientific_validity': 'not_evaluated'}
