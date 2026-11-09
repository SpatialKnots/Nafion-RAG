"""Finite source grammars and recomputable Russian renderings; no corpus IDs/gold."""

from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction
from typing import Any

from app.generation.answer_fidelity import prepare as fidelity_contract
from app.generation.fact_types import NUMBER, Fact, FactPatternError, Rendering, SourceView, Value
from app.generation.providers import Evidence
from app.generation.source_paraphrases import (
    COULOMBIC_CONCLUSION,
    COULOMBIC_VERSION,
    EIS_MEDIUM,
    GAS_SYNTHESIS,
    HOLD_OBSERVATION,
    PREFIX_GUARD,
)


def _fact(view: SourceView, match: re.Match[str], property: str, value: Value | None, unit: Value | None,
          sample: Value | None, operation: str, conditions: dict[str, Value], *, status: str = "source_reported",
          method: Value | None = None, unknown: tuple[str, ...] = ()) -> Fact:
    return Fact(property, sample, value, unit, operation, method, conditions, status, view.support(match), unknown)


def _ratio(left: Value, right: Value) -> tuple[str, dict[str, Any]]:
    numerator, denominator = Decimal(left.text), Decimal(right.text)
    if denominator <= 0 or numerator < 0:
        raise FactPatternError("invalid_ratio_operands")
    exact = Fraction(numerator) / Fraction(denominator)
    rounded = (numerator / denominator).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    return format(rounded, "f"), {"origin": "system_arithmetic", "operation": "ratio", "numerator": left.text,
        "denominator": right.text, "exact_fraction": str(exact), "display_value": str(rounded),
        "rounding": "one_decimal_half_up", "unit_conversion": False}


def composition(source: Evidence, params: dict[str, str]) -> Rendering:
    v = SourceView(source)
    base = v.one(rf"(?P<concentration>{NUMBER}) (?P<unit>M) (?P<salt>Li[A-Za-z0-9]+) in "
                 rf"(?P<solvents>[A-Za-z0-9/, -]+) \((?P<ratio>\d+:\d+:\d+) by (?P<basis>volume)\)")
    addition = v.one(rf"added (?P<concentration>{NUMBER}) (?P<unit>M) (?P<salt>lithium [A-Za-z() -]+) "
                     r"as a (?P<method>film-?forming additive)")
    total = v.one(rf"new bifunctional electrolyte of (?P<concentration>{NUMBER}) (?P<unit>M)")
    a, b, t = (v.value(m, "concentration") for m in (base, addition, total))
    if Decimal(a.text) + Decimal(b.text) != Decimal(t.text):
        raise FactPatternError("reported_total_inconsistent_with_components")
    sample = v.value(base, "solvents")
    facts = (_fact(v, base, "base_salt_concentration", a, v.value(base, "unit"), sample, "electrolyte_composition",
                   {"salt": v.value(base, "salt"), "solvent_ratio": v.value(base, "ratio"), "ratio_basis": v.value(base, "basis")}),
             _fact(v, addition, "additive_concentration", b, v.value(addition, "unit"), sample, "electrolyte_composition",
                   {"salt": v.value(addition, "salt")}, method=v.value(addition, "method")),
             _fact(v, total, "reported_solution_concentration", t, v.value(total, "unit"), sample, "electrolyte_composition", {}))
    solvents = sample.text.replace("dimethyl carbonate", "диметилкарбонат")
    additive = {"lithium difluoro(oxalato)borate": "дифтороксалатоборат лития"}.get(addition["salt"], addition["salt"])
    text = (f"Электролит содержит {a.text} M {base['salt']} в смеси {solvents} "
            f"в соотношении {base['ratio']} по объёму и добавку «{additive}» с концентрацией {b.text} M. "
            f"Добавка названа плёнкообразующей. Суммарная концентрация этих двух солей — {t.text} M "
            f"(расчёт системы: {a.text} + {b.text}; совпадает с приведённой в источнике концентрацией раствора).")
    return Rendering(facts, text, {"origin": "system_arithmetic", "operation": "sum", "operands": [a.text, b.text],
                                   "result": t.text, "unit": base["unit"], "unit_conversion": False})


