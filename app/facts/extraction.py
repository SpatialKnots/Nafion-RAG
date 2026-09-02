from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import Article, Chunk, Collection, StructuredFact

RULE_BASED_NUMERIC_SOURCE = "rule_based_numeric_v1"
MAX_FACTS_PER_CHUNK = 12

NUMERIC_UNIT_PATTERN = re.compile(
    r"(?P<value>[-+]?(?:\d+(?:[.,]\d*)?|[.,]\d+)(?:\s*[x×]\s*10\s*[-+]?\d+|[eE][-+]?\d+)?)"
    r"\s*(?P<unit>"
    r"S\s*cm\s*-?\s*1|S\s*/\s*cm|mS\s*cm\s*-?\s*1|mS\s*/\s*cm|"
    r"wt\s*%|mol\s*%|vol\s*%|%|"
    r"°C|degC|K|"
    r"kJ\s*mol\s*-?\s*1|kJ\s*/\s*mol|eV|"
    r"g\s*cm\s*-?\s*3|g\s*/\s*cm\s*3|mg|g|"
    r"nm|µm|um|mm|cm|"
    r"MPa|GPa|Pa"
    r")(?![A-Za-z])",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True)
class StructuredFactCandidate:
    article_id: UUID
    source_chunk_id: UUID
    entity_type: str
    field_name: str
    field_value_text: str
    field_value_numeric: Decimal
    unit: str
    confidence: Decimal
    source: str = RULE_BASED_NUMERIC_SOURCE


def extract_structured_fact_candidates_from_chunk(chunk: Chunk) -> list[StructuredFactCandidate]:
    candidates: list[StructuredFactCandidate] = []
    seen: set[tuple[str, str, str]] = set()
    for line in chunk.text.splitlines():
        for match in NUMERIC_UNIT_PATTERN.finditer(line):
            numeric = _parse_numeric(match.group("value"))
            if numeric is None:
                continue
            unit = _normalize_unit(match.group("unit"))
            field_name = _field_name_for_unit(unit, line)
            value_text = match.group(0).strip()
            key = (field_name, value_text.lower(), unit.lower())
            if key in seen:
                continue
            seen.add(key)
            candidates.append(
                StructuredFactCandidate(
                    article_id=chunk.article_id,
                    source_chunk_id=chunk.id,
                    entity_type="numeric_measurement",
                    field_name=field_name,
                    field_value_text=value_text,
                    field_value_numeric=numeric,
                    unit=unit,
                    confidence=_confidence_for_chunk(chunk),
                )
            )
            if len(candidates) >= MAX_FACTS_PER_CHUNK:
                return candidates
    return candidates


def build_structured_fact_report(
    session: Session,
    *,
    collection_name: str = "literature",
    article_ids: list[UUID] | None = None,
) -> dict[str, object]:
    chunks = _candidate_chunks(session, collection_name=collection_name, article_ids=article_ids)
    candidates = _extract_candidates(chunks)
    return _report_payload(collection_name=collection_name, chunks=chunks, candidates=candidates, applied=False)


def refresh_structured_facts(
    session: Session,
    *,
    collection_name: str = "literature",
    article_ids: list[UUID] | None = None,
) -> dict[str, object]:
    chunks = _candidate_chunks(session, collection_name=collection_name, article_ids=article_ids)
    candidates = _extract_candidates(chunks)
    selected_article_ids = sorted({chunk.article_id for chunk in chunks})
    if selected_article_ids:
        session.execute(
            delete(StructuredFact)
            .where(StructuredFact.article_id.in_(selected_article_ids))
            .where(StructuredFact.source == RULE_BASED_NUMERIC_SOURCE)
        )
    now = datetime.now(UTC)
    for candidate in candidates:
        session.add(
            StructuredFact(
                id=uuid.uuid4(),
                article_id=candidate.article_id,
                entity_type=candidate.entity_type,
                field_name=candidate.field_name,
                field_value_text=candidate.field_value_text,
                field_value_numeric=candidate.field_value_numeric,
                unit=candidate.unit,
                source_chunk_id=candidate.source_chunk_id,
                confidence=candidate.confidence,
                source=candidate.source,
            )
        )
    session.flush()
    report = _report_payload(collection_name=collection_name, chunks=chunks, candidates=candidates, applied=True)
    report["updated_at"] = now.isoformat()
    return report


