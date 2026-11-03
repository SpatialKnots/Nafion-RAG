"""Request-local source context for presentation; never a new evidence selector."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.generation.providers import Evidence

if TYPE_CHECKING:
    from app.retrieval.search import SearchResponse

VERSION = "answer_presentation_v0.1"
PRESENTATION_INSTRUCTION = (
    "Present a substantive, source-checkable answer. Start with the direct conclusion and its scope. "
    "Then explain the relevant quantity definition, material/form, solvent or mixture composition, temperature, "
    "units, method and experimental conditions only where the cited evidence supplies them. "
    "Keep each value and its conditions with the same work, sample and operation. "
    "Distinguish experimentally observed values, regression/model-derived parameters and system arithmetic. "
    "After the supported result, state relevant limitations or missing conditions without inventing them. "
    "For a maximum, state the actual comparison set; a selected solvent set is not the complete literature. "
    "Use readable explanatory prose in claim text, with detail proportional to the evidence; no padding or fixed word count. "
    "If quoting, copy an exact short fragment of the supplied evidence and do not paraphrase inside quotation marks. "
    "The application renders source titles, pages and links from citation_ids: do not invent URLs, authors or references. "
    "These presentation instructions do not make insufficient evidence answerable or relax the empty-claims abstention rule."
)


@dataclass(frozen=True)
class PresentationSource:
    citation_id: str
    article_id: str
    chunk_id: str
    page_start: int
    page_end: int
    generation_text: str
    source_text: str | None
    text_layer: str | None
    source_type: str
    generation_is_derived: bool

    def matches(self, citation: dict[str, object]) -> bool:
        return all(citation.get(key) == getattr(self, key) for key in
                   ("citation_id", "article_id", "chunk_id", "page_start", "page_end"))


def capture_sources(retrieval: SearchResponse, evidence: list[Evidence]) -> dict[str, PresentationSource]:
    """Bind exact strings from this request's trace, without I/O or text transformations."""
    if len({e.citation_id for e in evidence}) != len(evidence):
        raise ValueError("Presentation evidence citation IDs must be unique")
    raw = {r.chunk_id: r for r in retrieval.results}
    output = {}
    for item in evidence:
        result = raw.get(item.chunk_id)
        bound = (result is not None and result.article_id == item.article_id
                 and result.page_start == item.page_start and result.page_end == item.page_end)
        output[item.citation_id] = PresentationSource(
            item.citation_id, item.article_id, item.chunk_id, item.page_start, item.page_end, item.text,
            result.full_text if bound and result is not None else None,
            result.text_layer if bound and result is not None else None, item.source_type,
            item.source_type in {"table_derived", "procedure_derived", "comparison_derived"},
        )
    return output
