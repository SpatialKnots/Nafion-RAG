"""Finite source-bound coverage checks; not general semantic entailment.

Only raw selected evidence supplies quantities. The contract never repairs text,
converts units or establishes scientific ownership. Missing finite source patterns
are diagnosed separately from scientific absence of evidence.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

from app.generation.providers import Evidence, GeneratedClaim, GenerationOutputError
from app.generation.source_paraphrases import PATTERNS, PREFIX_GUARD
from app.generation.source_paraphrases import VERSION as PARAPHRASE_VERSION
from app.retrieval.requested_context import normalize

VERSION = "source_bound_answer_fidelity_v0.2"


def normal(text: str) -> str:
    return normalize(text).replace("−", "-").replace("–", "-").replace("^", "")


def has(pattern: str, text: str) -> bool:
    return re.search(pattern, text) is not None


@dataclass(frozen=True)
class Requirement:
    key: str
    instruction: str
    patterns: tuple[str, ...]
    anchors: list[dict[str, Any]]


@dataclass(frozen=True)
class Contract:
    family: str
    requirements: list[Requirement]
    missing_source_roles: list[str]

    @property
    def eligible(self) -> bool:
        return bool(self.requirements) and not self.missing_source_roles

    def metadata(self) -> dict[str, Any]:
        result = {"version": VERSION, "family": self.family, "eligible": self.eligible,
                "missing_source_roles": self.missing_source_roles,
                "requirements": [{"key": r.key, "instruction": r.instruction, "anchors": r.anchors}
                                 for r in self.requirements],
                "scope": "finite_textual_coverage_not_semantic_entailment",
                "scientific_ownership_verified": False, "units_converted": False}
        roles = [r.key for r in self.requirements if any(a.get("grammar_version") == PARAPHRASE_VERSION for a in r.anchors)]
        if roles:
            result["source_paraphrases"] = {"version": PARAPHRASE_VERSION, "roles": roles}
        return result


def family(question: str) -> str | None:
    q = normal(question)
    if ("li2o" in q and has(r"однофаз|single.phase", q) and has(r"объ[её]м|bulk", q)
            and has(r"комнатн|room temperature", q) and has(r"услов|condition", q)
            and has(r"проводим|conductiv", q)):
        return "model_layer_bulk_conductivity_conditions"
    if (has(r"li[ -]*nafion", q) and "ec/sl" in q and has(r"смешени|mixing", q)
            and has(r"нагрев|heating", q) and has(r"охлажд|cooling", q) and has(r"структур|structur", q)):
        return "plasticiser_cycles_structure_qualifiers"
    return None


def _find(sources: list[Evidence], pattern: str, *, paraphrase: bool = False) -> list[dict[str, Any]]:
    anchors = []
    for source in sources:
        for match in re.finditer(pattern, source.text, re.I | re.S):
            prefix = re.split(r"[.!?]\s+", source.text[max(0, match.start() - 160):match.start()])[-1]
            if has(r"\b(?:no|never)\s*$|\bnot true that\b|"
                   r"\b(?:hypothetical|proposed|planned|assumed|imagine|future)\b", normal(prefix)):
                continue
            if paraphrase and has(PREFIX_GUARD, normal(prefix)):
                continue
            anchors.append({"citation_id": source.citation_id, "article_id": source.article_id,
                            "chunk_id": source.chunk_id, "start": match.start(), "end": match.end(),
                            "text": match.group(), "groups": match.groupdict(),
                            "raw_chunk_sha256": hashlib.sha256(source.text.encode()).hexdigest()})
            if paraphrase:
                anchors[-1]["grammar_version"] = PARAPHRASE_VERSION
    return anchors


def _role_anchors(sources: list[Evidence], key: str, legacy_pattern: str) -> list[dict[str, Any]]:
    anchors = _find(sources, legacy_pattern)
    if key in PATTERNS:
        anchors.extend(_find(sources, PATTERNS[key], paraphrase=True))
    return anchors


def _number(value: str) -> str:
    # Equivalent decimal spelling only; no unit or scale conversion.
    literal = re.escape(value.rstrip("0").rstrip(".") if "." in value else value)
    return r"(?<![\d.])" + literal + r"(?:\.0+)?(?![\d.])"


def _conductivity(sources: list[Evidence]) -> Contract:
    found: list[Requirement] = []
    missing = []

    def add(key: str, source_pattern: str, instruction: str, patterns: tuple[str, ...]) -> list[dict[str, Any]]:
        anchors = _role_anchors(sources, key, source_pattern)
        if not anchors:
            missing.append(key)
        else:
            found.append(Requirement(key, instruction, patterns, anchors))
        return anchors

    comparison = add("absolute_conductivities",
        r"single.component\s+Li2O\s+SEI\s*\(\s*~?(?P<layer>10[-−–]\d+)\s*S/cm\).*?"
        r"sintered\s+bulk\s+Li2O.{0,100}?\(\s*~?(?P<bulk>10[-−–]\d+)\s*S/cm\).*?at\s+room\s+temperature",
        "Report both absolute conductivities with units, layer versus bulk, at room temperature; "
        "say bulk is from prior literature, not a measurement of the layer.", ())
    if comparison:
        pairs = {(a["groups"]["layer"], a["groups"]["bulk"]) for a in comparison}
        if len(pairs) != 1:
            missing.append("ambiguous_absolute_conductivities")
        else:
            layer, bulk = next(iter(pairs))
            unit = r"\s*(?:s\s*/\s*cm|s\s*[·⋅]?\s*cm-1|см\s*/\s*см)"
            layer_value, bulk_value = (r"(?<!\d)" + re.escape(normal(v)) + r"(?!\d)" + unit for v in (layer, bulk))
            owner_l, owner_b = r"(?:сло\w*|интерфейс\w*|\bsei\b|layer)", r"(?:объ[её]м\w*|bulk)"
            pair = (owner_l + r".{0,140}?" + layer_value + r".{0,220}?" + owner_b + r".{0,140}?" + bulk_value)
            reverse = (owner_b + r".{0,140}?" + bulk_value + r".{0,220}?" + owner_l + r".{0,140}?" + layer_value)
            found[-1] = Requirement(found[-1].key, found[-1].instruction,
                (f"(?:{pair}|{reverse})", r"комнатн|room temperature", r"литератур|literature"), comparison)
    synthesis = add("gas_synthesis",
        r"Li\s+foils\s+were\s+reacted\s+in\s+O2\s+gas.{0,100}?from\s+(?P<low>\d+(?:\.\d+)?)\s*°C\s+to\s*"
        r"(?P<high>\d+(?:\.\d+)?)\s*°C\s+for\s+(?P<hours>\d+(?:\.\d+)?)\s+hours?[^.]*\.",
        "State O2 treatment of Li foil: source temperature range and duration. Explicitly label this as synthesis, "
        "separate from EIS measurement temperature.", ())
    if synthesis:
        values = {tuple(a["groups"][k] for k in ("low", "high", "hours")) for a in synthesis}
        if len(values) != 1:
            missing.append("ambiguous_gas_synthesis")
        else:
            low, high, hours = next(iter(values))
            found[-1] = Requirement(found[-1].key, found[-1].instruction,
                (r"o2|кислород", r"синтез|получен|обработ|reacted|synthesi|treat",
                 _number(low) + r"\s*(?:°\s*c\s*)?(?:-|до|to)\s*" + _number(high) + r"\s*°\s*c",
                 _number(hours) + r"\s*(?:час|hours?\b|h\b)"), synthesis)
    medium = add("eis_medium",
        r"electrolyte\s*\(\s*(?P<concentration>\d+(?:\.\d+)?)\s*(?-i:M)\s*LiPF6\s+in\s+EC/DEC,\s*"
        r"v/v\s*=\s*(?P<left>\d+)/(?P<right>\d+)[^)]*\)",
        "Give EIS, symmetric Li cells, salt concentration and EC/DEC ratio explicitly by volume.", ())
    if medium:
        values = {tuple(a["groups"][k] for k in ("concentration", "left", "right")) for a in medium}
        if len(values) != 1:
            missing.append("ambiguous_eis_medium")
        else:
            concentration, left, right = next(iter(values))
            found[-1] = Requirement(found[-1].key, found[-1].instruction,
                (r"eis|импеданс", r"симметр|symmetric", r"ec\s*/\s*dec",
                 _number(concentration) + r"\s*m\s*lipf6", re.escape(left) + r"\s*[:/]\s*" + re.escape(right),
                 r"по объ[её]му|объ[её]мн|by volume|v/v"), medium)
    return Contract("model_layer_bulk_conductivity_conditions", found, missing)


def _structure(sources: list[Evidence]) -> Contract:
    specs = [
        ("cycle_retention", r"the\s+higher\s+the\s+mixing\s+temperature.{0,350}?cooling\s+cycle.{0,150}?barely\s+noticeable\.",
         "Explain increasing uptake on heating and retention of achieved uptake on cooling, not disappearance of uptake.",
         (r"нагрев|heating", r"увелич|increas", r"охлажд|cooling", r"сохраня|retain|preserv")),
        ("hold_observation", r"long.term\s*\((?P<days>\d+)\s+days\).{0,100}?at\s+(?P<temperature>\d+)\s*◦C.{0,250}?"
         r"did\s+not\s+in(?:ﬂ|fl)uence\s+the\s+obtained\s+W\s+values\.",
         "Report hold duration/temperature and unchanged uptake; keep it an observation, not proof of irreversibility.",
         (r"сохраня|не измен|не повлия|unchanged|did not|не привел",)),
        ("alternative_interpretations", r"suggests\s+either.{0,200}?equilibrium\s+state.{0,100}?syneresis.{0,100}?long\s+time\.",
         "Keep both source alternatives: near equilibrium OR extremely slow syneresis.",
         (r"равновес|equilibrium", r"синерез|syneres", r"медлен|slow|long time", r"либо|или|\bor\b")),
        ("irreversibility_hypothesis", r"hysteresis.{0,180}?supports\s+the\s+hypothesis.{0,150}?irreversible.{0,220}?temperatures\.",
         "Call irreversible rearrangement a hypothesis supported by hysteresis, not a proven result.",
         (r"гипотез|hypothes", r"необратим|irrevers")),
        ("slight_crystalline_intensity", r"somewhat\s+reduces.{0,130}?crystal\s+re(?:ﬂ|fl)ection"
         r".{0,200}?slight\s+decrease.{0,100}?intensity\.",
         "Describe only some/slight reduction of the named crystalline reflection intensity; do not infer crystal loss.",
         (r"небольш|незначитель|некотор|slight|somewhat", r"интенсив|intensit", r"кристалл|crystal")),
        ("preserved_crystalline_regions", r"crystalline\s+regions,\s*which\s+remain\s+nearly\s+unchanged.{0,100}?°?◦?C\.",
         "Explicitly state that crystalline regions remain nearly unchanged; distinguish this from intensity changes.",
         (r"кристалл|crystall", r"практически (?:неизмен|не измен)|почти (?:неизмен|не измен)|nearly unchanged|practically unchanged")),
        ("old_and_new_amorphous_halos", r"halo\s+observed\s+in\s+the\s+“dry”\s+membrane"
         r".{0,100}?decreases.{0,150}?new,.{0,100}?halo.{0,300}?\d+\s*◦C\.",
         "Distinguish decreased old DRY-membrane halo from the new halo/new amorphous structure; do not claim all halos shrink.",
         (r"аморф|amorph", r"сух|\bdry\b", r"нов|\bnew\b", r"гало|halo")),
    ]
    requirements, missing = [], []
    context = normal(" ".join(s.text for s in sources))
    if not has(r"li[ -]*nafion", context) or "ec/sl" not in context:
        missing.append("target_material_context_not_found")
    for key, pattern, instruction, patterns in specs:
        anchors = _role_anchors(sources, key, pattern)
        if not anchors:
            missing.append(key)
            continue
        checks = tuple(patterns)
        if key == "hold_observation":
            values = {tuple(a["groups"][k] for k in ("days", "temperature")) for a in anchors}
            if len(values) != 1:
                missing.append("ambiguous_hold_observation")
            else:
                days, temperature = next(iter(values))
                checks += (_number(days) + r"\s*(?:сут|дн|days?\b)", _number(temperature) + r"\s*°\s*c")
        requirements.append(Requirement(key, instruction, checks, anchors))
    return Contract("plasticiser_cycles_structure_qualifiers", requirements, missing)


def prepare(question: str, evidence: list[Evidence]) -> Contract | None:
    kind = family(question)
    if kind is None:
        return None
    groups: dict[str, list[Evidence]] = {}
    for source in evidence:
        if not source.source_type.endswith("_derived"):
            groups.setdefault(source.article_id, []).append(source)
    parser = _conductivity if kind == "model_layer_bulk_conductivity_conditions" else _structure
    candidates = [parser(sources) for sources in groups.values()]
    complete = [c for c in candidates if c.eligible]
    if len(complete) == 1:
        return complete[0]
    if len(complete) > 1:
        return Contract(kind, [], ["ambiguous_source_work"])
    return max(candidates, key=lambda c: len(c.requirements), default=Contract(kind, [], ["no_raw_source"]))


def instruction(contract: Contract | None) -> str:
    if contract is None:
        return ""
    return ("Source-bound answer obligations. Cover EVERY role with its correct source citation; otherwise abstain. "
            "Keep experimental roles, uncertainty and modest/strong wording exactly scoped to the source. "
            "Do not satisfy a role by denying it, listing missing data, quoting an incorrect alternative or copying instructions.\n"
            + json.dumps(contract.metadata(), ensure_ascii=False) + "\n\n")


def validate(claims: list[GeneratedClaim], contract: Contract | None) -> None:
    if contract is None:
        return
    if not contract.eligible:
        raise GenerationOutputError("Answer fidelity source pattern unresolved: " + ", ".join(contract.missing_source_roles))
    failures = []
    for requirement in contract.requirements:
        citations = {a["citation_id"] for a in requirement.anchors}
        if not any(citations.intersection(c.citation_ids) and not _denied_role(requirement.key, normal(c.text))
                   and (requirement.key != "eis_medium" or re.search(r"\d\s*M\s*LiPF[6₆]", c.text) is not None)
                   and all(has(p, normal(c.text)) for p in requirement.patterns)
                   for c in claims):
            failures.append(requirement.key)
    if contract.family == "plasticiser_cycles_structure_qualifiers":
        for claim in claims:
            for clause in re.split(r"(?<=[.!?;])\s+", normal(claim.text)):
                if (has(r"необратим|irrevers", clause) and not has(r"гипотез|hypothes|не доказан|not proven", clause)):
                    failures.append("irreversibility_overstatement")
                if (has(r"необратим|irrevers", clause) and has(r"(?<!не )\bдоказан|(?<!not )\bproven", clause)):
                    failures.append("irreversibility_overstatement")
                if has(r"\b(?:значительн\w*|резк\w*|сильн\w*|significant|substantial)\b.{0,80}?"
                       r"(?:интенсив\w*.{0,40}?кристалл|crystal.{0,40}?intensit)", clause):
                    failures.append("crystalline_intensity_overstatement")
    if failures:
        raise GenerationOutputError("Answer fidelity requirements failed: " + ", ".join(sorted(set(failures))))


def _denied_role(key: str, text: str) -> bool:
    if has(r"не (?:приведен|указан|извест|определен)|not (?:reported|specified|known)|unreported|данных нет", text):
        return True
    patterns = {
        "absolute_conductivities": r"\bне\s+10|не (?:сло|объ[её]м)|not (?:layer|bulk)",
        "gas_synthesis": r"не (?:обрабатыва|синтезир|получа)|не в\s*(?:o2|кислород)|not.{0,15}(?:treat|react|synthesi)",
        "eis_medium": r"не использова|не применя|без\s+(?:eis|lipf6)|not.{0,15}(?:use|eis)|without\s+lipf6",
        "cycle_retention": r"не сохраня|not retain|not preserv",
        "alternative_interpretations": r"исключен|отвергнут|ruled out|rejected",
        "irreversibility_hypothesis": r"не поддержива|не подтвержда|отвергнут|not supported|rejected",
        "slight_crystalline_intensity": r"не явля.{0,15}незначитель|not slight|not small",
        "preserved_crystalline_regions": r"не оста.{0,30}неизмен|не сохраня|not.{0,20}unchanged",
        "old_and_new_amorphous_halos": r"не появля|no new|not appear",
    }
    return has(patterns.get(key, r"(?!)"), text)
