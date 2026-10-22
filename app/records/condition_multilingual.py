"""Conservative RU/EN source-scope proposals; no measurement or field admission."""

from __future__ import annotations

import json
import re
from typing import Final, Literal, Self

from pydantic import model_validator

from app.records.material_roles import RoleSpan
from app.records.schema import ContractModel, NonEmpty, Sha256, SourceRegion, text_hash

VERSION: Final = 'records_condition_multilingual_v0.1'
Kind = Literal['measurement_protocol', 'measurement_setup', 'preparation_procedure', 'conditioning_procedure']
State = Literal['scope_proposal', 'ambiguous_scope', 'guarded_source', 'incomplete_source', 'unsupported_clause']


def pattern(value: str) -> re.Pattern[str]:
    return re.compile(value, re.IGNORECASE)


# These are finite literal grammars, not a general language or scientific parser.
# Whitespace and explicitly written hyphen breaks match in place; text is never repaired.
RULES: tuple[tuple[str, Kind, re.Pattern[str]], ...] = (
    ('ru_conductivity', 'measurement_protocol', pattern(r'^Электропроводность\s+(?:не\s+)?измеряли\b')),
    ('ru_cell_preparation', 'preparation_procedure', pattern(
        r'^Подготовку\s+электродов\s+и\s+сборку\s+измерительных\s+ячеек\s+(?:не\s+)?проводили\b')),
    ('ru_before_measurement', 'conditioning_procedure', pattern(
        r'^Перед\s+измерениями\s+образцы\s+(?:не\s+)?выдерживали\b')),
    ('ru_cells', 'measurement_setup', pattern(r'^Измерения\s+(?:не\s+)?прово(?:-\s*)?дили\s+в\s+симметричных\s+ячейках\b')),
    ('ru_impedance', 'measurement_protocol', pattern(r'^Для\s+измерений\s+импеданса\s+(?:не\s+)?использовали\b')),
    ('en_conductivity', 'measurement_protocol', pattern(
        r'^(?:The\s+)?(?:(?:AC|DC|ionic|lithium|proton|through-plane|in-plane)\s+)*'
        r'conductivity\s+was\s+(?:not\s+)?measured\b')),
    ('en_measurements', 'measurement_protocol', pattern(
        r'^(?:The\s+)?measurements\s+were\s+(?:not\s+)?(?:carried\s+out|performed|conducted)\b')),
    ('en_impedance', 'measurement_protocol', pattern(
        r'^(?:The\s+)?impedance\s+spectra\s+were\s+(?:not\s+)?(?:recorded|measured)\b')),
    ('en_preparation', 'preparation_procedure', pattern(
        r'^(?:The\s+)?(?:(?:membrane|electrolyte)\s+)?(?:samples?|membranes?|films?|electrodes?)\s+'
        r'(?:was|were)\s+(?:not\s+)?(?:prepared|cast|dried|annealed|synthesi[sz]ed)\b')),
    ('en_equilibration', 'conditioning_procedure', pattern(r'\bequilibrat(?:ed|ing|-\s*ing)\b')),
    ('en_before_measurement', 'conditioning_procedure', pattern(
        r'^Before\s+(?:the\s+)?measurements?,\s+(?:the\s+)?(?:samples?|membranes?)\s+'
        r'(?:was|were)\s+(?:not\s+)?(?:held|conditioned|kept)\b')),
)
GUARDS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ('negation_in_block', pattern(r"\b(?:not|never|without|neither|no|cannot|не|без|ни)\b|\b\w+n['’]t\b")),
    ('reported_work_or_citation_in_block', pattern(
        r'\b(?:previous(?:ly)?|reported|literature|according\s+to|et\s+al\.?|ранее|согласно|цитиру\w*)\b'
        r'|по\s+данным|\[\s*\d+(?:\s*[,;–—-]\s*\d+)*\s*\]')),
    ('modal_or_future_in_block', pattern(r'\b(?:would|could|should|may|might|will|может|следует|будет)\b')),
)
BOUNDARY = re.compile(r'[.!?](?=\s+[A-ZА-ЯЁ(\d]|\s*$)')
ABBREVIATION = pattern(r'\b(?:fig|figs|eq|eqs|dr|prof|mr|mrs|e\.g|i\.e|et\s+al|рис|табл)\.$')


