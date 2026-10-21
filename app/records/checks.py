"""Automatic, source-bound technical checks; no scientific admission."""

from __future__ import annotations

import re
from collections import Counter
from typing import Literal

from pydantic import Field

from app.records.readiness import assess_readiness
from app.records.review import observations_for_review
from app.records.schema import CandidateBundle, ContractModel, EvidenceSpan, NonEmpty, RecordCandidate

VERSION = "records_checks_v0.1"
LINK_ROLES = ("sample_value", "property_value", "conditions_measurement")

# Recognize syntax without evaluating, normalizing or imposing scientific limits.
_DECIMAL = r"[+−-]?(?:[0-9]+(?:\.[0-9]+)?|\.[0-9]+)"
_SCALAR = re.compile(
    rf"(?P<coefficient>{_DECIMAL})(?:"
    r"\s*[eE]\s*(?P<e_exponent>[+−-]?[0-9]+)|"
    r"\s*×\s*10(?:\s*\^\s*(?P<caret_exponent>[+−-]?[0-9]+)|"
    r"\s*(?P<signed_exponent>[+−-]\s*[0-9]+)|(?P<superscript_exponent>[⁺⁻]?[⁰¹²³⁴⁵⁶⁷⁸⁹]+))"
    r")?"
)


class RecordCheck(ContractModel):
    rule_id: NonEmpty
    status: Literal["pass", "fail", "unknown"]
    reason: NonEmpty
    fields: tuple[str, ...] = ()
    evidence: tuple[EvidenceSpan, ...] = ()
    details: dict[str, str] = Field(default_factory=dict)


class RecordCheckReport(ContractModel):
    checks_version: Literal["records_checks_v0.1"] = "records_checks_v0.1"
    completeness_policy: Literal["li_nafion_completeness_v0.1"] = "li_nafion_completeness_v0.1"
    record_id: str
    technical_outcome: Literal["incomplete", "unresolved"]
    review_state: Literal["needs_review"] = "needs_review"
    scientific_admission: Literal["not_evaluated"] = "not_evaluated"
    checks: tuple[RecordCheck, ...]


def scalar_notation(raw: str) -> dict[str, str] | None:
    """Return only exact syntactic components; unsupported is not an error claim."""
    match = _SCALAR.fullmatch(raw)
    if match is None:
        return None
    return {key: value for key, value in match.groupdict().items() if value is not None}


def _checks_for_record(record: RecordCandidate) -> RecordCheckReport:
    readiness = assess_readiness(record)
    observations = dict(observations_for_review(record))
    required = (
        "sample_label", "material_form", "property_name", "value.raw_value", "value.raw_unit",
        "temperature", "medium", "medium_composition", "composition_basis", "method",
    )
    checks = [RecordCheck(
        rule_id="source.exact_spans", status="pass", fields=tuple(observations), evidence=record.evidence_spans(),
        reason="Bundle hashes, article membership and exact text coordinates were revalidated; semantic support is not established.",
    )]
    for name in required:
        observation = observations[name]
        checks.append(RecordCheck(
            rule_id=f"required.{name}", fields=(name,), evidence=observation.evidence,
            status="fail" if name in readiness.missing_fields else "pass",
            reason=f"Observed status: {observation.status}. Presence is not scientific correctness.",
        ))
    role_counts: Counter[str] = Counter(link.role for link in record.linkage)
    for role in LINK_ROLES:
        spans = tuple(span for link in record.linkage if link.role == role for span in link.evidence)
        checks.extend((
            RecordCheck(
                rule_id=f"linkage.{role}.unique_proposal", fields=(f"linkage.{role}",), evidence=spans,
                status="pass" if role_counts[role] == 1 else "fail",
                reason=f"Expected one linkage proposal; observed {role_counts[role]}. No proposal is silently merged.",
            ),
            RecordCheck(
                rule_id=f"linkage.{role}.scientific_support", fields=(f"linkage.{role}",), evidence=spans,
                status="unknown", reason="Exact quoted text and role labels do not validate the scientific relationship.",
            ),
        ))
    raw = record.value.raw_value
    components = scalar_notation(raw.raw_text) if raw.raw_text is not None and record.value.representation == "scalar" else None
    checks.extend((
        RecordCheck(
            rule_id="quantity.scalar_notation", fields=("value.raw_value", "value.representation"), evidence=raw.evidence,
            status="pass" if components is not None else "unknown", details=components or {},
            reason=("Supported scalar syntax only; no numeric interpretation, OCR validation or scientific acceptance."
                    if components is not None else
                    "Scalar syntax unsupported, unavailable or not requested by representation; original text is retained."),
        ),
        RecordCheck(
            rule_id="quantity.scientific_meaning", status="unknown",
            fields=("value.raw_value", "value.approximation", "value.uncertainty", "temperature"),
            evidence=raw.evidence + record.temperature.evidence,
            reason="Signs, exponents, ranges, uncertainty and measurement/temperature pairing require scientific validation.",
        ),
        RecordCheck(
            rule_id="unit.compatibility", status="unknown", fields=("value.raw_unit", "property_name"),
            evidence=record.value.raw_unit.evidence + record.property_name.evidence,
            reason="No approved unit interpretation/conversion registry is applied in this version.",
        ),
        RecordCheck(
            rule_id="origin.attribution", status="unknown", fields=("data_origin",), evidence=record.data_origin.evidence,
            reason="Author wording is retained; experimental/calculated/cited-result attribution is not independently validated.",
        ),
        RecordCheck(
            rule_id="record.scientific_identity", status="unknown", fields=("sample_label", "work_group_id"),
            evidence=record.sample_label.evidence,
            reason="Sample identity, cross-publication equivalence and independent measurement identity are not established.",
        ),
    ))
    return RecordCheckReport(record_id=str(record.record_id), checks=tuple(checks),
                             technical_outcome="incomplete" if any(check.status == "fail" for check in checks) else "unresolved")


def check_bundle(bundle: CandidateBundle) -> tuple[RecordCheckReport, ...]:
    # Reparse, including objects created through model_copy/model_construct bypasses.
    validated = CandidateBundle.model_validate_json(bundle.model_dump_json())
    return tuple(_checks_for_record(record) for record in validated.records)