def _candidate_chunks(session: Session, *, collection_name: str, article_ids: list[UUID] | None) -> list[Chunk]:
    statement = select(Chunk).join(Article, Chunk.article_id == Article.id).join(Collection, Article.collection_id == Collection.id)
    statement = statement.where(Collection.name == collection_name)
    if article_ids is not None:
        statement = statement.where(Chunk.article_id.in_(article_ids))
    statement = statement.order_by(Article.title, Chunk.chunk_index)
    return list(session.scalars(statement))


def _extract_candidates(chunks: list[Chunk]) -> list[StructuredFactCandidate]:
    candidates: list[StructuredFactCandidate] = []
    seen: set[tuple[UUID, str, str, str]] = set()
    for chunk in chunks:
        for candidate in extract_structured_fact_candidates_from_chunk(chunk):
            key = (
                candidate.source_chunk_id,
                candidate.field_name,
                candidate.field_value_text.lower(),
                candidate.unit.lower(),
            )
            if key in seen:
                continue
            seen.add(key)
            candidates.append(candidate)
    return candidates


def _report_payload(
    *,
    collection_name: str,
    chunks: list[Chunk],
    candidates: list[StructuredFactCandidate],
    applied: bool,
) -> dict[str, object]:
    by_field: dict[str, int] = {}
    by_unit: dict[str, int] = {}
    for candidate in candidates:
        by_field[candidate.field_name] = by_field.get(candidate.field_name, 0) + 1
        by_unit[candidate.unit] = by_unit.get(candidate.unit, 0) + 1
    return {
        "status": "applied" if applied else "dry_run",
        "collection": collection_name,
        "source": RULE_BASED_NUMERIC_SOURCE,
        "chunk_count": len(chunks),
        "candidate_count": len(candidates),
        "by_field": dict(sorted(by_field.items())),
        "by_unit": dict(sorted(by_unit.items())),
        "sample": [_candidate_payload(candidate) for candidate in candidates[:25]],
    }


def _candidate_payload(candidate: StructuredFactCandidate) -> dict[str, object]:
    return {
        "article_id": str(candidate.article_id),
        "source_chunk_id": str(candidate.source_chunk_id),
        "entity_type": candidate.entity_type,
        "field_name": candidate.field_name,
        "field_value_text": candidate.field_value_text,
        "field_value_numeric": str(candidate.field_value_numeric),
        "unit": candidate.unit,
        "confidence": str(candidate.confidence),
        "source": candidate.source,
    }


def _parse_numeric(value: str) -> Decimal | None:
    normalized = value.replace(",", ".").replace(" ", "")
    normalized = re.sub(r"[x×]10", "e", normalized, flags=re.IGNORECASE)
    try:
        return Decimal(normalized)
    except InvalidOperation:
        return None


def _normalize_unit(unit: str) -> str:
    compact = re.sub(r"\s+", " ", unit.strip())
    lowered = compact.lower().replace(" ", "")
    if lowered in {"s/cm", "scm-1", "scm1"}:
        return "S cm-1"
    if lowered in {"ms/cm", "mscm-1", "mscm1"}:
        return "mS cm-1"
    if lowered == "wt%":
        return "wt %"
    if lowered == "mol%":
        return "mol %"
    if lowered == "vol%":
        return "vol %"
    if lowered in {"degc", "°c"}:
        return "°C"
    if lowered in {"kj/mol", "kjmol-1", "kjmol1"}:
        return "kJ mol-1"
    if lowered in {"g/cm3", "gcm-3", "gcm3"}:
        return "g cm-3"
    if lowered == "um":
        return "µm"
    return compact


def _field_name_for_unit(unit: str, line: str) -> str:
    lowered_line = line.lower()
    if unit in {"S cm-1", "mS cm-1"}:
        return "conductivity"
    if unit in {"°C", "K"}:
        return "temperature"
    if unit in {"wt %", "mol %", "vol %", "%"}:
        if "swelling" in lowered_line or "uptake" in lowered_line:
            return "swelling_or_uptake"
        return "fraction_or_percent"
    if unit == "kJ mol-1" or unit == "eV":
        return "energy"
    if unit in {"nm", "µm", "mm", "cm"}:
        return "length"
    if unit in {"MPa", "GPa", "Pa"}:
        return "pressure_or_modulus"
    if unit in {"g cm-3", "mg", "g"}:
        return "mass_or_density"
    return "numeric_value"


def _confidence_for_chunk(chunk: Chunk) -> Decimal:
    if chunk.source_type in {"table", "table_caption"}:
        return Decimal("0.80")
    if chunk.source_type in {"method", "formula_block"}:
        return Decimal("0.70")
    return Decimal("0.60")
