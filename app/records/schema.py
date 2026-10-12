"""Versioned evidence integrity contract, not a scientific admission policy."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
NonEmpty = Annotated[str, Field(min_length=1)]


def text_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def source_identity(data: Mapping[str, object]) -> str:
    keys = (
        "article_id", "original_pdf_sha256", "page_number", "text_layer_id",
        "text_layer", "layer_pdf_sha256", "page_text_sha256", "start", "end",
    )
    # Selection labels and machine-local paths do not change source identity.
    return text_hash(json.dumps([str(data[key]) for key in keys], ensure_ascii=False, separators=(",", ":")))


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SourceRegion(ContractModel):
    """Offsets are zero-based Unicode codepoints, end exclusive, in stored page text."""

    region_id: Sha256
    article_id: UUID
    original_pdf_path: NonEmpty
    original_pdf_sha256: Sha256
    page_number: int = Field(ge=1)
    text_layer_id: UUID
    text_layer: Literal["original", "ocr"]
    layer_pdf_path: NonEmpty
    layer_pdf_sha256: Sha256
    page_text: NonEmpty
    page_text_sha256: Sha256
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    quote: NonEmpty
    quote_sha256: Sha256
    selection_basis: Literal["manual_development", "expert_oracle", "fixed_page", "retrieval"]
    selection_note: NonEmpty

    @model_validator(mode="after")
    def validate_content(self) -> Self:
        if not self.start < self.end <= len(self.page_text):
            raise ValueError("Region span is outside page text")
        if self.page_text[self.start : self.end] != self.quote:
            raise ValueError("Region quote does not match exact page span")
        if text_hash(self.page_text) != self.page_text_sha256 or text_hash(self.quote) != self.quote_sha256:
            raise ValueError("Text checksum mismatch")
        if self.text_layer == "original" and (
            self.layer_pdf_path != self.original_pdf_path or self.layer_pdf_sha256 != self.original_pdf_sha256
        ):
            raise ValueError("Original text layer must identify the original PDF")
        if self.region_id != source_identity(self.model_dump()):
            raise ValueError("Region identity checksum mismatch")
        return self


class EvidenceSpan(ContractModel):
    """Offsets are relative to SourceRegion.quote, not to the entire page."""

    region_id: Sha256
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    quote: NonEmpty

    @model_validator(mode="after")
    def validate_order(self) -> Self:
        if self.end <= self.start:
            raise ValueError("Evidence end must be greater than start")
        return self


class TextObservation(ContractModel):
    status: Literal["present", "not_found_in_context", "ambiguous", "unsupported"]
    raw_text: NonEmpty | None = None
    evidence: tuple[EvidenceSpan, ...] = ()
    note: NonEmpty | None = None

    @model_validator(mode="after")
    def validate_missingness(self) -> Self:
        if self.status == "present":
            if self.raw_text is None or not self.raw_text.strip() or not self.evidence:
                raise ValueError("Present observation requires raw text and evidence")
            if not any(self.raw_text in span.quote for span in self.evidence):
                raise ValueError("Raw text must occur verbatim in cited evidence")
        else:
            if self.raw_text is not None:
                raise ValueError("Non-present observation cannot carry an asserted raw value")
            if self.note is None or not self.note.strip():
                raise ValueError("Missing or ambiguous observation requires a diagnostic note")
        return self


class QuantityProposal(ContractModel):
    raw_value: TextObservation
    raw_unit: TextObservation
    representation: Literal["scalar", "range", "bound", "unparsed"] = "unparsed"
    approximation: TextObservation
    uncertainty: TextObservation
    # No parsed number, inferred temperature, conversion, or range thresholds in v0.1.


class LinkageProposal(ContractModel):
    role: Literal["sample_value", "property_value", "conditions_measurement"]
    evidence: tuple[EvidenceSpan, ...] = Field(min_length=1)
    note: NonEmpty


class RecordCandidate(ContractModel):
    record_id: UUID
    article_id: UUID
    work_group_id: NonEmpty | None = None
    sample_label: TextObservation
    material_form: TextObservation
    preparation: TextObservation
    property_name: TextObservation
    value: QuantityProposal
    temperature: TextObservation
    medium: TextObservation
    medium_composition: TextObservation
    composition_basis: TextObservation
    conditioning: TextObservation
    method: TextObservation
    data_origin: TextObservation
    li_ion_author_claim: TextObservation
    li_ion_confirmation: Literal["not_reviewed"] = "not_reviewed"
    linkage: tuple[LinkageProposal, ...] = ()
    review_state: Literal["needs_review"] = "needs_review"

    def evidence_spans(self) -> tuple[EvidenceSpan, ...]:
        observations = (
            self.sample_label, self.material_form, self.preparation, self.property_name,
            self.value.raw_value, self.value.raw_unit, self.value.approximation, self.value.uncertainty,
            self.temperature, self.medium, self.medium_composition, self.composition_basis, self.conditioning,
            self.method, self.data_origin, self.li_ion_author_claim,
        )
        return tuple(span for obs in observations for span in obs.evidence) + tuple(
            span for link in self.linkage for span in link.evidence
        )


class CandidateBundle(ContractModel):
    schema_version: Literal["li_nafion_candidate_v0.1"] = "li_nafion_candidate_v0.1"
    run_id: UUID
    created_at: datetime
    producer: NonEmpty
    regions: tuple[SourceRegion, ...] = Field(min_length=1)
    records: tuple[RecordCandidate, ...] = ()

    @model_validator(mode="after")
    def validate_references(self) -> Self:
        if self.created_at.utcoffset() is None:
            raise ValueError("created_at must include timezone")
        regions = {region.region_id: region for region in self.regions}
        if len(regions) != len(self.regions):
            raise ValueError("Duplicate source region")
        if len({record.record_id for record in self.records}) != len(self.records):
            raise ValueError("Duplicate record ID")
        for record in self.records:
            if record.article_id not in {region.article_id for region in self.regions}:
                raise ValueError("Record article has no source region")
            for span in record.evidence_spans():
                region = regions.get(span.region_id)
                if region is None:
                    raise ValueError("Evidence references unknown region")
                if region.article_id != record.article_id:
                    raise ValueError("Evidence belongs to a different article")
                if span.end > len(region.quote) or region.quote[span.start : span.end] != span.quote:
                    raise ValueError("Evidence quote does not match exact region span")
        return self
