"""Evaluate the existing adequacy gate against source-verified relation labels.

Labels are reviewed annotations, not inferred from keywords or model predictions.
This module does not change retrieval, generation, or the production gate.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from typing import Annotated, Any, Literal

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Article, Chunk, PageTextLayer
from app.documents.service import build_pdf_url
from app.generation.evidence_adequacy import assess_evidence_adequacy
from app.retrieval.cross_lingual import build_query_bundle, glossary_terms_for_concepts

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
SHA256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class RelationSource(StrictModel):
    article_checksum: SHA256
    title: Text
    doi: str | None
    pdf_reviewed_pages: list[Annotated[int, Field(ge=1)]] = Field(min_length=1)


class RelationFragment(StrictModel):
    source: Text
    page: int = Field(ge=1)
    text_layer: Literal["original", "ocr"]
    start: int = Field(ge=0)
    text: str = Field(min_length=1)
    text_sha256: SHA256
    section: Text


class RelationCase(StrictModel):
    id: Text
    queries: dict[Literal["en", "ru"], Text] = Field(min_length=1)
    relation: Text
    material: Text
    independent_variable: Text
    dependent_variable: Text
    conditions: Text
    expected_support: Literal["supports", "insufficient"]
    rationale: Text
    fragments: list[Text] = Field(min_length=1)


class RelationDataset(StrictModel):
    version: Literal[1]
    review_status: Literal["assistant_pdf_reviewed"]
    independent_review: Literal[False]
    review_date: Text
    scope: Text
    sources: dict[str, RelationSource] = Field(min_length=1)
    fragments: dict[str, RelationFragment] = Field(min_length=1)
    cases: list[RelationCase] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_references(self) -> RelationDataset:
        if len({case.id for case in self.cases}) != len(self.cases):
            raise ValueError("duplicate relation case IDs")
        for fragment_id, fragment in self.fragments.items():
            if fragment.source not in self.sources:
                raise ValueError(f"{fragment_id}: unknown source {fragment.source}")
            if fragment.page not in self.sources[fragment.source].pdf_reviewed_pages:
                raise ValueError(f"{fragment_id}: page not listed in PDF review")
        for case in self.cases:
            if len(set(case.fragments)) != len(case.fragments):
                raise ValueError(f"{case.id}: duplicate fragment references")
            if any(fragment not in self.fragments for fragment in case.fragments):
                raise ValueError(f"{case.id}: unknown fragment reference")
        return self


class UniqueKeyLoader(yaml.SafeLoader):  # type: ignore[misc]
    pass


def _unique_mapping(loader: UniqueKeyLoader, node: Any, deep: bool = False) -> dict[Any, Any]:
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise ValueError(f"duplicate YAML key: {key}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _unique_mapping)


def load_relation_dataset(path: Path) -> RelationDataset:
    return RelationDataset.model_validate(yaml.load(path.read_text(encoding="utf-8"), Loader=UniqueKeyLoader))


def fragment_text_error(fragment: RelationFragment, page_text: str) -> str | None:
    if hashlib.sha256(fragment.text.encode("utf-8")).hexdigest() != fragment.text_sha256:
        return "annotation_text_hash_mismatch"
    if page_text[fragment.start : fragment.start + len(fragment.text)] != fragment.text:
        return "source_fragment_changed"
    return None


def verify_relation_sources(session: Session, dataset: RelationDataset) -> tuple[dict[str, dict[str, Any]], list[dict[str, str]]]:
    verified: dict[str, dict[str, Any]] = {}
    errors: list[dict[str, str]] = []
    sources: dict[str, Article] = {}
    for source_id, source in dataset.sources.items():
        article = session.scalar(select(Article).where(Article.checksum_sha256 == source.article_checksum))
        error = None
        if article is None:
            error = "article_not_found"
        elif article.doi != source.doi:
            error = "article_doi_changed"
        elif not Path(article.pdf_original_path).is_file():
            error = "original_pdf_missing"
        elif hashlib.sha256(Path(article.pdf_original_path).read_bytes()).hexdigest() != source.article_checksum:
            error = "original_pdf_hash_mismatch"
        if error:
            errors.append({"source": source_id, "reason": error})
        elif article is not None:
            sources[source_id] = article
    for fragment_id, fragment in dataset.fragments.items():
        article = sources.get(fragment.source)
        if article is None:
            continue
        layer = session.scalar(select(PageTextLayer).where(
            PageTextLayer.article_id == article.id,
            PageTextLayer.page_number == fragment.page,
            PageTextLayer.layer_type == fragment.text_layer,
        ))
        error = "page_layer_missing" if layer is None else fragment_text_error(fragment, layer.text)
        if error:
            errors.append({"fragment": fragment_id, "reason": error})
            continue
        chunks = session.scalars(select(Chunk).where(
            Chunk.article_id == article.id, Chunk.page_start <= fragment.page, Chunk.page_end >= fragment.page,
            Chunk.text_layer == fragment.text_layer,
        ).order_by(Chunk.chunk_index, Chunk.id))
        verified[fragment_id] = {
            **fragment.model_dump(), "article_id": str(article.id), "title": article.title, "doi": article.doi,
            "article_checksum": article.checksum_sha256,
            "pdf_path": str(Path(article.pdf_original_path).resolve()),
            "pdf_page_url": build_pdf_url(article.id, "original", fragment.page),
            "scope": "exact_page_fragment",
            "containing_chunks": [
                {"chunk_id": str(chunk.id), "source_type": chunk.source_type, "text_layer": chunk.text_layer,
                 "page_start": chunk.page_start, "page_end": chunk.page_end}
                for chunk in chunks if fragment.text in chunk.text
            ],
        }
    return verified, errors


def summarize_relation_predictions(rows: list[dict[str, Any]]) -> dict[str, Any]:
    valid = [row for row in rows if row["status"] == "evaluated"]
    tp = sum(row["expected_adequate"] and row["predicted_adequate"] for row in valid)
    tn = sum(not row["expected_adequate"] and not row["predicted_adequate"] for row in valid)
    fp = sum(not row["expected_adequate"] and row["predicted_adequate"] for row in valid)
    fn = sum(row["expected_adequate"] and not row["predicted_adequate"] for row in valid)
    return {
        "total": len(rows), "evaluated": len(valid), "invalid": len(rows) - len(valid),
        "true_accepts": tp, "true_refusals": tn, "false_accepts": fp, "false_refusals": fn,
        "passed": tp + tn, "failed": fp + fn,
        "accuracy": (tp + tn) / len(valid) if valid else None,
        "adequacy_precision": tp / (tp + fp) if tp + fp else None,
        "adequacy_recall": tp / (tp + fn) if tp + fn else None,
    }


def evaluate_relation_cases(dataset: RelationDataset, verified: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for case in dataset.cases:
        for language, query in case.queries.items():
            for mode in ("lexical", "cross_lingual_concepts"):
                row: dict[str, Any] = {
                    "case_id": case.id, "language": language, "query": query, "mode": mode,
                    "relation": case.relation, "expected_adequate": case.expected_support == "supports",
                    "fragments": case.fragments, "rationale": case.rationale,
                }
                missing = [fragment for fragment in case.fragments if fragment not in verified]
                if missing:
                    rows.append({**row, "status": "invalid_source", "unverified_fragments": missing})
                    continue
                concept_terms = glossary_terms_for_concepts(build_query_bundle(query).matched_concepts) if mode != "lexical" else None
                adequacy = assess_evidence_adequacy(
                    query, [SimpleNamespace(text=verified[fragment]["text"]) for fragment in case.fragments],
                    concept_terms=concept_terms,
                )
                rows.append({**row, "status": "evaluated", "predicted_adequate": adequacy.adequate, "diagnostics": asdict(adequacy)})
    return rows


def run_relation_evaluation(session: Session, path: Path) -> dict[str, Any]:
    dataset = load_relation_dataset(path)
    verified, errors = verify_relation_sources(session, dataset)
    rows = evaluate_relation_cases(dataset, verified)
    return {
        "dataset": str(path), "dataset_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "annotation": dataset.model_dump(), "scope": "annotated_fragment_adequacy_not_retrieval_or_generated_answer_evaluation",
        "verified_fragments": verified, "integrity_errors": errors, "predictions": rows,
        "summary": summarize_relation_predictions(rows),
        "by_mode": {mode: summarize_relation_predictions([row for row in rows if row["mode"] == mode])
                    for mode in ("lexical", "cross_lingual_concepts")},
    }
