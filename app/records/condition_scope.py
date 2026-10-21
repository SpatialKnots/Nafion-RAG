"""Bounded literal source scopes, separate from candidate fields and scientific admission."""

from __future__ import annotations

import json
import re
from typing import Any, Final, Literal, Self
from uuid import UUID

from pydantic import model_validator

from app.records.material_roles import RoleSpan, candidate_hash, checked_span
from app.records.schema import ContractModel, NonEmpty, RecordCandidate, Sha256, SourceRegion, text_hash

VERSION: Final = "records_condition_scope_v0.1"
Scope = Literal["measurement_temperature", "measurement_protocol", "preparation_procedure", "conditioning_procedure"]
EventKind = Literal["measurement_protocol", "preparation_procedure", "conditioning_procedure", "measurement_setup", "unclassified"]
SourceField = Literal["temperature", "method", "preparation", "conditioning"]
FIELDS: tuple[SourceField, ...] = ("temperature", "method", "preparation", "conditioning")
CUES: tuple[tuple[EventKind, re.Pattern[str]], ...] = (
    ("measurement_protocol", re.compile(r"Электропроводность\s+измеряли\b")),
    ("preparation_procedure", re.compile(r"Подготовку\s+электродов\s+и\s+сборку\s+измерительных\s+ячеек\s+проводили\b")),
    ("conditioning_procedure", re.compile(r"Перед\s+измерениями\s+образцы\s+выдерживали\b")),
    ("measurement_setup", re.compile(r"Измерения\s+прово(?:-\s*)?дили\s+в\s+симметричных\s+ячейках\b")),
    ("measurement_protocol", re.compile(r"Для\s+измерений\s+импеданса\s+использовали\b")),
)
BOUNDARY = re.compile(r"[.!?](?=\s+[А-ЯЁA-Z(]|\s*$)")
METHOD = re.compile(r"(?:в\s+поперечном\s+направлении\s+мембраны\s+)?(?:методом\s+)?импедансной\s+спектроскопии")
COOLING = re.compile(r"в\s+режиме\s+охлаждения(?:\s+с\s+шагом\s+\d+(?:[.,]\d+)?°[CС])?")
ATMOSPHERE = re.compile(r"(?:в\s+сухом\s+боксе\s+)?в\s+атмосфере\s+арго(?:-\s*)?на")
TEMPERATURE = re.compile(r"σ(?P<temperature>[+−–-]?\d+(?:[.,]\d+)?°[CС]),")


class SourceEvent(ContractModel):
    event_id: Sha256
    kind: EventKind
    state: Literal["complete_clause_proposal", "unsupported_clause", "incomplete_source"]
    context: RoleSpan
    cues: tuple[RoleSpan, ...]
    diagnostic: NonEmpty
    scientific_support: Literal["not_evaluated"] = "not_evaluated"

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if self.event_id != event_identity(self.context, self.kind, self.state):
            raise ValueError("Condition source event identity differs from exact context/kind/state")
        if bool(self.cues) != (self.kind != "unclassified"):
            raise ValueError("Recognized condition events require literal cues")
        if self.state == "complete_clause_proposal" and self.kind == "unclassified":
            raise ValueError("Unclassified text cannot become a complete scope proposal")
        if self.state == "unsupported_clause" and self.kind != "unclassified":
            raise ValueError("Unsupported clause cannot assert a recognized scope")
        if (self.state == "incomplete_source") == (self.context.text[-1] in '.!?'):
            raise ValueError("Condition event boundary state contradicts its literal terminal punctuation")
        for cue in self.cues:
            if (cue.region_id != self.context.region_id or not self.context.start <= cue.start < cue.end <= self.context.end
                    or self.context.text[cue.start - self.context.start:cue.end - self.context.start] != cue.text):
                raise ValueError("Condition cue differs from its exact context occurrence")
        return self


