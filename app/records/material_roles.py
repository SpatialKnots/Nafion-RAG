"""Strict additive source-label roles; legacy fields and scientific statuses stay intact."""

from __future__ import annotations

import json
import re
from typing import Any, Final, Literal, Self
from uuid import UUID

from pydantic import Field, StrictInt, model_validator

from app.records.schema import ContractModel, NonEmpty, RecordCandidate, Sha256, SourceRegion, text_hash

VERSION: Final = "records_material_roles_v0.1"
ROLE_NAMES = ("plasticiser_components", "plasticiser_composition", "plasticiser_basis",
              "membrane_composition", "measurement_environment")
RoleName = Literal["plasticiser_components", "plasticiser_composition", "plasticiser_basis",
                   "membrane_composition", "measurement_environment"]
LegacyField = Literal["medium", "medium_composition", "composition_basis"]
FIELDS: tuple[LegacyField, ...] = ("medium", "medium_composition", "composition_basis")
RATIO = re.compile(r"\d+(?:[.,]\d+)?(?:/\d+(?:[.,]\d+)?)+")
CODE_LABEL = re.compile(r"[A-Za-z][A-Za-z0-9]*")


class RoleSpan(ContractModel):
    """Absolute Unicode codepoint offsets in the registered SourceRegion's page."""

    region_id: Sha256
    start: StrictInt = Field(ge=0)
    end: StrictInt = Field(gt=0)
    text: NonEmpty

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if self.end <= self.start:
            raise ValueError("Role source span must have increasing absolute page offsets")
        return self


class RoleBinding(ContractModel):
    source_field: LegacyField
    selected: RoleSpan
    reference: RoleSpan
    match_kind: Literal["exact_source_label", "complete_group_heading", "basis_boundary_variant"]
    context: tuple[RoleSpan, ...] = Field(min_length=1)


class MaterialRole(ContractModel):
    role: RoleName
    status: Literal["source_label_proposal", "unknown", "unsupported_layout"]
    bindings: tuple[RoleBinding, ...]
    diagnostic: NonEmpty
    scientific_support: Literal["not_evaluated"] = "not_evaluated"

    @model_validator(mode="after")
    def no_unearned_science(self) -> Self:
        if (self.status == "source_label_proposal") != bool(self.bindings):
            raise ValueError("Only a source-label proposal may contain bindings, and requires at least one")
        if self.role in {"membrane_composition", "measurement_environment"} and (self.status != "unknown" or self.bindings):
            raise ValueError("Membrane/environment roles remain unknown without bindings in v0.1")
        return self


class UnassignedSelection(ContractModel):
    source_field: LegacyField
    selected: RoleSpan
    diagnostic: NonEmpty


class RoleProjection(ContractModel):
    schema_version: Literal["records_material_roles_v0.1"] = VERSION
    record_id: UUID
    cell_id: Sha256
    original_candidate_sha256: Sha256
    roles: tuple[MaterialRole, ...] = Field(min_length=5, max_length=5)
    unassigned_selections: tuple[UnassignedSelection, ...]
    missing_source_fields: dict[str, str]
    scientific_admission: Literal["not_evaluated"] = "not_evaluated"

    @model_validator(mode="after")
    def complete_conservative_roles(self) -> Self:
        if {r.role for r in self.roles} != set(ROLE_NAMES):
            raise ValueError("Each of the five material/environment roles must occur exactly once")
        fields = [b.source_field for r in self.roles for b in r.bindings]
        fields += [u.source_field for u in self.unassigned_selections]
        if len(fields) != len(set(fields)):
            raise ValueError("One legacy selection must not be silently assigned to multiple roles")
        if set(fields) & set(self.missing_source_fields) or set(fields) | set(self.missing_source_fields) != set(FIELDS):
            raise ValueError("Every legacy role field must be mapped, unassigned or explicitly missing")
        if any(status not in {"not_found_in_context", "ambiguous", "unsupported"} for status in self.missing_source_fields.values()):
            raise ValueError("Missing role selections require an unchanged non-present source status")
        return self


