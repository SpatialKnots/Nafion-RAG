"""Separate bounded multi-record reply; exact source restoration, never scientific admission."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Literal, Self
from uuid import uuid4

from pydantic import Field, StrictInt, model_validator

from app.records.fixed_links import FixedSpanMeasurement, FixedSpanReply, build_fixed_messages, resolve_fixed_reply
from app.records.schema import CandidateBundle, ContractModel, NonEmpty, RecordCandidate
from app.records.spans import TokenSpan, resolve_token_span

VERSION = "records_multi_fixed_v0.1"
MAX_RECORDS = 4


class UnresolvedScope(ContractModel):
    reason: Literal["ambiguous_linkage", "unsupported_layout", "record_budget", "incomplete_conditions", "unmeasurable", "other"]
    evidence: tuple[TokenSpan, ...] = Field(min_length=1)
    note: NonEmpty


class MultiReply(ContractModel):
    schema_version: Literal["records_multi_fixed_reply_v0.1"]
    coverage: Literal["claimed_complete_in_context", "partial", "unsupported", "no_measurements_proposed"]
    returned_measurement_count: StrictInt = Field(ge=0, le=MAX_RECORDS)
    measurements: tuple[FixedSpanMeasurement, ...] = Field(max_length=MAX_RECORDS)
    unresolved: tuple[UnresolvedScope, ...]
    diagnostic: NonEmpty

    @model_validator(mode="after")
    def validate_coverage(self) -> Self:
        count = len(self.measurements)
        if self.returned_measurement_count != count:
            raise ValueError("Returned measurement count differs from measurements array")
        if self.coverage == "claimed_complete_in_context" and (not count or self.unresolved or count == MAX_RECORDS):
            raise ValueError("Claimed complete coverage requires 1–3 proposals and no unresolved scope")
        if self.coverage in {"unsupported", "no_measurements_proposed"} and count:
            raise ValueError("Unsupported or no-proposal coverage cannot contain measurements")
        if self.coverage in {"partial", "unsupported"} and not self.unresolved:
            raise ValueError("Partial/unsupported coverage requires source-supported unresolved scope")
        if count == MAX_RECORDS and not any(item.reason == "record_budget" for item in self.unresolved):
            raise ValueError("Reply at operational record ceiling requires a record-budget diagnostic")
        return self


def parse_multi_reply(content: str) -> MultiReply:
    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key in multi-record reply: {key}")
            result[key] = value
        return result

    return MultiReply.model_validate(json.loads(content, object_pairs_hook=unique_object))


def measurement_signature(item: FixedSpanMeasurement) -> str:
    """Exact raw-coordinate/status signature; notes and link wording cannot inflate counts."""
    fields = [{"field": obs.field, "status": obs.status,
               "raw_span": obs.raw_span.model_dump(mode="json") if obs.raw_span else None}
              for obs in sorted(item.observations, key=lambda observation: observation.field)]
    return json.dumps({"fields": fields}, sort_keys=True, separators=(",", ":"))


def resolve_multi_reply(bundle: CandidateBundle, reply: MultiReply) -> tuple[CandidateBundle, list[dict[str, Any]]]:
    records: list[RecordCandidate] = []
    signatures: set[str] = set()
    for item in reply.measurements:
        signature = measurement_signature(item)
        if signature in signatures:
            raise ValueError("Duplicate multi-record raw-coordinate proposal; notes/evidence cannot create a new measurement")
        signatures.add(signature)
        single = FixedSpanReply(schema_version="records_span_fixed_reply_v0.1", measurements=(item,), diagnostic=reply.diagnostic)
        records.extend(resolve_fixed_reply(bundle, single).records)
    # Validate source-only/one-article constraints even for an empty reply.
    if not reply.measurements:
        resolve_fixed_reply(bundle, FixedSpanReply(schema_version="records_span_fixed_reply_v0.1", measurements=(),
                                                  diagnostic=reply.diagnostic))
    unresolved = [{"reason": item.reason, "note": item.note,
                   "evidence": [resolve_token_span(bundle, span).model_dump(mode="json") for span in item.evidence]}
                  for item in reply.unresolved]
    return CandidateBundle(run_id=uuid4(), created_at=datetime.now(UTC), producer=VERSION,
                           regions=bundle.regions, records=tuple(records)), unresolved


def build_multi_messages(bundle: CandidateBundle, task: str) -> list[dict[str, str]]:
    messages = build_fixed_messages(bundle, task)
    old = "Select source token spans for zero or ONE conductivity measurement selected by the task."
    if old not in messages[0]["content"]:
        raise ValueError("Historical span prompt changed; multi-record instruction binding requires review")
    messages[0]["content"] = messages[0]["content"].replace(old,
        "Select source token spans for ALL supported conductivity observations in the supplied context, up to FOUR proposals.")
    messages[0]["content"] += (
        " Return JSON with schema_version=records_multi_fixed_reply_v0.1, coverage, returned_measurement_count, "
        "measurements, unresolved, diagnostic. Coverage is only YOUR claim about this context. "
        "Use claimed_complete_in_context only for 1–3 proposals and no unresolved scope. "
        "At four proposals use partial and a record_budget unresolved entry citing exact affected source spans; never truncate silently. "
        "Use partial/unsupported with nonempty unresolved source spans for ambiguous layout/links or incomplete scope. "
        "Use no_measurements_proposed for zero proposals, not a claim of scientific absence. "
        "Separate different samples/temperatures and keep a stated range as one range. "
        "Preserve reported electronic versus ionic property wording, reference origin and footnote overrides. "
        "An absent method/condition stays missing; never borrow it from another measurement. "
        "Do not repeat the same source-coordinate proposal with different notes. Keep notes short and factual."
    )
    user = json.loads(messages[1]["content"])
    user.update(format=VERSION, operational_record_budget=MAX_RECORDS)
    messages[1]["content"] = json.dumps(user, ensure_ascii=False)
    return messages