def capacity(source: Evidence, params: dict[str, str]) -> Rendering:
    v = SourceView(source)
    m = v.one(rf"(?P<cell>Li\|\|[A-Za-z0-9]+) batteries to maintain (?P<qualifier>nearly|about) "
              rf"(?P<retention>{NUMBER})(?P<percent>%) capacity after (?P<cycles>\d+) (?P<cycle_unit>cycles) "
              rf"when charged to (?P<voltage>{NUMBER}) (?P<voltage_unit>V) under the current density of "
              rf"(?P<current>{NUMBER}) (?P<current_unit>mA g[−–-]1)")
    conditions = {key: v.value(m, key) for key in ("cycles", "cycle_unit", "voltage", "voltage_unit", "current", "current_unit")}
    f = _fact(v, m, "capacity_retention", v.value(m, "retention"), v.value(m, "percent"), v.value(m, "cell"),
              "electrochemical_cycling", conditions, status="source_reported_approximate")
    return Rendering((f,), f"В ячейках {m['cell']} сохранено около {m['retention']}% ёмкости после {m['cycles']} циклов "
                           f"при зарядке до {m['voltage']} V и токе {m['current']} {m['current_unit']}.")


def coulombic(source: Evidence, params: dict[str, str]) -> Rendering:
    v = SourceView(source)
    legacy = (rf"(?P<cell>Li\|\|[A-Za-z0-9]+) half-cells maintain (?P<qualifier>about|nearly) "
              rf"(?P<efficiency>{NUMBER})(?P<percent>%) coulombic efficiency after being charged/discharged "
              rf"(?P<cycles>\d+) (?P<cycle_unit>times) under (?P<current>{NUMBER}) (?P<current_unit>mA cm[−–-]2) "
              rf"current density and (?P<capacity>{NUMBER}) (?P<capacity_unit>mAh cm[−–-]2) lithium deposition amount per cycle")
    candidates: list[tuple[re.Match[str], str | None]] = [(m, None) for m in re.finditer(legacy, v.text)]
    for match in re.finditer(COULOMBIC_CONCLUSION, v.text):
        prefix = re.split(r"[.!?]\s+", v.text[max(0, match.start() - 160):match.start()])[-1]
        if not re.search(PREFIX_GUARD, prefix, re.I):
            candidates.append((match, COULOMBIC_VERSION))
    if not candidates or len({m.group() for m, _ in candidates}) != 1:
        raise FactPatternError("missing_or_ambiguous_source_pattern")
    m, grammar = candidates[0]
    f = _fact(v, m, "coulombic_efficiency", v.value(m, "efficiency"), v.value(m, "percent"), v.value(m, "cell"),
              "electrochemical_cycling", {key: v.value(m, key) for key in
                  ("cycles", "cycle_unit", "current", "current_unit", "capacity", "capacity_unit")},
              status="source_reported_approximate",
              unknown=("measurement_temperature", "electrolyte_composition_in_this_clause") if grammar else ())
    return Rendering((f,), f"Для {m['cell']} кулоновская эффективность составляет около {m['efficiency']}% после "
                           f"{m['cycles']} циклов при {m['current']} {m['current_unit']} и осаждении лития "
                           f"{m['capacity']} {m['capacity_unit']} за цикл. Это другой показатель, чем сохранение ёмкости.",
                     grammar=grammar)


