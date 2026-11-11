"""Finite complete-answer source contracts; never general chemical or epistemic validation."""

from __future__ import annotations

import re
import unicodedata
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from typing import Any

from app.generation.fact_types import Fact, FactPatternError, SourceView
from app.generation.providers import Evidence
from app.generation.reviewed_glyphs import ReviewedGlyphView

KINDS = {"solvent_reaction_comparison", "capacity_film_status", "electrolyte_formulations"}
NUMBER = r"\d+(?:\.\d+)?"
SIGNED = rf"[−-]?{NUMBER}"
CODE = r"[A-Z][A-Za-z0-9]{0,24}"
ION = r"[A-Z][a-z]?\s*\+"
MU = rf"[μµ]{ION}"
ENERGY = r"kJ mol[−-]1"
RATIO = rf"{NUMBER}/{NUMBER}"
CAPACITY = r"mA\s*h\s*g[−-]1"
CAPACITY_GLYPHS = (Path(__file__).resolve().parents[1] / "resources/reviewed_capacity_film_glyph_aliases_v01.json",
                   "c7e4e7894169ddccf35784ae328749f6c0c70226857e59d1c3d017d98505ee6a")
FORMULATION_GLYPHS = (Path(__file__).resolve().parents[1] / "resources/reviewed_formulation_identity_glyph_aliases_v01.json",
                      "7d2e644ff571a0ccea7ebf79d87151fa293c99cf0ad5aa0746c00a46c818e4fa")
QUERIES = {
    "solvent_reaction_comparison": re.compile(
        rf"Какие значения (?P<symbol>{MU}) получены для (?P<salt1>{CODE})/(?P<s1>{CODE}), "
        rf"(?P<salt2>{CODE})/(?P<s2>{CODE}) и (?P<salt3>{CODE})/(?P<s3>{CODE}) при мольном соотношении "
        rf"соль/растворитель (?P<ratio>{RATIO}), и какие реакции происходят на графите\?", re.I),
    "capacity_film_status": re.compile(
        rf"Какую разрядную [её]мкость продемонстрировала система (?P<base>{CODE})[–−-](?P<solvent>{CODE}) "
        rf"на (?P<cycle>\d+)-м цикле и подтвержд[её]н ли химический состав е[её] защитной пл[её]нки\?", re.I),
    "electrolyte_formulations": re.compile(
        rf"Каков состав электролитов (?P<label1>{CODE}), (?P<label2>{CODE}), (?P<label3>{CODE}) и (?P<label4>{CODE}) "
        r"и чем отличаются способы задания соотношений компонентов\?", re.I),
}
REACTION_FRAME = re.compile(
    rf"Here, we focus on the reactions of graphite in (?P<salt>{CODE}) electrolytes "
    rf"\((?P<basis_salt>{CODE})/solvent = (?P<ratio>{RATIO}) by mol\) with different solvation abilities and (?P<symbol>{MU}) "
    rf"values, namely, (?P<s1>{CODE}) \((?P<mu1>{SIGNED}) (?P<unit1>{ENERGY})\), "
    rf"(?P<s2>{CODE}) \((?P<mu2>{SIGNED}) (?P<unit2>{ENERGY})\), and "
    rf"(?P<s3>{CODE}) \((?P<mu3>{SIGNED}) (?P<unit3>{ENERGY})\) \(Figure (?P<figure>\d+)\)\.")
COINTERCALATION = re.compile(
    rf"in strongly solvating (?P<solvent>{CODE}) with low (?P<symbol>{MU}) \((?P<mu>{SIGNED}) (?P<unit>{ENERGY})\)\. "
    rf"This reaction corresponds to (?P<reaction>(?P<ion>{ION})[–−-]solvent cointercalation) forming "
    rf"(?P<gic>(?P<metal>[A-Z][a-z]?)[–−-]solvent[–−-]graphite intercalation compounds) \(GICs\) with an "
    rf"interlayer distance of (?P<distance>{NUMBER}) (?P<distance_unit>nm)")
