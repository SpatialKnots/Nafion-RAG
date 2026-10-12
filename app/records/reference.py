"""Source-bound development expectations, never independent gold or scientific admission."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import Field, model_validator

from app.records.schema import CandidateBundle, ContractModel, EvidenceSpan, NonEmpty, Sha256
from app.records.smoke import REQUIRED_FIELDS, SmokeField


class ExpectedAnswer(ContractModel):
    raw_text: NonEmpty
    anchors: tuple[EvidenceSpan, ...] = Field(min_length=1)


class FieldExpectation(ContractModel):
    field: SmokeField
    criterion: Literal["exact_raw", "abstain", "deferred"]
    answers: tuple[ExpectedAnswer, ...] = ()
    support: tuple[EvidenceSpan, ...] = Field(min_length=1)
    rationale: NonEmpty

    @model_validator(mode="after")
    def validate_criterion(self) -> Self:
        if (self.criterion == "exact_raw") != bool(self.answers):
            raise ValueError("Only exact_raw expectations require permitted source-bound answers")
        if len({answer.raw_text for answer in self.answers}) != len(self.answers):
            raise ValueError("Duplicate permitted answer")
        return self


class LinkageReview(ContractModel):
    dimension: Literal["sample_linkage", "condition_linkage", "origin_linkage"]
    status: Literal["needs_independent_review", "not_applicable"]
    support: tuple[EvidenceSpan, ...] = Field(min_length=1)
    rationale: NonEmpty


class ReferenceCase(ContractModel):
    case_id: NonEmpty
    input_sha256: Sha256
    task_sha256: Sha256
    context: CandidateBundle
    fields: tuple[FieldExpectation, ...] = Field(min_length=10, max_length=10)
    linkage: tuple[LinkageReview, ...] = Field(min_length=3, max_length=3)

    @model_validator(mode="after")
    def validate_source_expectations(self) -> Self:
        names = [item.field for item in self.fields]
        if len(set(names)) != len(names) or set(names) != REQUIRED_FIELDS:
            raise ValueError("Reference case must declare all ten fields exactly once")
        dimensions = {item.dimension for item in self.linkage}
        if dimensions != {"sample_linkage", "condition_linkage", "origin_linkage"}:
            raise ValueError("Reference case must declare all three linkage dimensions")
        regions = {region.region_id: region for region in self.context.regions}
        spans = [span for item in self.fields for span in item.support]
        spans += [span for item in self.linkage for span in item.support]
        spans += [span for item in self.fields for answer in item.answers for span in answer.anchors]
        for span in spans:
            region = regions.get(span.region_id)
            if region is None or region.quote[span.start:span.end] != span.quote or span.end > len(region.quote):
                raise ValueError("Reference evidence must match an exact span in its source context")
        for item in self.fields:
            for answer in item.answers:
                if not answer.raw_text.strip() or not all(span.quote == answer.raw_text for span in answer.anchors):
                    raise ValueError("Answer anchors must identify exact occurrences of the permitted raw text")
        return self


class DevelopmentReference(ContractModel):
    schema_version: Literal["records_development_reference_v0.1"] = "records_development_reference_v0.1"
    reference_id: UUID
    created_at: datetime
    author: NonEmpty
    status: Literal["needs_independent_review"] = "needs_independent_review"
    cases: tuple[ReferenceCase, ...] = Field(min_length=1)
    limitations: tuple[NonEmpty, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_reference_identity(self) -> Self:
        if self.created_at.utcoffset() is None:
            raise ValueError("Reference timestamp must include timezone")
        if len({case.case_id for case in self.cases}) != len(self.cases):
            raise ValueError("Duplicate reference case")
        return self