def dispersion_method(source: Evidence, params: dict[str, str]) -> Rendering:
    v = SourceView(source)
    m = v.one(rf"(?P<grade>Nafion[-‐‑]\d+) membrane, .{{0,100}}?autoclave containing a "
              rf"(?P<ratio>\d+/\d+) mixture of (?P<solvents>water and ethanol), and heated at "
              rf"(?P<temperature>{NUMBER}) (?P<t_unit>K) for (?P<duration>\d+|one|two|three|four|five|six|seven|eight|nine|ten) "
              r"(?P<d_unit>hours?)\. .{0,100}?\((?P<initial>[a-z]\d+) sample\)")
    step = v.one(r"Ethanol-free Nafion dispersion was prepared from the (?P<initial>[a-z]\d+) sample by "
                 r"(?P<method>semi-batch continuous azeotropic distillation) at (?P<volume>constant volume)\. "
                 r".{0,100}?without ethanol was obtained \((?P<product>[a-z]\d+) sample\)")
    if m["initial"] != step["initial"] or step["product"] != params["product"] or m["grade"] != params["grade"]:
        raise FactPatternError("dispersion_step_sample_binding_mismatch")
    first = _fact(v, m, "starting_dispersion_preparation", v.value(m, "initial"), None, v.value(m, "grade"), "autoclave_preparation",
                  {key: v.value(m, key, word_number=key == "duration")
                   for key in ("ratio", "solvents", "temperature", "t_unit", "duration", "d_unit")},
                  unknown=("water_ethanol_ratio_basis",))
    second = _fact(v, step, "ethanol_free_dispersion_preparation", v.value(step, "product"), None,
                   v.value(step, "initial"), "solvent_removal", {"volume": v.value(step, "volume")},
                   method=v.value(step, "method"))
    duration = {"one": "одного", "two": "двух", "three": "трёх", "four": "четырёх", "five": "пяти", "six": "шести",
                "seven": "семи", "eight": "восьми", "nine": "девяти", "ten": "десяти"}.get(m["duration"], m["duration"])
    text = (f"Дисперсию {step['product']} получают через промежуточную дисперсию {m['initial']}: {m['grade']} "
            f"обрабатывают в автоклаве в смеси воды и этанола {m['ratio']} при {m['temperature']} K "
            f"в течение {duration} часов. Затем этанол удаляют полунепрерывной азеотропной дистилляцией "
            f"при постоянном объёме. Это удаление этанола из {m['initial']}, а не прямое растворение мембраны в чистой воде. "
            "Основа соотношения воды и этанола в этом предложении источника не указана.")
    return Rendering((first, second), text)


def casting(source: Evidence, params: dict[str, str]) -> Rendering:
    v = SourceView(source)
    m = v.one(rf"Recast membrane without using organic solvents .{{0,70}}?was obtained from the "
              rf"(?P<sample>[a-z]\d+) dispersion on a (?P<substrate>glass plate), evaporating the water at "
              rf"(?P<temperature>{NUMBER}) (?P<unit>K)")
    if m["sample"] != params["product"]:
        raise FactPatternError("casting_sample_mismatch")
    f = _fact(v, m, "film_casting_temperature", v.value(m, "temperature"), v.value(m, "unit"), v.value(m, "sample"),
              "film_casting", {"substrate": v.value(m, "substrate")}, unknown=("casting_duration",))
    return Rendering((f,), f"Из {m['sample']} получают мембрану на стеклянной подложке, испаряя воду при "
                           f"{m['temperature']} K. Эта температура относится к изготовлению мембраны.")


