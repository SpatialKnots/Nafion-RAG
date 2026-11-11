"""Finite cited-source status/role/completeness audit; not general scientific entailment."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Callable
from copy import deepcopy
from dataclasses import asdict
from typing import Any

from app.generation.providers import (
    AnswerLanguage,
    AnswerProvider,
    AnswerStyle,
    Evidence,
    GeneratedClaim,
    GenerationOutputError,
    ProviderResult,
)

VERSION = "finite_answer_support_v0.2"
MAX_CLAIMS = 64
MAX_TEXT_CHARS = 300000
IDENTITY = {
    "organofluorine": r"organofluorin\w*|органофтор\w*",
    "compound": r"\bcompounds?\b|соединени\w*|соединен\w*",
    "product": r"\bproducts?\b|продукт\w*",
    "reduction": r"\breduct\w*|восстанов\w*|катодн\w*",
    "alkoxide": r"\balkoxid\w*|алкоксид\w*|алкоголят\w*",
    "lithium": r"\blithium\b|лития|литиев\w*",
    "fluorinated": r"\bfluorinat\w*|фторирован\w*",
}
ROLE = r"\b(?:SEI|CEI)\b"
NEG_IDENTIFIED = re.compile(
    r"(?:Although\s+|While\s+)?(?:the\s+)?(?P<subject>[\w -]{3,90}?)\s+"
    r"(?:have|has|had|were|was|are|is)\s+not\s+(?:been\s+)?identified", re.I)
POS_IDENTIFIED = re.compile(
    r"(?:the\s+)?(?P<subject>[\w -]{3,90}?)\s+(?:have|has|had|were|was|are|is)\s+"
    r"(?:been\s+)?identified", re.I)
IDENTIFIED = re.compile(r"идентифицир\w*|\bidentified\b|\bidentif(?:y|ies)\b", re.I)
HEDGE = re.compile(r"(?:\bnot\b|\bnever\b|\bno\b|\bmay\b|\bmight\b|\bcould\b|\bif\b|"
                   r"\bhypothes\w*|\bsuggest\w*|\bpropos\w*|\bне\b|\bесли\b|\bмог\w*|\bмож\w*|"
                   r"\bпредполож\w*|\bпредполага\w*|\bвозможно\b|\bincorrectly\b|\bwrongly\b|\bошибоч\w*)", re.I)
NONCURRENT = re.compile(r"\b(?:previous|prior|earlier|literature|hypothetical|future|planned|imagine)\b|"
                        r"\b(?:предыдущ\w*|литератур\w*|планиру\w*|гипотетич\w*)\b", re.I)
ROLE_HEDGE = re.compile(HEDGE.pattern + r"|\bcan\b|\bpossibl\w*|\bputative\b|\bвозмож\w*", re.I)
COMPOSITION = re.compile(r"consists?\s+of|composed\s+of|contains?|rich\s+in|содерж\w*|состав\w*|обогащ\w*|богат\w*", re.I)
FORMULA = re.compile(r"(?<!\w)[A-Z][A-Za-z0-9₀₁₂₃₄₅₆₇₈₉]*\b")
ENERGY = re.compile(
    r"energy\s+density\s+of\s*[>~≈]?[\s\u200b\u00ad]*(?P<value>\d+(?:\.\d+)?)\s*"
    r"Wh\s*kg\s*[−–-]\s*1\s+based\s+on\s+(?:the\s+)?"
    r"(?P<basis>(?:total|combined)\s+cathode\s*/\s*anode\s+masses)", re.I)
ANY_ENERGY = re.compile(
    r"energy\s+density\s+of\s*[>~≈]?[\s\u200b\u00ad]*(?P<value>\d+(?:\.\d+)?)\s*"
    r"Wh\s*kg\s*[−–-]\s*1\s+based\s+on\s+(?:the\s+)?(?P<basis>[^.;]{1,120})", re.I)
MIXTURE = re.compile(
    r"cycling\s+efficiency\s+of\s+(?:the\s+)?(?P<samples>.{1,180}?)\s+systems?\s+"
    r"(?:maintained|remained|reached|was|were)\s+(?:at\s+)?(?:about\s*|approximately\s*|~\s*)?"
    r"(?P<value>\d+(?:\.\d+)?)\s*%", re.I | re.S)
MIX_LABEL = re.compile(r"(?<![A-Za-z0-9])(?P<prefix>[A-Z][A-Za-z0-9]+)[−–-](?P<component>[A-Z][A-Za-z0-9]+)(?![A-Za-z0-9])")


def normal(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text)).strip()


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def segments(text: str) -> list[tuple[int, int, str]]:
    """Keep raw offsets; PDF soft line breaks alone are not sentence boundaries."""
    bounds = [0, *[m.end() for m in re.finditer(r";\s*|[.!?]\s+(?=[A-ZА-ЯЁ])|,\s+(?:but|но|а)\s+|\n\s*\n", text)], len(text)]
    return [(a, b, text[a:b]) for a, b in zip(bounds, bounds[1:], strict=False) if text[a:b].strip()]


def local_clause(text: str, position: int) -> str:
    return next((s for a, b, s in segments(text) if a <= position < b), "")


def keys(text: str) -> set[str]:
    return {key for key, pattern in IDENTITY.items() if re.search(pattern, normal(text), re.I)}


def anchor(source: Evidence, start: int, end: int) -> dict[str, Any]:
    return {"citation_id": source.citation_id, "article_id": source.article_id, "chunk_id": source.chunk_id,
            "source_type": source.source_type, "page_range": [source.page_start, source.page_end],
            "raw_text_sha256": sha(source.text), "start": start, "end": end, "text": source.text[start:end]}


def raw_sources(evidence: list[Evidence]) -> list[Evidence]:
    return [e for e in evidence if not e.source_type.endswith("_derived")]


def status_observations(sources: list[Evidence]) -> list[dict[str, Any]]:
    found = []
    for source in sources:
        for start, _, sentence in segments(source.text):
            if NONCURRENT.search(sentence):
                continue
            for m in NEG_IDENTIFIED.finditer(sentence):
                identity = keys(m["subject"])
                if len(identity) >= 2:
                    found.append({"kind": "not_identified", "identity_keys": sorted(identity),
                                  "anchor": anchor(source, start + m.start(), start + m.end())})
            if not HEDGE.search(sentence):
                for m in POS_IDENTIFIED.finditer(sentence):
                    identity = keys(m["subject"])
                    if len(identity) >= 2:
                        found.append({"kind": "identified", "identity_keys": sorted(identity),
                                      "anchor": anchor(source, start + m.start(), start + m.end())})
    return found


def species(text: str) -> list[str]:
    return sorted({m[0] for m in FORMULA.finditer(text) if len(m[0]) > 1 and m[0] not in {"SEI", "CEI", "XPS", "The"}})


def role_observations(sources: list[Evidence]) -> list[dict[str, Any]]:
    found = []
    for source in sources:
        parts = segments(source.text)
        for index, (start, end, sentence) in enumerate(parts):
            roles = set(re.findall(ROLE, sentence, re.I))
            if len(roles) != 1 or NONCURRENT.search(sentence) or ROLE_HEDGE.search(sentence):
                continue
            role = next(iter(roles)).upper()
            # Direct composition grammar, excluding article-wide role membership.
            comp = COMPOSITION.search(sentence)
            if comp:
                values = species(sentence[comp.end():])
                if len(values) >= 2:
                    found.append({"kind": "composition_species", "role": role, "species": values,
                                  "anchors": [anchor(source, start, end)], "binding": "single_role_composition_clause"})
            # Bounded anaphor: XPS role statement -> immediately following 'these species (...)'.
            if not re.search(r"\bXPS\s+(?:confirmed|revealed|showed|indicated)\b", sentence, re.I):
                continue
            if index + 1 >= len(parts):
                continue
            next_start, next_end, following = parts[index + 1]
            if (set(r.upper() for r in re.findall(ROLE, following, re.I)) - {role}
                    or NONCURRENT.search(following) or ROLE_HEDGE.search(following)):
                continue
            match = re.search(r"(?:these|such)\s+[\w -]*species\s*\((?P<items>[^()]{1,150})\)", following, re.I)
            if match:
                values = species(match["items"])
                if len(values) >= 2:
                    found.append({"kind": "composition_species", "role": role, "species": values,
                        "anchors": [anchor(source, start, end), anchor(source, next_start, next_end)],
                        "binding": "adjacent_xps_role_and_these_species_clause"})
    return found


def identification_findings(claim: GeneratedClaim, observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    found = []
    for start, end, sentence in segments(claim.text):
        assertions = list(IDENTIFIED.finditer(sentence))
        # Without a clause boundary two status predicates cannot safely share a subject.
        if len(assertions) != 1:
            continue
        for assertion in assertions:
            if HEDGE.search(sentence[:assertion.start()]):
                continue
            active = re.search(r"идентифицировали|идентифицируют|идентифицирует", assertion[0], re.I)
            actor = re.search(r"\b(?:authors?|researchers?|we|they)\b", sentence[:assertion.start()], re.I)
            identity = keys(sentence[assertion.end():] if active or actor else sentence[:assertion.start()])
            bound = [o for o in observations if o["kind"] == "not_identified" and set(o["identity_keys"]) <= identity]
            alternatives = [o for o in observations if o["kind"] == "identified" and set(o["identity_keys"]) <= identity]
            if bound and not alternatives:
                found.append({"code": "identification_status_conflict", "severity": "conflict",
                    "claim_span": {"start": start, "end": end, "text": sentence}, "source_observations": bound,
                    "meaning": "affirmative identification versus explicitly unestablished identity in cited raw text"})
    return found


def role_findings(claim: GeneratedClaim, observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    found = []
    for start, end, sentence in segments(claim.text):
        roles = {r.upper() for r in re.findall(ROLE, sentence, re.I)}
        if len(roles) != 1 or ROLE_HEDGE.search(sentence) or not COMPOSITION.search(sentence):
            continue
        values = set(species(sentence))
        bound = [o for o in observations if len(set(o["species"]) & values) >= 2]
        owners = {o["role"] for o in bound}
        if len(owners) == 1 and roles != owners:
            found.append({"code": "interphase_role_conflict", "severity": "conflict",
                "claim_span": {"start": start, "end": end, "text": sentence},
                "asserted_role": next(iter(roles)), "bound_role": next(iter(owners)),
                "source_observations": bound, "meaning": "same composition fingerprint assigned to a different interphase role"})
    return found


def number_present(value: str, text: str) -> bool:
    value = value.rstrip("0").rstrip(".") if "." in value else value
    suffix = r"0*" if "." in value else r"(?:\.0+)?"
    return re.search(r"(?<![\d.])" + re.escape(value) + suffix + r"(?![\d.])", normal(text)) is not None


def completeness(question: str, claims: list[GeneratedClaim], sources: dict[str, Evidence]
                 ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    findings: list[dict[str, Any]] = []
    inspection: list[dict[str, Any]] = []
    answer = "\n".join(c.text for c in claims)
    for ci, claim in enumerate(claims, 1):
        cited = raw_sources([sources[i] for i in claim.citation_ids])
        if len({e.article_id for e in cited}) != 1:
            continue
        if re.search(r"удельн\w*\s+энерги|specific\s+energy|energy\s+density", normal(question), re.I):
            source_contracts = 0
            for source in cited:
                for m in ENERGY.finditer(source.text):
                    if (not number_present(m["value"], claim.text) or not re.search(r"energy|энерги", claim.text, re.I)
                            or NONCURRENT.search(local_clause(source.text, m.start()))
                            or HEDGE.search(local_clause(source.text, m.start()))):
                        continue
                    alternatives = [o for e in cited for o in ANY_ENERGY.finditer(e.text)
                        if o["value"] == m["value"] and not re.search(r"(?:total|combined)\s+cathode\s*/\s*anode\s+masses",
                                                                                    o["basis"], re.I)]
                    if alternatives:
                        inspection.append({"claim_id": f"C{ci}", "family": "energy_mass_basis",
                                           "status": "ambiguous_source_bases_not_evaluated"})
                        continue
                    source_contracts += 1
                    basis_present = bool(re.search(r"cathod|катод", claim.text, re.I)
                        and re.search(r"anod|анод", claim.text, re.I) and re.search(r"mass|масс", claim.text, re.I)
                        and re.search(r"total|combined|суммар|совокуп|общ", claim.text, re.I))
                    if re.search(r"(?:\bnot\b|\bне\b)\s+(?:[\w/-]+\s+){0,7}(?:mass\w*|масс\w*)", claim.text, re.I):
                        basis_present = False
                    if not basis_present:
                        findings.append({"code": "missing_energy_mass_basis", "severity": "incomplete", "claim_id": f"C{ci}",
                            "source_value": m["value"], "source_basis": m["basis"],
                            "source_observations": [{"anchor": anchor(source, m.start(), m.end())}],
                            "meaning": "reported electrode-mass energy needs its explicit mass denominator"})
            inspection.append({"claim_id": f"C{ci}", "family": "energy_mass_basis", "source_contracts": source_contracts,
                               "status": "finite_scope_only" if source_contracts else "no_bound_current_source_contract"})
        if not re.search(r"cycling\s+efficiency|эффективност\w*\s+циклирован", normal(question), re.I):
            continue
        if not re.search(r"efficien|эффективност", claim.text, re.I):
            continue
        source_contracts = 0
        for source in cited:
            for m in MIXTURE.finditer(source.text):
                if (not number_present(m["value"], claim.text) or NONCURRENT.search(local_clause(source.text, m.start()))
                        or HEDGE.search(local_clause(source.text, m.start()))):
                    continue
                labels = [label for label in MIX_LABEL.finditer(m["samples"]) if re.search(
                    r"(?<!\w)" + re.escape(label["component"]) + r"(?!\w)", normal(question), re.I)]
                for label in labels:
                    # A hyphenated run/sample code alone does not prove mixture semantics.
                    # v0.2 supports the explicit EC co-solvent qualifier only.
                    if label["prefix"] != "EC":
                        inspection.append({"claim_id": f"C{ci}", "family": "cycling_mixture_qualifier",
                                           "status": "unrecognized_sample_prefix_not_evaluated"})
                        continue
                    source_contracts += 1
                    prefix = label["prefix"]
                    present = re.search(r"(?<!\w)" + re.escape(prefix) + r"(?!\w)", normal(answer), re.I)
                    if prefix == "EC":
                        present = present or re.search(r"ethylene\s+carbonate|этиленкарбонат", normal(answer), re.I)
                    if not present:
                        findings.append({"code": "missing_mixture_qualifier", "severity": "incomplete", "claim_id": f"C{ci}",
                            "source_value": m["value"], "source_sample": label[0], "required_prefix": prefix,
                            "source_observations": [{"anchor": anchor(source, m.start(), m.end())}],
                            "meaning": "cited mixture performance is expressed without its co-component qualifier"})
        inspection.append({"claim_id": f"C{ci}", "family": "cycling_mixture_qualifier", "source_contracts": source_contracts,
                           "status": "finite_scope_only" if source_contracts else "no_bound_current_source_contract"})
    # Duplicate overlapping chunks are not independent findings.
    unique: dict[tuple[Any, ...], dict[str, Any]] = {}
    for finding in findings:
        key = (finding["code"], finding["claim_id"], finding.get("source_value"), finding.get("required_prefix"))
        unique.setdefault(key, finding)
    return list(unique.values()), inspection or [{"status": "completeness_question_family_not_implemented"}]


def audit(question: str, claims: list[GeneratedClaim], evidence: list[Evidence]) -> dict[str, Any]:
    if not isinstance(question, str) or not question.strip() or len(claims) > MAX_CLAIMS:
        raise ValueError("Invalid question/claim budget")
    if len(question) + sum(len(c.text) for c in claims) + sum(len(e.text) for e in evidence) > MAX_TEXT_CHARS:
        raise ValueError("Audit text budget exceeded")
    sources = {e.citation_id: e for e in evidence}
    if len(sources) != len(evidence):
        raise ValueError("Duplicate source citation IDs")
    if any(not c.text.strip() or not c.citation_ids or len(set(c.citation_ids)) != len(c.citation_ids)
           or set(c.citation_ids) - sources.keys() for c in claims):
        raise ValueError("Empty/unbound/duplicate claim citations")
    rows: list[dict[str, Any]] = []
    for index, claim in enumerate(claims, 1):
        cited = raw_sources([sources[i] for i in claim.citation_ids])
        if len({e.article_id for e in cited}) > 1:
            rows.append({"claim_id": f"C{index}", "original_claim": asdict(claim), "findings": [],
                "source_status_observations": [], "source_role_observations": [],
                "semantic_support": "cross_work_binding_not_evaluated", "scientific_validity": "not_evaluated"})
            continue
        status, roles = status_observations(cited), role_observations(cited)
        findings = identification_findings(claim, status) + role_findings(claim, roles)
        rows.append({"claim_id": f"C{index}", "original_claim": asdict(claim), "findings": findings,
            "source_status_observations": status, "source_role_observations": roles,
            "semantic_support": "bounded_conflict_detected" if findings else "not_evaluated",
            "scientific_validity": "not_evaluated"})
    gaps, inspection = completeness(question, claims, sources)
    findings = [f for row in rows for f in row["findings"]]
    decision = "withhold_conflict" if findings else "withhold_incomplete" if gaps else "not_blocked_by_finite_checks"
    inputs = {"question": question, "claims": [asdict(c) for c in claims], "evidence": [asdict(e) for e in evidence]}
    return {"version": VERSION, "input_sha256": sha(json.dumps(inputs, ensure_ascii=False, sort_keys=True, allow_nan=False)),
        "claims": rows, "completeness_findings": gaps, "completeness_inspection": inspection, "decision": decision,
        "findings_count": len(findings) + len(gaps), "not_evaluated": ["general_entailment", "general_completeness",
            "unrecognized_grammar", "scientific_validity", "independent_accuracy"],
        "scope": "finite actually-cited raw-source contracts; not scientific acceptance",
        "repair_performed": False, "provider_calls": 0, "default_admission_changed": False}


class AuditedAnswerProvider:
    """Explicit opt-in: abstain as a whole; no retry, partial selection or prose repair."""

    def __init__(self, provider: AnswerProvider, on_report: Callable[[dict[str, Any]], None] | None = None) -> None:
        self.provider, self.on_report = provider, on_report

    def generate(self, question: str, evidence: list[Evidence], *, answer_style: AnswerStyle = "claims",
                 answer_language: AnswerLanguage = "auto") -> ProviderResult:
        result = self.provider.generate(question, evidence, answer_style=answer_style, answer_language=answer_language)
        if result.answerable != bool(result.claims):
            raise GenerationOutputError("Underlying provider answerable/claims contract mismatch")
        if not result.answerable:
            return result
        report = audit(question, result.claims, evidence)
        blocked = report["decision"].startswith("withhold_")
        report["wrapper_decision"] = {"origin": "deterministic_finite_source_audit", "native_answerable": result.answerable,
                                      "guarded_answerable": not blocked, "second_provider_call": False}
        if self.on_report:
            self.on_report(deepcopy(report))
        if blocked:
            return ProviderResult(answerable=False, claims=[], provider=result.provider, model=result.model)
        return result
