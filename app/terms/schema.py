"""Immutable source/context contract, separate from scientific relations."""
from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.records.schema import source_identity, text_hash

Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
NonEmpty = Annotated[str, Field(min_length=1)]


class TermModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class SourceFragment(TermModel):
    """An exact Unicode-codepoint slice of one frozen selected page."""

    region_id: Sha256
    article_id: NonEmpty
    original_pdf_path: NonEmpty
    original_pdf_sha256: Sha256
    page_number: int = Field(ge=1)
    text_layer_id: NonEmpty
    text_layer: Literal["original", "ocr"]
    layer_pdf_path: NonEmpty
    layer_pdf_sha256: Sha256
    page_text_sha256: Sha256
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    quote: NonEmpty
    quote_sha256: Sha256
    source_type: Literal["pdf_selected_TAC_text"] = "pdf_selected_TAC_text"

    @model_validator(mode="after")
    def validate_identity(self) -> Self:
        if self.start >= self.end or self.end - self.start != len(self.quote) or self.region_id != source_identity(self.model_dump()):
            raise ValueError("Terms source fragment identity/offsets invalid")
        if self.quote_sha256 != text_hash(self.quote):
            raise ValueError("Terms source quote hash mismatch")
        if self.text_layer == "original" and (
            self.layer_pdf_sha256 != self.original_pdf_sha256 or self.layer_pdf_path != self.original_pdf_path
        ):
            raise ValueError("Terms original layer differs from original PDF")
        return self


class Context(TermModel):
    context_id: Sha256
    kind: Literal["T", "A", "C"]
    source: SourceFragment
    method: NonEmpty
    scope: Literal["frozen_TAC_page_fragment"] = "frozen_TAC_page_fragment"
    boundary_status: Literal["unreviewed", "pass", "boundary_error", "missed", "not_separately_delimited", "unresolved"]


class Mention(TermModel):
    mention_id: Sha256
    source: SourceFragment


class TermUse(TermModel):
    use_id: Sha256
    term_id: Sha256
    mention_id: Sha256
    context_id: Sha256
    state: Literal["unclassified"] = "unclassified"


class LexicalContainment(TermModel):
    outer_use_id: Sha256
    inner_use_id: Sha256
    kind: Literal["lexical_span_contains"] = "lexical_span_contains"


class Transition(TermModel):
    from_context_id: Sha256
    to_context_id: Sha256
    geometry: Literal["same_page_disjoint", "same_page_overlap", "adjacent_pages", "page_gap"]
    text_continuity: Literal["not_asserted"] = "not_asserted"


class SectionGroup(TermModel):
    kind: Literal["T", "A", "C"]
    context_ids: list[Sha256]
    transitions: list[Transition]


class LocalTerm(TermModel):
    term_id: Sha256
    term: NonEmpty
    label: NonEmpty
    use_ids: list[Sha256]


class ArticleContexts(TermModel):
    article_id: NonEmpty
    terms: list[LocalTerm]
    mentions: list[Mention]
    contexts: list[Context]
    uses: list[TermUse]
    section_groups: list[SectionGroup]
    containment: list[LexicalContainment]
    diagnostics: list[str]