def conductivity_table(source: Evidence, params: dict[str, str]) -> Rendering:
    v = SourceView(source)
    header = v.one(r"Tab\.\s*\d+\. EIS analysis\. Sample Conductivity [— -]+ (?P<unit>S (?:N |[·⋅] ?)?cm[−–-]1) "
                   r"Water content [— -]+ (?P<water_unit>wt\.-%)")
    rows: dict[str, tuple[Value, Value, Value, re.Match[str]]] = {}
    for label in (params["product"], params["comparator"]):
        m = v.one(rf"(?<![A-Za-z0-9])(?:Sample )?(?P<sample>{re.escape(label)})(?:a\))? "
                  rf"(?P<conductivity>{NUMBER}) (?P<water>{NUMBER})(?![.\d])")
        rows[label] = (v.value(m, "conductivity"), v.value(m, "water"), v.value(m, "sample"), m)
    product, reference = rows[params["product"]], rows[params["comparator"]]
    unit, water_unit = v.value(header, "unit"), v.value(header, "water_unit")
    ratio, arithmetic = _ratio(product[0], reference[0])
    facts = tuple(_fact(v, row[3], "conductivity", row[0], unit, row[2], "EIS_measurement",
                        {"water_content": row[1], "water_unit": water_unit},
                        unknown=("measurement_temperature", "ionomer_equivalent_weight", "activation_conditions",
                                 "charge_carrier_not_bound_in_table"))
                  for row in rows.values())
    ambiguous = " N " in unit.text
    unit_text = f"в единицах извлечённого заголовка «{unit.text}»" if ambiguous else unit.text
    text = (f"В таблице EIS проводимость мембраны {product[2].text} равна {product[0].text}, "
            f"а {reference[2].text} — {reference[0].text} ({unit_text}). Отношение составляет примерно {ratio} "
            f"(расчёт системы: {product[0].text}/{reference[0].text}). Содержание воды различается: "
            f"{product[1].text} и {reference[1].text} {water_unit.text} соответственно. "
            "Разницу проводимостей нельзя приписывать только удалению этанола на основании этой таблицы; "
            "температура измерения и эквивалентная масса иономера в выбранном табличном фрагменте не установлены.")
    if ambiguous:
        arithmetic["unit_status"] = "ambiguous_raw_header_preserved_no_unit_conversion"
        text += " Неоднозначный символ в обозначении единицы сохранён; точный заголовок доступен в исходной цитате."
    return Rendering(facts, text, arithmetic)


def _fidelity_view(source: Evidence, recipe: str) -> tuple[SourceView, dict[str, Any]]:
    # The established finite grammar is reused, not re-created with benchmark constants.
    question = ("single-phase Li2O bulk conductivity room temperature conditions" if recipe.startswith("oxide_") else
                "Li-Nafion EC/SL mixing temperature heating cooling structure")
    result = fidelity_contract(question, [source])
    if result is None:
        raise FactPatternError("missing_fidelity_family")
    return SourceView(source), {r.key: r for r in result.requirements}


def _role(view: SourceView, roles: dict[str, Any], key: str) -> tuple[SourceView, Any]:
    if key not in roles:
        raise FactPatternError("missing_fidelity_role_" + key)
    anchors = roles[key].anchors
    if len({a["text"] for a in anchors}) != 1:
        raise FactPatternError("ambiguous_fidelity_role_" + key)
    a = anchors[0]
    # Obtain a mapped match in the full raw parent, not an independently offset substring.
    text = SourceView(Evidence(**{**vars(view.source), "text": a["text"]})).text
    return view, view.one(re.escape(text))


def oxide_comparison(source: Evidence, params: dict[str, str]) -> Rendering:
    v, roles = _fidelity_view(source, "oxide_comparison")
    _, region = _role(v, roles, "absolute_conductivities")
    m = v.one(r"(?P<layer_sample>single-component Li2O SEI) \(~?(?P<layer>10[-−–]\d+) (?P<layer_unit>S/cm)\) "
              r"and that of (?P<bulk_sample>sintered bulk Li2O pellets) reported in "
              r"(?P<literature>literature\d*) \(~?(?P<bulk>10[-−–]\d+) (?P<bulk_unit>S/cm)\) at (?P<temperature>room temperature)")
    facts = tuple(_fact(v, m, "ionic_conductivity", v.value(m, key, power_of_ten=True), v.value(m, key + "_unit"), v.value(m, sample),
                        "conductivity_comparison", {"temperature": v.value(m, "temperature")}, status=status)
                  for key, sample, status in (("layer", "layer_sample", "source_reported"),
                                              ("bulk", "bulk_sample", "prior_literature")))
    layer = Decimal(10) ** int(re.split(r"[-−–]", m["layer"])[1])
    bulk = Decimal(10) ** int(re.split(r"[-−–]", m["bulk"])[1])
    # Both source exponents above are negative, so conductivity ratio reverses these powers.
    factor = bulk / layer
    superscript = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")
    layer_display = "10⁻" + re.split(r"[-−–]", m["layer"])[1].translate(superscript)
    bulk_display = "10⁻" + re.split(r"[-−–]", m["bulk"])[1].translate(superscript)
    text = (f"При комнатной температуре проводимость модельного слоя Li₂O составляет около {layer_display} S/cm, "
            f"а спечённого объёмного Li₂O — около {bulk_display} S/cm. Значение для объёмного материала взято "
            f"из предшествующей литературы. Слой проводит примерно в {format(factor, 'f')} раз лучше "
            "(расчёт системы из приведённых порядков величин). Это сравнение модельного слоя, а не любого реального SEI.")
    return Rendering(facts, text, {"origin": "system_arithmetic", "operation": "ratio_of_powers",
                                   "operands": [m["layer"], m["bulk"]], "result": str(factor), "unit_conversion": False})