INTERCALATION = re.compile(
    rf"In contrast, in weakly solvating (?P<solvent>{CODE}) with high (?P<symbol>{MU}) "
    rf"\((?P<mu>{SIGNED}) (?P<unit>{ENERGY})\), voltage plateaus were observed in the range of "
    rf"(?P<low>{NUMBER})[–−-](?P<high>{NUMBER}) V, with a reversible capacity of (?P<bound>over) "
    rf"(?P<capacity>{NUMBER}) (?P<capacity_unit>mAh g[−-]1)\. This reaction corresponds to "
    rf"(?P<reaction>(?P<ion>{ION}) intercalation) forming (?P<metal>[A-Z][a-z]?)-GIC (?P<gic>{CODE})")
PARTIAL_INTERCALATION = re.compile(
    rf"In moderately solvating (?P<solvent>{CODE}) with intermediate (?P<symbol>{MU}) "
    rf"\((?P<mu>{SIGNED}) (?P<unit>{ENERGY})\), we observed (?P<reaction>(?P<ion>{ION}) intercalation), "
    rf"but the reversible capacity was (?P<capacity_status>much lower) because of the "
    rf"(?P<limitation>incomplete inhibition of (?P<coion>{ION})[–−-]\s*solvent cointercalation)\.")
CAPACITY_RESULT = re.compile(
    rf"The discharge capacity is expressed on the basis of the (?P<basis>mass of (?P<cathode>{CODE}) as a cathode)\. "
    rf"The discharge capacity in the (?P<system>(?P<base>{CODE})[–−-](?P<solvent>{CODE})) system "
    rf"was (?P<qualifier>as high as) (?P<capacity>{NUMBER}) (?P<unit>{CAPACITY}) even at the (?P<cycle>\d+)th cycle\.")
POSSIBLE_FILM = re.compile(
    rf"The cathodic decomposition of the (?P<solvent>{CODE})-based solution on a (?P<electrode>lithium anode) "
    r"(?P<modal>can form) (?P<film>passive thin films) containing (?P<contents>adequate amounts of "
    r"organofluorine compounds such as fluorinated alkoxides)\.")
COMPONENT_NAMES = re.compile(
    rf"Battery-grade (?P<ec_name>ethylene carbonate) \((?P<ec>{CODE})\), "
    rf"(?P<emc_name>ethyl methyl carbonate) \((?P<emc>{CODE})\), "
    rf"(?P<fec_name>fluoroethylene carbonate) \((?P<fec>{CODE})\), "
    rf"(?P<femc_name>2,2,2-trifluoroethyl methyl carbonate) \((?P<femc>{CODE})\) and "
    r"(?P<salt_name>lithium hexafluorophosphate) \((?P<salt>LiPF6)\)")
ETHER_NAME = re.compile(
    rf"(?P<tfee_name>1,2-Bis\(1,1,2,2-tetrafluoroethoxy\) ethane) \((?P<tfee>{CODE}), (?P<purity>{NUMBER})%\)")
FORMULATIONS = re.compile(
    rf"The base electrolyte was (?P<c1>{NUMBER}) (?P<u1>M) (?P<salt1>{CODE}) dissolved in "
    rf"(?P<components1>(?P<a1>{CODE})/(?P<b1>{CODE})) at (?P<ratio1>{RATIO}) ratio "
    rf"(?P<basis1>by volume) \(marked as (?P<label1>{CODE})\)\. Three investigative electrolytes were prepared as follows: "
    rf"(?P<label2>{CODE}): (?P<c2>{NUMBER}) (?P<u2>M) (?P<salt2>{CODE}) dissolved in "
    rf"(?P<components2>(?P<a2>{CODE})/(?P<b2>{CODE})/(?P<d2>{CODE})) at (?P<ratio2>{RATIO}/{NUMBER}) ratio "
    rf"(?P<basis2>by weight)\. (?P<label3>{CODE}): (?P<c3>{NUMBER}) (?P<u3>M) (?P<salt3>{CODE}) dissolved in "
    rf"(?P<components3>(?P<a3>{CODE})/(?P<b3>{CODE})/(?P<d3>{CODE})) at (?P<ratio3>{RATIO}/{NUMBER}) ratio "
    rf"(?P<basis3>by weight)\. (?P<label4>{CODE}): (?P<c4>{NUMBER}) (?P<u4>M) (?P<salt4>{CODE}) dissolved in "
    rf"(?P<components4>(?P<a4>{CODE})/(?P<b4>{CODE})/(?P<d4>{CODE})) at (?P<ratio4>{RATIO}/{NUMBER}) ratio "
    rf"(?P<basis4>by weight)\.")