class ScopedSelection(ContractModel):
    source_field: SourceField
    selected: RoleSpan
    status: Literal["scoped_proposal", "unassigned", "ambiguous", "incomplete_source"]
    scope: Scope | None
    event_ids: tuple[Sha256, ...]
    context: tuple[RoleSpan, ...]
    diagnostic: NonEmpty
    applicability: Literal["not_evaluated"] = "not_evaluated"

    @model_validator(mode="after")
    def no_forced_scope(self) -> Self:
        if (self.status == "scoped_proposal") != (self.scope is not None):
            raise ValueError("Only scoped proposals can assert a condition scope")
        if len(self.event_ids) != len(set(self.event_ids)):
            raise ValueError("Condition event references must be unique")
        if self.status == "ambiguous" and len(self.event_ids) < 2:
            raise ValueError("Ambiguous scope must preserve multiple intersected events")
        if self.status == "incomplete_source" and not self.event_ids:
            raise ValueError("Incomplete scope requires its source event")
        if self.scope == "measurement_temperature" and (self.event_ids or len(self.context) != 1):
            raise ValueError("Table temperature requires its column context, without method-event inheritance")
        if self.status == "scoped_proposal" and self.scope != "measurement_temperature" and len(self.event_ids) != 1:
            raise ValueError("Non-temperature scope proposal requires exactly one complete source event")
        if self.scope != "measurement_temperature" and len(self.context) != len(self.event_ids):
            raise ValueError("Every referenced condition event requires its preserved context")
        if self.status == "scoped_proposal" and not any(c.region_id == self.selected.region_id
                and c.start <= self.selected.start < self.selected.end <= c.end for c in self.context):
            raise ValueError("A scoped selection must stay within its preserved source context")
        return self


class ConditionProjection(ContractModel):
    schema_version: Literal["records_condition_scope_v0.1"] = VERSION
    record_id: UUID
    cell_id: Sha256
    original_candidate_sha256: Sha256
    selections: tuple[ScopedSelection, ...]
    missing_source_fields: dict[str, str]
    measurement_environment: Literal["unknown"] = "unknown"
    equilibration_completion: Literal["unknown"] = "unknown"
    scientific_admission: Literal["not_evaluated"] = "not_evaluated"

    @model_validator(mode="after")
    def accounted(self) -> Self:
        fields = [s.source_field for s in self.selections]
        if len(fields) != len(set(fields)) or set(fields) & set(self.missing_source_fields):
            raise ValueError("A condition source field must occur exactly once")
        if set(fields) | set(self.missing_source_fields) != set(FIELDS):
            raise ValueError("Every condition field must be selected or explicitly missing")
        if any(v not in {"not_found_in_context", "ambiguous", "unsupported"} for v in self.missing_source_fields.values()):
            raise ValueError("Missing conditions require unchanged non-present source status")
        return self


