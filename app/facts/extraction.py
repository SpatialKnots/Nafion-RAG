from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import Article, Chunk, Collection, StructuredFact
from app.facts.context_cues import NumericContextCue, numeric_context_cues

RULE_BASED_NUMERIC_SOURCE = "rule_based_numeric_v1"
MAX_FACTS_PER_CHUNK = 12

SUPERSCRIPT_DIGITS = "⁰¹²³⁴⁵⁶⁷⁸⁹"
NUMERIC_TYPOGRAPHY = str.maketrans("−⁻⁺" + SUPERSCRIPT_DIGITS, "--+0123456789")
EXPONENT = rf"(?:[-+−]?\s*\d+|[⁺⁻]?[{SUPERSCRIPT_DIGITS}]+)"
MULTIPLICATION_PREFIX = r"(?:[×·∙]|(?<![A-Za-z])x)"

# Previous recognizer is used only to prioritize existing slots under the unchanged
# cap. It never authorizes a candidate rejected by the current recognizer.
LEGACY_SLOT_PATTERN = re.compile(
    r"[-+]?(?:\d+(?:[.,]\d*)?|[.,]\d+)(?:\s*[x×]\s*10\s*[-+]?\d+|[eE][-+]?\d+)?"
    r"\s*(?:S\s*cm\s*-?\s*1|S\s*/\s*cm|mS\s*cm\s*-?\s*1|mS\s*/\s*cm|"
    r"wt\s*%|mol\s*%|vol\s*%|%|°C|degC|K|kJ\s*mol\s*-?\s*1|kJ\s*/\s*mol|eV|"
    r"g\s*cm\s*-?\s*3|g\s*/\s*cm\s*3|mg|g|nm|µm|um|mm|cm|MPa|GPa|Pa)(?![A-Za-z])",
    flags=re.IGNORECASE,
)