def family(question: str) -> str | None:
    q = unicodedata.normalize("NFKC", question).casefold()
    if "значения" in q and "какие реакции происходят на графите" in q and re.search(MU, q, re.I):
        return "solvent_reaction_comparison"
    if "разрядную" in q and "химический состав" in q and re.search(r"пл[её]нки", q):
        return "capacity_film_status"
    if "состав электролитов" in q and "способы задания соотношений компонентов" in q:
        return "electrolyte_formulations"
    return None


def query(body: str, kind: str) -> dict[str, Any]:
    m = QUERIES[kind].fullmatch(body.strip())
    if m is None:
        raise FactPatternError("complete_answer_query_scope_not_supported")
    params = m.groupdict()
    if kind == "solvent_reaction_comparison":
        if len({params["salt" + i] for i in ("1", "2", "3")}) != 1 or len({params["s" + i] for i in ("1", "2", "3")}) != 3:
            raise FactPatternError("one_salt_three_unique_solvents_required")
        positive_ratio(params["ratio"])
    elif kind == "capacity_film_status" and int(params["cycle"]) < 1:
        raise FactPatternError("positive_cycle_required")
    elif kind == "electrolyte_formulations" and len(set(params.values())) != 4:
        raise FactPatternError("four_unique_formulation_labels_required")
    return params


def positive_ratio(value: str) -> Fraction:
    parts = [Decimal(n) for n in value.split("/")]
    if len(parts) != 2 or any(n <= 0 for n in parts):
        raise FactPatternError("positive_molar_ratio_required")
    return Fraction(parts[0]) / Fraction(parts[1])


def compact(value: str) -> str:
    return re.sub(r"\s+", "", value).replace("µ", "μ")


def view(source: Evidence, kind: str) -> SourceView:
    if kind == "capacity_film_status":
        return ReviewedGlyphView(source, catalogue_binding=CAPACITY_GLYPHS)
    if kind == "electrolyte_formulations":
        return ReviewedGlyphView(source, catalogue_binding=FORMULATION_GLYPHS)
    return SourceView(source, join_soft_hyphen_lines=True)


def current(v: SourceView, m: re.Match[str], *, modal: str | None = None) -> bool:
    refs = re.search(r"(?im)^\s*(?:references|bibliography)\s*$", v.source.text)
    if refs and v.support(m).start >= refs.start():
        return False
    lead = re.split(r"[.!?;]\s+", v.text[max(0, m.start() - 200):m.start()])[-1]
    status = m.group()
    if modal:
        status = status.replace(modal, "bound_author_possibility")
    return re.search(r"\b(?:previous\w*|prior|earlier|hypothetical|unmeasured|literature|references|bibliography|"
                     r"future|expected|proposed|assumed|cannot|not|never|without|may|might|could|no)\b", lead + status, re.I) is None


def parse(source: Evidence, kind: str, params: dict[str, Any]) -> list[tuple[list[Fact], str]]:
    v = view(source, kind)
    patterns = {"solvent_reaction_comparison": (REACTION_FRAME, COINTERCALATION, INTERCALATION, PARTIAL_INTERCALATION),
                "capacity_film_status": (CAPACITY_RESULT, POSSIBLE_FILM),
                "electrolyte_formulations": (COMPONENT_NAMES, ETHER_NAME, FORMULATIONS)}[kind]
    matches = [list(p.finditer(v.text)) for p in patterns]
    if any(len(rows) > 1 for rows in matches):
        raise FactPatternError("ambiguous_complete_answer_source_frames")
    if not all(matches):
        return []
    selected = [rows[0] for rows in matches]
    for m in selected:
        modal = m["modal"] if kind == "capacity_film_status" and "modal" in m.groupdict() else None
        if not current(v, m, modal=modal):
            return []
    if any(left.end() > right.start() for left, right in zip(selected, selected[1:], strict=False)):
        raise FactPatternError("complete_source_frames_out_of_order")
    if re.search(r"(?:^|\s)(?:\d+\.\d+|\d+\.)\s+[A-Z][A-Za-z]+", v.text[selected[0].end():selected[-1].start()]):
        raise FactPatternError("complete_source_frames_cross_section_boundary")
    if kind == "solvent_reaction_comparison":
        return [reactions(v, selected[0], selected[1], selected[2], selected[3], params=params)]
    if kind == "capacity_film_status":
        return [film(v, selected[0], selected[1], params=params)]
    return [formulations(v, selected[0], selected[1], selected[2], params=params)]


