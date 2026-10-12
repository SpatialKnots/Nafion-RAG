"""User-selected completeness prerequisites; scientific correctness remains unreviewed."""

from __future__ import annotations

from dataclasses import dataclass

from app.records.schema import RecordCandidate


@dataclass(frozen=True)
class ReadinessReport:
    record_id: str
    missing_fields: tuple[str, ...]
    missing_linkage_roles: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "record_id": self.record_id,
            "policy_version": "li_nafion_completeness_v0.1",
            "required_observations_present": not self.missing_fields,
            "required_linkage_proposals_present": not self.missing_linkage_roles,
            "missing_fields": list(self.missing_fields),
            "missing_linkage_roles": list(self.missing_linkage_roles),
            "review_state": "needs_review",
            "scientific_admission": "not_evaluated",
        }


def assess_readiness(record: RecordCandidate) -> ReadinessReport:
    # Sample, temperature, medium composition and method were chosen by the user.
    # Material/property/value/unit and explicit linkage are prerequisites for interpreting them.
    observations = {
        "sample_label": record.sample_label,
        "material_form": record.material_form,
        "property_name": record.property_name,
        "value.raw_value": record.value.raw_value,
        "value.raw_unit": record.value.raw_unit,
        "temperature": record.temperature,
        "medium": record.medium,
        "medium_composition": record.medium_composition,
        "composition_basis": record.composition_basis,
        "method": record.method,
    }
    roles = {link.role for link in record.linkage}
    return ReadinessReport(
        record_id=str(record.record_id),
        missing_fields=tuple(name for name, observation in observations.items() if observation.status != "present"),
        missing_linkage_roles=tuple(
            role for role in ("sample_value", "property_value", "conditions_measurement") if role not in roles
        ),
    )