def oxide_synthesis(source: Evidence, params: dict[str, str]) -> Rendering:
    v, roles = _fidelity_view(source, "oxide_synthesis")
    _, m = _role(v, roles, "gas_synthesis")
    if roles["gas_synthesis"].anchors[0].get("grammar_version"):
        fields = v.one(GAS_SYNTHESIS, re.I)
    else:
        fields = v.one(rf"(?P<sample>Li foils) were reacted in (?P<gas>O2 gas).{{0,100}}?from "
                   rf"(?P<low>{NUMBER}) (?P<unit>°C) to (?P<high>{NUMBER}) °C for "
                   rf"(?P<duration>{NUMBER}) (?P<d_unit>hours?)")
    f = _fact(v, fields, "layer_synthesis", None, None, v.value(fields, "sample"), "gas_synthesis",
              {key: v.value(fields, key) for key in ("gas", "low", "unit", "high", "duration", "d_unit")})
    return Rendering((f,), f"Модельный слой получают обработкой литиевой фольги газообразным кислородом "
                           f"при {fields['low']}–{fields['high']} °C в течение {fields['duration']} ч. "
                           "Этот диапазон относится к синтезу слоя, а не к температуре сравнения проводимости.")


def oxide_eis(source: Evidence, params: dict[str, str]) -> Rendering:
    v, roles = _fidelity_view(source, "oxide_eis")
    _role(v, roles, "eis_medium")
    if roles["eis_medium"].anchors[0].get("grammar_version"):
        medium = v.one(EIS_MEDIUM, re.I)
    else:
        medium = v.one(rf"electrolyte \((?P<concentration>{NUMBER}) (?P<unit>M) (?P<salt>LiPF6) in "
                   r"(?P<solvents>EC/DEC), (?P<basis>v/v) = (?P<ratio>\d+/\d+),[^)]+\)")
    method = v.one(r"(?P<method>EIS measurements) were conducted")
    sample = v.one(r"(?P<sample>Symmetric Li-Li cells)")
    f = _fact(v, medium, "eis_electrolyte_concentration", v.value(medium, "concentration"), v.value(medium, "unit"),
              v.value(sample, "sample"), "EIS_measurement", {key: v.value(medium, key) for key in
                  ("salt", "solvents", "basis", "ratio")}, method=v.value(method, "method"),
              unknown=("EIS_measurement_temperature_in_this_clause",))
    return Rendering((f,), f"EIS проводили в симметричных Li‖Li ячейках с электролитом {medium['concentration']} M "
                           f"{medium['salt']} в EC/DEC {medium['ratio'].replace('/', ':')} по объёму. "
                           "Температуру получения слоя не следует переносить на эти измерения.")