def reactions(v: SourceView, frame: re.Match[str], co: re.Match[str], inter: re.Match[str], partial: re.Match[str],
              *, params: dict[str, Any]) -> tuple[list[Fact], str]:
    symbol = compact(params["symbol"])
    ion = symbol[1:]
    solvents = [frame["s" + i] for i in ("1", "2", "3")]
    if (frame["salt"] != params["salt1"] or frame["salt"] != frame["basis_salt"]
            or not frame["salt"].startswith(ion[:-1]) or len(set(solvents)) != 3
            or set(solvents) != {params["s" + i] for i in ("1", "2", "3")}
            or positive_ratio(frame["ratio"]) != positive_ratio(params["ratio"])
            or any(compact(m["symbol"]) != symbol for m in (frame, co, inter, partial))
            or any(compact(m["ion"]) != ion for m in (co, inter, partial)) or compact(partial["coion"]) != ion
            or co["metal"] != ion[:-1] or inter["metal"] != ion[:-1] or not inter["gic"].startswith(ion[:-1] + "C")):
        raise FactPatternError("reaction_frame_identity_ion_or_molar_ratio_mismatch")
    observations = {co["solvent"]: co, inter["solvent"]: inter, partial["solvent"]: partial}
    if len(observations) != 3 or set(observations) != set(solvents):
        raise FactPatternError("reaction_membership_or_unique_solvent_binding_mismatch")
    facts = []
    summaries = []
    for solvent in (params["s1"], params["s2"], params["s3"]):
        m = observations[solvent]
        index = str(solvents.index(solvent) + 1)
        if Decimal(m["mu"].replace("−", "-")) != Decimal(frame["mu" + index].replace("−", "-")):
            raise FactPatternError("reaction_mu_owner_or_value_mismatch")
        conditions = {"salt": v.value(frame, "salt"), "salt_solvent_molar_ratio": v.value(frame, "ratio"),
                      "symbol": v.value(frame, "symbol"), "reaction": v.value(m, "reaction")}
        if m is co:
            conditions["intercalate_identity"] = v.value(co, "gic")
            description = "совместная интеркаляция иона с растворителем с образованием соединений ион–растворитель–графит"
        elif m is partial:
            conditions.update(capacity_comparison=v.value(m, "capacity_status"), incomplete_suppression=v.value(m, "limitation"))
            description = ("интеркаляция иона с существенно меньшей обратимой ёмкостью; авторы связывают это "
                           "с неполным подавлением совместной интеркаляции иона с растворителем")
        else:
            conditions["intercalate_identity"] = v.value(inter, "gic")
            description = "интеркаляция иона с образованием " + inter["gic"]
        facts.append(Fact("solvent_specific_mu_and_graphite_reaction", v.value(m, "solvent"), v.value(m, "mu"),
            v.value(m, "unit"), "source_reported_comparison", None, conditions, "source_reported_reaction", v.support(m),
            ("measurement_temperature", "measurement_uncertainty")))
        summaries.append(f"{frame['salt']}/{solvent}: {symbol} = {m['mu']} {m['unit']}; {description}.")
    text = f"При мольном отношении соль/растворитель {frame['ratio']} авторы сообщают: " + " ".join(summaries)
    return facts, text