NUMERIC_UNIT_PATTERN = re.compile(
    r"(?<![\d.,+−^⁺⁻-])(?:(?<!\w)|(?=[+−-]))"
    rf"(?P<value>[-+−]?(?:\d+(?:[.,]\d*)?|[.,]\d+)(?:\s*[x×·∙]\s*10\s*{EXPONENT}|[eE][-+−]?\d+)?)"
    r"\s*(?P<unit>"
    r"S\s*cm\s*(?:[-−]?\s*1|⁻¹)|S\s*/\s*cm|mS\s*cm\s*(?:[-−]?\s*1|⁻¹)|mS\s*/\s*cm|"
    r"wt\s*%|mol\s*%|vol\s*%|%|"
    r"[°◦]C|degC|K|"
    r"kJ\s*mol\s*(?:[-−]?\s*1|⁻¹)|kJ\s*/\s*mol|eV|"
    r"g\s*cm\s*(?:[-−]?\s*3|⁻³)|g\s*/\s*cm\s*3|mg|g|"
    r"nm|µm|um|mm|cm|"
    r"MPa|GPa|Pa"
    rf")(?![A-Za-z0-9{SUPERSCRIPT_DIGITS}⁺⁻−^/])",
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


@dataclass
class NumericOccurrence:
    """Recognizer match, with half-open Python character offsets in chunk.text.

    Rejected spans may be partial operands/units, not complete scientific facts.
    Duplicate links refer to the first eligible occurrence, even if cap-omitted.
    """

    start: int
    end: int
    text: str
    line_start: int
    line_end: int
    decision: str
    reason: str
    duplicate_of_start: int | None = None
    legacy_slot: bool | None = None
    candidate_index: int | None = None
    context_cues: list[NumericContextCue] = field(default_factory=list)


def extract_structured_fact_candidates_from_chunk(chunk: Chunk) -> list[StructuredFactCandidate]:
    return _extract_chunk(chunk)


def diagnose_numeric_occurrences(chunk: Chunk) -> tuple[list[StructuredFactCandidate], list[NumericOccurrence]]:
    """Read-only diagnostics from the production recognizer and selection path.

    Does not detect arbitrary numbers that NUMERIC_UNIT_PATTERN never matches.
    Does not infer an occurrence page from a multi-page chunk.
    """
    occurrences: list[NumericOccurrence] = []
    candidates = _extract_chunk(chunk, occurrences)
    # Enrichment happens after selection, and only on the diagnostic API path.
    for occurrence in occurrences:
        occurrence.context_cues = numeric_context_cues(
            chunk.text, start=occurrence.start, end=occurrence.end,
            line_start=occurrence.line_start, line_end=occurrence.line_end,
        )
    return candidates, occurrences


def _extract_chunk(
    chunk: Chunk, occurrences: list[NumericOccurrence] | None = None,
) -> list[StructuredFactCandidate]:
    candidates: list[StructuredFactCandidate] = []
    legacy_slots: list[bool] = []
    seen: set[tuple[str, str, str]] = set()
    candidate_occurrences: list[NumericOccurrence] = []
    first_occurrences: dict[tuple[str, str, str], int] = {}
    offset = 0
    for source_line in chunk.text.splitlines(keepends=True):
        line = source_line.rstrip("\r\n")
        line_start = offset
        offset += len(source_line)
        for match in NUMERIC_UNIT_PATTERN.finditer(line):
            occurrence = NumericOccurrence(
                start=line_start + match.start(), end=line_start + match.end(),
                text=match.group(0), line_start=line_start, line_end=line_start + len(line),
                decision="rejected", reason="",
            )
            if occurrences is not None:
                occurrences.append(occurrence)
            prefix = chunk.text[:line_start + match.start()]
            suffix = line[match.end():]
            # A figure panel identifier is not grams or kelvin. Keep standalone
            # compact measurements such as 5g; require an explicit reference cue.
            if re.fullmatch(r"\d+[gk]", match.group(0), flags=re.IGNORECASE) and re.search(
                r"\b(?:fig(?:ure)?s?\.?|рис\.?)\s*"
                r"(?:S?\d+[a-z]?(?:\s*[-–]\s*(?:\d+)?[a-z])?\s*(?:,|and|и)\s*)*$",
                prefix, flags=re.IGNORECASE,
            ):
                occurrence.reason = "figure_reference"
                continue
            # The scalar schema cannot represent uncertainty or ambiguous dashes.
            # Reject their operands, including signs separated by PDF whitespace.
            if re.search(r"(?:±|∓|\uf0b1|\+\s*/\s*[-−]?|[—–−+\-])\s*$", prefix):
                occurrence.reason = "uncertainty_or_dash_prefix"
                continue
            # A bare power of ten is unsupported: never extract only its exponent.
            if re.search(r"(?<![\w.])10\s*\^?\s*$", prefix):
                occurrence.reason = "bare_power_exponent"
                continue
            # Do not truncate an inverse/powered/compound unit to a simpler unit.
            if re.match(rf"\s*(?:\^|/|[-−⁻+]\s*\d|[{SUPERSCRIPT_DIGITS}⁺⁻])", suffix):
                occurrence.reason = "powered_or_compound_unit"
                continue
            # PDF-reviewed corrupt inverse suffix: reject, never guess its value.
            if re.match(r"\s*(?:\\u0001|\x01)", suffix):
                occurrence.reason = "corrupt_inverse_suffix"
                continue
            # A per-time suffix makes a rate, not the numerator's scalar unit.
            if re.match(r"\s*(?:min|s|h)\s*(?:[-−–]\s*1|⁻¹|(?:\\u0001|\x01)1)(?!\d)", suffix):
                occurrence.reason = "rate_suffix"
                continue
            # A capacity denominator is not part of a standalone mass measurement.
            if match.group("unit").lower() in {"g", "mg"} and re.match(
                r"\s*(?:m?Ah)\s*(?:[-−–]\s*1|⁻¹)(?!\d)", suffix,
            ):
                occurrence.reason = "capacity_denominator"
                continue
            # Do not rescue the denominator exponent as a new signed value.
            if re.search(r"(?<![A-Za-z])(?:m?Ah|min|s|h)\s*$", prefix) and match.group("value").startswith(("-", "−", "+")):
                occurrence.reason = "denominator_exponent"
                continue
            # Never rescue a suffix of an unsupported/malformed scientific number.
            # This is matching-only validation; preserve the exact source lexeme.
            if re.search(
                rf"(?:{MULTIPLICATION_PREFIX}\s*|{MULTIPLICATION_PREFIX}\s*10\s*\^?\s*[-+−⁺⁻]?\s*|"
                r"(?:\b[eE]|\d[eE])\s*[-+−]?\s*)$",
                prefix,
                flags=re.IGNORECASE,
            ):
                occurrence.reason = "scientific_number_suffix"
                continue
            numeric = _parse_numeric(match.group("value"))
            if numeric is None:
                occurrence.reason = "invalid_numeric"
                continue
            unit = _normalize_unit(match.group("unit"))
            field_name = _field_name_for_unit(unit, line)
            value_text = match.group(0).strip()
            key = (field_name, value_text.lower(), unit.lower())
            if key in seen:
                occurrence.reason = "duplicate"
                occurrence.decision = "duplicate"
                occurrence.duplicate_of_start = first_occurrences[key]
                continue
            first_occurrences[key] = occurrence.start
            occurrence.decision = "accepted"
            occurrence.reason = "selected"
            occurrence.legacy_slot = LEGACY_SLOT_PATTERN.search(value_text) is not None
            occurrence.candidate_index = len(candidates)
            candidate_occurrences.append(occurrence)
            seen.add(key)
            legacy_slots.append(LEGACY_SLOT_PATTERN.search(value_text) is not None)
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
    # New typographic matches fill spare slots rather than displacing existing
    # recognized values. Corrected full numbers can replace old partial matches.
    selected = sorted(range(len(candidates)), key=lambda i: (not legacy_slots[i], i))[:MAX_FACTS_PER_CHUNK]
    for i, occurrence in enumerate(candidate_occurrences):
        if i not in selected:
            occurrence.decision = "cap_omitted"
            occurrence.reason = "max_facts_per_chunk"
    return [candidates[i] for i in sorted(selected)]


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
    normalized = re.sub(r"\s+", "", value.translate(NUMERIC_TYPOGRAPHY).replace(",", "."))
    normalized = re.sub(r"[x×·∙]10", "e", normalized, flags=re.IGNORECASE)
    try:
        return Decimal(normalized)
    except InvalidOperation:
        return None


def _normalize_unit(unit: str) -> str:
    compact = re.sub(r"\s+", " ", unit.translate(NUMERIC_TYPOGRAPHY).replace("◦", "°").strip())
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