def event_identity(context: RoleSpan, kind: str, state: str) -> str:
    return text_hash(json.dumps([context.model_dump(), kind, state], ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def source_events(source: SourceRegion) -> tuple[SourceEvent, ...]:
    """Literal sentence boundaries; preserve unsupported and clipped source, never repair text."""
    ends = [m.end() for m in BOUNDARY.finditer(source.quote)]
    if not ends or ends[-1] < len(source.quote):
        ends.append(len(source.quote))
    start, events = 0, []
    for end in ends:
        text = source.quote[start:end]
        left, right = start + len(text) - len(text.lstrip()), end - len(text) + len(text.rstrip())
        start = end
        if left >= right:
            continue
        context = RoleSpan(region_id=source.region_id, start=source.start + left, end=source.start + right,
                           text=source.quote[left:right])
        kind: EventKind = "unclassified"
        cues = []
        for candidate_kind, pattern in CUES:
            match = pattern.match(context.text)
            if match and not re.search(r"\bне\s", context.text):
                kind = candidate_kind
                cues.append(RoleSpan(region_id=source.region_id, start=context.start, end=context.start + match.end(), text=match[0]))
                break
        complete = context.text[-1] in '.!?'
        state = "complete_clause_proposal" if complete and cues else "unsupported_clause" if complete else "incomplete_source"
        events.append(SourceEvent.model_validate({"event_id": event_identity(context, kind, state), "kind": kind,
            "state": state, "context": context, "cues": cues,
            "diagnostic": "Literal anchored source cue only; applicability unknown." if complete
            else "Source ends before sentence completion; do not infer equilibrium, waiting duration or environment."}))
    return tuple(events)


def project_conditions(row: dict[str, Any], sources: dict[str, SourceRegion], slot: dict[str, Any],
                       table_id: str, events: tuple[SourceEvent, ...]) -> ConditionProjection:
    record = RecordCandidate.model_validate(row['candidate'])
    if str(record.record_id) != row['record_id'] or row['cell_id'] != slot['cell_id']:
        raise ValueError("Condition candidate/cell identity differs from parent")
    available = set(row['region_ids'])
    for evidence in record.evidence_spans():
        source = sources.get(evidence.region_id)
        if (source is None or source.article_id != record.article_id or evidence.region_id not in available
                or source.quote[evidence.start:evidence.end] != evidence.quote):
            raise ValueError("Condition evidence differs from available exact same-article source")
    for event in events:
        checked_span(event.context.model_dump(), sources, record.article_id)
        if event.context.region_id == table_id or sources[event.context.region_id].page_number == sources[table_id].page_number:
            raise ValueError("Condition method events require a separate non-table source page")
    header = checked_span({**slot['header'], 'region_id': table_id}, sources, record.article_id)
    match = TEMPERATURE.fullmatch(header.text)
    expected_temperature = None if not match else RoleSpan(region_id=table_id, start=header.start + match.start('temperature'),
        end=header.start + match.end('temperature'), text=match['temperature'])
    missing: dict[str, str] = {}
    selections = []
    for field in FIELDS:
        original, previous = getattr(record, field), row['selected_fields'][field]
        if previous['status'] != original.status:
            raise ValueError("Condition field status differs from unchanged candidate")
        if original.status != 'present':
            if previous['raw'] is not None:
                raise ValueError("Missing condition cannot contain a raw selection")
            missing[field] = original.status
            continue
        if previous['raw'] is None:
            raise ValueError("Present condition lost its original selection")
        selected = checked_span(previous['raw'], sources, record.article_id)
        source = sources[selected.region_id]
        if (selected.region_id not in available or selected.text != original.raw_text or not any(
                e.region_id == selected.region_id and source.start + e.start <= selected.start < selected.end <= source.start + e.end
                for e in original.evidence)):
            raise ValueError("Condition selection differs from its original cited occurrence")
        scope: Scope | None = None
        status = 'unassigned'
        intersected = [e for e in events if e.context.region_id == selected.region_id
                       and e.context.start < selected.end and e.context.end > selected.start]
        context = [e.context for e in intersected]
        if expected_temperature and selected == expected_temperature:
            status, scope, context = 'scoped_proposal', 'measurement_temperature', [header]
        elif len(intersected) > 1:
            status = 'ambiguous'
        elif len(intersected) == 1:
            event = intersected[0]
            contained = event.context.start <= selected.start < selected.end <= event.context.end
            if event.state == 'incomplete_source':
                status = 'incomplete_source'
            elif contained and event.state == 'complete_clause_proposal':
                entire = selected == event.context
                if event.kind == 'measurement_protocol' and (entire or METHOD.fullmatch(selected.text) or COOLING.fullmatch(selected.text)):
                    status, scope = 'scoped_proposal', 'measurement_protocol'
                elif event.kind == 'preparation_procedure' and (entire or ATMOSPHERE.fullmatch(selected.text)):
                    status, scope = 'scoped_proposal', 'preparation_procedure'
                elif event.kind == 'conditioning_procedure' and entire:
                    status, scope = 'scoped_proposal', 'conditioning_procedure'
        diagnostic = {'scoped_proposal': 'Literal source scope proposal; field name does not establish scope. Applicability unknown.',
                      'ambiguous': 'Selection crosses source clauses; no single scope assigned.',
                      'incomplete_source': 'Selection intersects the clipped source tail; no completed condition inferred.',
                      'unassigned': 'No qualifying occurrence/cue. Material adjectives and method ranges do not fill conditions.'}[status]
        selections.append(ScopedSelection.model_validate({'source_field': field, 'selected': selected, 'status': status, 'scope': scope,
            'event_ids': [e.event_id for e in intersected], 'context': context, 'diagnostic': diagnostic}))
    return ConditionProjection(record_id=record.record_id, cell_id=row['cell_id'],
                               original_candidate_sha256=candidate_hash(row['candidate']),
                               selections=tuple(selections), missing_source_fields=missing)