def film(v: SourceView, capacity: re.Match[str], possible: re.Match[str], *, params: dict[str, Any]) -> tuple[list[Fact], str]:
    if (capacity["base"] != params["base"] or capacity["solvent"] != params["solvent"]
            or possible["solvent"] != params["solvent"] or int(capacity["cycle"]) != int(params["cycle"])):
        raise FactPatternError("capacity_cycle_or_possible_film_solvent_mismatch")
    facts = [Fact("cycle_discharge_capacity", v.value(capacity, "system"), v.value(capacity, "capacity"),
        v.value(capacity, "unit"), "source_reported_capacity", None,
        {"cycle": v.value(capacity, "cycle"), "normalization": v.value(capacity, "basis"),
         "source_qualifier": v.value(capacity, "qualifier")}, "source_reported_quantity", v.support(capacity)),
        Fact("possible_passive_film_composition", v.value(possible, "solvent"), v.value(possible, "contents"), None,
             "source_author_possible_composition_not_identification", None,
             {"modality": v.value(possible, "modal"), "electrode": v.value(possible, "electrode"),
              "film": v.value(possible, "film")}, "source_author_possibility", v.support(possible),
             ("experimentally_identified_film_composition", "composition_characterization_method", "film_thickness"))]
    text = (f"Для системы {capacity['system']} авторы сообщают разрядную ёмкость {capacity['capacity']} "
        f"{capacity['unit']} на {capacity['cycle']}-м цикле, в расчёте на массу {capacity['cathode']} катода. "
        f"Состав плёнки в приведённом тексте дан как возможное объяснение: разложение раствора на основе "
        f"{possible['solvent']} на литиевом аноде может образовать пассивные тонкие плёнки с органофторсодержащими "
        'соединениями, например фторированными алкоксидами. Это авторское «can form», а не подтверждённая '
        'химическая идентификация. По этому фрагменту нельзя утверждать, что состав плёнки установлен; '
        'это также не доказывает отсутствие любых исследований состава во всей статье.')
    return facts, text


def formulations(v: SourceView, names: re.Match[str], ether: re.Match[str], forms: re.Match[str],
                 *, params: dict[str, Any]) -> tuple[list[Fact], str]:
    labels = [forms["label" + i] for i in ("1", "2", "3", "4")]
    if (len(set(labels)) != 4 or set(labels) != set(params.values())
            or len({names[k] for k in ("ec", "emc", "fec", "femc", "salt")} | {ether["tfee"]}) != 6
            or any(forms["salt" + i] != names["salt"] for i in ("1", "2", "3", "4"))
            or (forms["a1"], forms["b1"]) != (names["ec"], names["emc"])
            or (forms["a2"], forms["b2"], forms["d2"]) != (names["ec"], names["emc"], ether["tfee"])
            or (forms["a3"], forms["b3"], forms["d3"]) != (names["fec"], names["emc"], ether["tfee"])
            or (forms["a4"], forms["b4"], forms["d4"]) != (names["fec"], names["femc"], ether["tfee"])):
        raise FactPatternError("formulation_label_salt_or_component_identity_mismatch")
    facts, summaries = [], []
    for label in params.values():
        i = str(labels.index(label) + 1)
        if Decimal(forms["c" + i]) <= 0 or any(Decimal(n) <= 0 for n in forms["ratio" + i].split("/")):
            raise FactPatternError("positive_formulation_concentration_and_component_ratios_required")
        facts.append(Fact("electrolyte_formulation", v.value(forms, "label" + i), v.value(forms, "components" + i), None,
            "source_declared_formulation", None, {key: v.value(forms, field + i) for key, field in
             (("salt", "salt"), ("salt_concentration", "c"), ("concentration_unit", "u"),
              ("component_ratio", "ratio"), ("ratio_basis", "basis"))}, "source_declared_composition", v.support(forms),
             ("preparation_temperature",)))
        basis = "по объёму" if forms["basis" + i] == "by volume" else "по массе"
        summaries.append(f"{label}: {forms['c' + i]} {forms['u' + i]} {forms['salt' + i]} в "
                         f"{forms['components' + i]}, {forms['ratio' + i]} {basis}.")
    identity_text = []
    for match, keys in ((names, ("ec", "emc", "fec", "femc", "salt")), (ether, ("tfee",))):
        for key in keys:
            facts.append(Fact("source_declared_component_identity", v.value(match, key), v.value(match, key + "_name"), None,
                "literal_source_name_alias_binding_not_general_structure_validation", None, {},
                "source_declared_identity", v.support(match)))
            identity_text.append(match[key] + " — " + match[key + "_name"])
    return facts, " ".join(summaries) + " Названия компонентов как в источнике: " + "; ".join(identity_text) + "."


def metadata(source: Evidence, kind: str) -> dict[str, Any]:
    v = view(source, kind)
    result: dict[str, Any] = {"completeness_policy": "finite_complete_answer_source_binding_v0.1", "query_scope": kind,
                              "claim_kind": "complete_source_reported_answer_not_independent_scientific_acceptance"}
    if isinstance(v, ReviewedGlyphView):
        result["glyph_decoding"] = v.provenance()
    return result