class ScopeCue(ContractModel):
    rule_id: NonEmpty
    kind: Kind
    span: RoleSpan


class ScopeGuard(ContractModel):
    reason: Literal['negation_in_block', 'reported_work_or_citation_in_block', 'modal_or_future_in_block']
    span: RoleSpan


class MultilingualEvent(ContractModel):
    version: Literal['records_condition_multilingual_v0.1'] = VERSION
    event_id: Sha256
    context: RoleSpan
    state: State
    proposed_kind: Kind | None
    cues: tuple[ScopeCue, ...]
    block_guards: tuple[ScopeGuard, ...]
    boundary_diagnostics: tuple[str, ...]
    diagnostic: NonEmpty
    scientific_support: Literal['not_evaluated'] = 'not_evaluated'
    per_result_applicability: Literal['not_established'] = 'not_established'

    @model_validator(mode='after')
    def supported(self) -> Self:
        kinds = {cue.kind for cue in self.cues}
        expected: State = ('incomplete_source' if self.boundary_diagnostics else 'guarded_source' if self.block_guards
                           else 'ambiguous_scope' if len(kinds) > 1 else 'scope_proposal' if kinds else 'unsupported_clause')
        if self.state != expected or self.proposed_kind != (next(iter(kinds)) if expected == 'scope_proposal' else None):
            raise ValueError('Scope assertion contradicts literal cues, boundaries or block guards')
        for cue in self.cues:
            span = cue.span
            if (span.region_id != self.context.region_id or not self.context.start <= span.start < span.end <= self.context.end
                    or self.context.text[span.start - self.context.start:span.end - self.context.start] != span.text):
                raise ValueError('Scope cue differs from its exact source context')
        if self.event_id != identity(self.model_dump(exclude={'event_id'})):
            raise ValueError('Multilingual event identity changed')
        return self


def identity(data: dict[str, object]) -> str:
    return text_hash(json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(',', ':')))


def source_events(source: SourceRegion) -> tuple[MultilingualEvent, ...]:
    """Keep every source clause, all cue/guard spans and unproven block boundaries."""
    def span(start: int, end: int) -> RoleSpan:
        return RoleSpan(region_id=source.region_id, start=source.start + start, end=source.start + end,
                        text=source.quote[start:end])

    guards = tuple(ScopeGuard.model_validate({'reason': reason, 'span': span(m.start(), m.end())})
                   for reason, regex in GUARDS for m in regex.finditer(source.quote))
    ends = [m.end() for m in BOUNDARY.finditer(source.quote) if not ABBREVIATION.search(source.quote[:m.end()])]
    if not ends or ends[-1] < len(source.quote):
        ends.append(len(source.quote))
    start = 0
    events: list[MultilingualEvent] = []
    for end in ends:
        raw = source.quote[start:end]
        left, right = start + len(raw) - len(raw.lstrip()), end - len(raw) + len(raw.rstrip())
        start = end
        if left >= right:
            continue
        context = span(left, right)
        cues = tuple(ScopeCue(rule_id=name, kind=kind, span=span(left + m.start(), left + m.end()))
                     for name, kind, regex in RULES for m in regex.finditer(context.text))
        boundaries = []
        if context.text[-1] not in '.!?' or ABBREVIATION.search(context.text):
            boundaries.append('terminal_sentence_boundary_unproven')
        if not events and not context.text[0].isupper():
            boundaries.append('initial_sentence_boundary_unproven')
        kinds = {c.kind for c in cues}
        state: State = ('incomplete_source' if boundaries else 'guarded_source' if guards else 'ambiguous_scope'
                        if len(kinds) > 1 else 'scope_proposal' if kinds else 'unsupported_clause')
        data: dict[str, object] = {'version': VERSION, 'context': context.model_dump(), 'state': state,
                'proposed_kind': next(iter(kinds)) if state == 'scope_proposal' else None,
                'cues': [c.model_dump() for c in cues], 'block_guards': [g.model_dump() for g in guards],
                'boundary_diagnostics': boundaries,
                'diagnostic': 'Finite RU/EN literal policy; block-wide guards deliberately over-abstain. '
                              'Sentence punctuation does not establish paragraph adequacy or own-work origin.',
                'scientific_support': 'not_evaluated', 'per_result_applicability': 'not_established'}
        events.append(MultilingualEvent.model_validate({'event_id': identity(data), **data}))
    return tuple(events)
