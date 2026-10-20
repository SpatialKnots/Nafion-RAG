"""Named nullable linkage slots; lossless conversion to existing span candidates."""

from __future__ import annotations

import json
from typing import Any, Literal, Self

from pydantic import Field, model_validator

from app.records.schema import CandidateBundle, ContractModel, NonEmpty
from app.records.spans import (
    SpanFullReply,
    SpanLink,
    SpanMeasurement,
    SpanObservation,
    TokenSpan,
    build_span_messages,
    resolve_span_reply,
)

VERSION = "records_fixed_link_slots_v0.1"


class LinkSelection(ContractModel):
    evidence: tuple[TokenSpan, ...] = Field(min_length=1)
    note: NonEmpty


class LinkSlots(ContractModel):
    sample_value: LinkSelection | None
    property_value: LinkSelection | None
    conditions_measurement: LinkSelection | None

    def as_links(self) -> tuple[SpanLink, ...]:
        # Each role comes from one named field, never from a model-provided role string.
        return tuple(SpanLink.model_validate({"role": role, **selection})
                     for role, selection in self.model_dump(mode="json").items() if selection is not None)


class FixedSpanMeasurement(ContractModel):
    observations: tuple[SpanObservation, ...] = Field(min_length=16, max_length=16)
    representation: Literal["scalar", "range", "bound", "unparsed"]
    linkage: LinkSlots

    @model_validator(mode="after")
    def validate_observations(self) -> Self:
        # Preserve the existing observation invariant without changing its schema or resolver.
        SpanMeasurement(observations=self.observations, representation=self.representation, linkage=())
        return self


class FixedSpanReply(ContractModel):
    schema_version: Literal["records_span_fixed_reply_v0.1"]
    measurements: tuple[FixedSpanMeasurement, ...] = Field(max_length=1)
    diagnostic: NonEmpty

    def as_span_reply(self) -> SpanFullReply:
        return SpanFullReply(schema_version="records_span_reply_v0.1", diagnostic=self.diagnostic, measurements=tuple(
            SpanMeasurement(observations=item.observations, representation=item.representation, linkage=item.linkage.as_links())
            for item in self.measurements))


def parse_fixed_reply(content: str) -> FixedSpanReply:
    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key in fixed-link reply: {key}")
            result[key] = value
        return result

    return FixedSpanReply.model_validate(json.loads(content, object_pairs_hook=unique_object))


def build_fixed_messages(bundle: CandidateBundle, task: str) -> list[dict[str, str]]:
    messages = build_span_messages(bundle, task, compact=False)
    messages[0]["content"] = messages[0]["content"].replace(
        "Select broader source spans for supported links; omit unsupported links.",
        "Select broader source spans for supported links. Linkage is an object with exactly three required named slots: "
        "sample_value, property_value, conditions_measurement. Each slot is either {evidence, note} or null if unsupported. "
        "Combine multiple supporting source spans for the same role in its one evidence array. "
        "Do not output role strings, a linkage list or repeated roles. Null means no proposed link, not disproved association.",
    )
    user = json.loads(messages[1]["content"])
    user.update(format="full_fixed_links", linkage_format=VERSION)
    messages[1]["content"] = json.dumps(user, ensure_ascii=False)
    return messages


def resolve_fixed_reply(bundle: CandidateBundle, reply: FixedSpanReply) -> CandidateBundle:
    resolved = resolve_span_reply(bundle, reply.as_span_reply())
    return CandidateBundle(run_id=resolved.run_id, created_at=resolved.created_at, producer=VERSION,
                           regions=resolved.regions, records=resolved.records)