def thermal_cycles(source: Evidence, params: dict[str, str]) -> Rendering:
    v, roles = _fidelity_view(source, "thermal_cycles")
    _, m = _role(v, roles, "cycle_retention")
    f = _fact(v, m, "heating_cooling_solvent_uptake", None, None, None, "thermal_swelling_cycle", {},
              unknown=("sample_grade_not_bound_in_this_passage",))
    return Rendering((f,), "При повышении температуры смешения поглощение пластификатора увеличивается. "
                           "При последующем охлаждении достигнутое поглощение практически сохраняется: "
                           "наблюдается гистерезис, а не исчезновение поглощённого растворителя.")


def hold_interpretation(source: Evidence, params: dict[str, str]) -> Rendering:
    v, roles = _fidelity_view(source, "hold_interpretation")
    _, hold = _role(v, roles, "hold_observation")
    _, alternatives = _role(v, roles, "alternative_interpretations")
    _, hypothesis = _role(v, roles, "irreversibility_hypothesis")
    if roles["hold_observation"].anchors[0].get("grammar_version"):
        m = v.one(HOLD_OBSERVATION, re.I)
    else:
        m = v.one(rf"long-term \((?P<days>{NUMBER}) (?P<d_unit>days)\) isothermal treatment was carried out at "
                  rf"(?P<temperature>{NUMBER}) (?P<t_unit>◦C)")
    observed = _fact(v, m, "isothermal_hold_duration", v.value(m, "days"), v.value(m, "d_unit"), None,
                     "post_cooling_hold", {"temperature": v.value(m, "temperature"), "unit": v.value(m, "t_unit")})
    meaning = _fact(v, hypothesis, "irreversible_rearrangement", None, None, None, "interpretation", {}, status="hypothesis")
    choices = _fact(v, alternatives, "equilibrium_or_slow_syneresis", None, None, None, "interpretation", {},
                    status="alternative_interpretations")
    return Rendering((observed, meaning, choices),
        f"Выдержка {m['days']} суток при {m['temperature']} °C после охлаждения не изменила поглощение. "
        "Возможны либо близость к равновесию, либо очень медленный синерезис. "
        "Гистерезис поддерживает гипотезу необратимой перестройки; необратимость не доказана.")


def crystals(source: Evidence, params: dict[str, str]) -> Rendering:
    v, roles = _fidelity_view(source, "crystals")
    _, intensity = _role(v, roles, "slight_crystalline_intensity")
    _, preservation = _role(v, roles, "preserved_crystalline_regions")
    facts = tuple(_fact(v, m, key, None, None, None, "structure_observation", {},
                        unknown=("sample_grade_not_bound_in_this_passage",))
                  for m, key in ((intensity, "slight_crystalline_intensity_reduction"),
                                 (preservation, "nearly_unchanged_crystalline_regions")))
    return Rendering(facts, "Кристаллические области остаются практически неизменными в исследованном диапазоне. "
                            "Интенсивность кристаллического рефлекса снижается лишь немного; "
                            "это не означает разрушения кристаллических областей.")


def amorphous(source: Evidence, params: dict[str, str]) -> Rendering:
    v, roles = _fidelity_view(source, "amorphous")
    _, m = _role(v, roles, "old_and_new_amorphous_halos")
    f = _fact(v, m, "old_and_new_amorphous_halos", None, None, None, "structure_observation", {},
              unknown=("sample_grade_not_bound_in_this_passage",))
    return Rendering((f,), "Реорганизация затрагивает аморфные области: вклад прежнего гало сухой мембраны уменьшается, "
                           "а новое аморфное гало появляется и усиливается. Эти два вклада нельзя объединять "
                           "в утверждение об уменьшении всей аморфной составляющей.")


RECIPES = {"composition": composition, "capacity": capacity, "coulombic": coulombic,
           "dispersion_method": dispersion_method, "casting": casting, "conductivity_table": conductivity_table,
           "oxide_comparison": oxide_comparison, "oxide_synthesis": oxide_synthesis, "oxide_eis": oxide_eis,
           "thermal_cycles": thermal_cycles, "hold_interpretation": hold_interpretation,
           "crystals": crystals, "amorphous": amorphous}