def candidate_hash(candidate: dict[str, Any]) -> str:
    return text_hash(json.dumps(candidate, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def checked_span(value: dict[str, Any], sources: dict[str, SourceRegion], article_id: UUID) -> RoleSpan:
    span = RoleSpan.model_validate({key: value[key] for key in ("region_id", "start", "end", "text")})
    source = sources.get(span.region_id)
    if (source is None or source.article_id != article_id or not source.start <= span.start < span.end <= source.end
            or source.page_text[span.start:span.end] != span.text):
        raise ValueError("Material-role span differs from exact registered article/source coordinates")
    return span


def _exact(a: RoleSpan, b: RoleSpan) -> bool:
    return (a.region_id, a.start, a.end) == (b.region_id, b.start, b.end)


def project_roles(row: dict[str, Any], sources: dict[str, SourceRegion], context: dict[str, Any]) -> RoleProjection:
    record = RecordCandidate.model_validate(row["candidate"])
    if str(record.record_id) != row["record_id"]:
        raise ValueError("Role projection candidate identity differs from parent audit")
    for evidence in record.evidence_spans():
        source = sources.get(evidence.region_id)
        if (source is None or source.article_id != record.article_id or evidence.end > len(source.quote)
                or source.quote[evidence.start:evidence.end] != evidence.quote):
            raise ValueError("Legacy candidate evidence changed before role projection")
    refs = {key: checked_span(context[key], sources, record.article_id) if context.get(key) else None
            for key in ("sample", "composition", "plasticiser_header", "basis", "medium_label")}
    group = context.get("group")
    group_span = checked_span(group["source"], sources, record.article_id) if group else None
    sample = refs["sample"]
    if sample and any(s is not None and s.region_id != sample.region_id for s in (*refs.values(), group_span)):
        raise ValueError("Material-role context crosses registered source table regions")
    header = refs["plasticiser_header"]
    header_ok = header is not None and header.text == "пластификатора"
    basis = refs["basis"]
    basis_ok = basis is not None and basis.text == "(масс. доли)"
    shared = bool(context.get("shared_block"))
    medium, composition = refs["medium_label"], refs["composition"]
    group_kind = group.get("kind") if group else None
    if group_kind == "mixture" and group_span and medium:
        group_ok = (group_span.region_id == medium.region_id and group_span.start + len("Смеси ") == medium.start
                    and group_span.end == medium.end and group_span.text == "Смеси " + medium.text)
    elif group_kind == "individual" and group_span and composition and medium:
        group_ok = (group_span.text == "Индивидуальные растворители" and _exact(medium, composition)
                    and CODE_LABEL.fullmatch(composition.text) is not None)
    else:
        group_ok = False
    valid_row = header_ok and group_ok and not shared and composition is not None and medium is not None
    basis_inner = None
    if basis_ok and basis:
        source = sources[basis.region_id]
        basis_inner = RoleSpan(region_id=basis.region_id, start=basis.start + 1, end=basis.end - 1,
                               text=source.page_text[basis.start + 1:basis.end - 1])
    bindings: dict[str, list[RoleBinding]] = {name: [] for name in ROLE_NAMES}
    missing: dict[str, str] = {}
    unassigned = []
    for field in FIELDS:
        original = getattr(record, field)
        selected_field = row["selected_fields"][field]
        if selected_field["status"] != original.status:
            raise ValueError("Role selected-field status differs from unchanged candidate")
        raw = selected_field["raw"]
        if original.status != "present":
            if raw is not None:
                raise ValueError("Missing legacy field cannot contain a selected role value")
            missing[field] = original.status
            continue
        if raw is None:
            raise ValueError("Present legacy field lost its source selection")
        selected = checked_span(raw, sources, record.article_id)
        source = sources[selected.region_id]
        if selected.text != original.raw_text or not any(e.region_id == selected.region_id
                and source.start + e.start <= selected.start and source.start + e.end >= selected.end for e in original.evidence):
            raise ValueError("Role selection differs from original field text/cited occurrence")
        role = None
        reference = None
        match: Literal["exact_source_label", "complete_group_heading", "basis_boundary_variant"] = "exact_source_label"
        evidence_context: list[RoleSpan] = [header] if header else []
        if valid_row and medium and _exact(selected, medium):
            role, reference = "plasticiser_components", medium
            evidence_context += [s for s in (refs["sample"], group_span, composition) if s is not None]
        elif valid_row and group_kind == "mixture" and group_span and _exact(selected, group_span):
            role, reference, match = "plasticiser_components", medium, "complete_group_heading"
            evidence_context += [s for s in (refs["sample"], group_span, composition) if s is not None]
        elif (valid_row and group_kind == "mixture" and composition and basis_ok and basis
              and _exact(selected, composition) and RATIO.fullmatch(composition.text)):
            role, reference = "plasticiser_composition", composition
            evidence_context += [s for s in (refs["sample"], group_span, basis) if s is not None]
        elif header_ok and basis_inner and basis and selected.region_id == basis.region_id and (
                basis.start <= selected.start <= basis_inner.start and basis_inner.end <= selected.end <= basis.end):
            role, reference = "plasticiser_basis", basis_inner
            match = "exact_source_label" if _exact(selected, basis_inner) else "basis_boundary_variant"
            evidence_context.append(basis)
        if role and reference:
            bindings[role].append(RoleBinding(source_field=field, selected=selected, reference=reference,
                                              match_kind=match, context=tuple(evidence_context)))
        else:
            unassigned.append(UnassignedSelection(source_field=field, selected=selected,
                diagnostic="No supported source-label role for this occurrence/context. No membrane/environment role inferred."))
    roles = []
    for name in ROLE_NAMES:
        if name in {"membrane_composition", "measurement_environment"}:
            diagnostic = ("Not established by this policy. "
                          "Plasticiser/header, preparation atmosphere and method text do not supply this role.")
            status = "unknown"
        elif bindings[name]:
            diagnostic = ("Printed source-label proposal only; original selection and field retained. "
                          "No chemical interpretation or admission.")
            status = "source_label_proposal"
        else:
            diagnostic = "No qualifying selected source occurrence; missing values are not filled from source opportunities."
            status = "unsupported_layout" if shared or not header_ok else "unknown"
        roles.append(MaterialRole.model_validate({"role": name, "status": status, "bindings": bindings[name], "diagnostic": diagnostic}))
    return RoleProjection(record_id=record.record_id, cell_id=row["cell_id"], original_candidate_sha256=candidate_hash(row["candidate"]),
                          roles=tuple(roles), unassigned_selections=tuple(unassigned), missing_source_fields=missing)
