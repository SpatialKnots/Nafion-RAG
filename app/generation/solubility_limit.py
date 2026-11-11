"""Finite source-bound solvent identity and below-comparison-concentration limitation."""
from __future__ import annotations

import re
from decimal import Decimal

from app.generation import conductivity_order as order
from app.generation.fact_types import Fact, FactPatternError, SourceView

# Reuse the existing exact-source catalogue; no new glyph interpretation.
GLYPHS = order.GLYPH_CATALOGUE
QUERY = re.compile(rf'Почему в сравнении проводимости авторы не приводят '
    rf'(?P<concentration>{order.NUMBER}) (?P<query_unit>(?-i:M)) раствор (?P<salt>{order.CODE}) '
    rf'в нефторированном (?P<base>{order.CODE})\?\s*$', re.I)
IDENTITY = re.compile(rf'The relative permittivity and viscosity of (?P<sample>{order.CODE}) were higher than those of '
    rf'(?P<name>1,2-diethoxyethane) \((?P<base>{order.CODE}), (?P<alias>ethylene glycol diethyl ether)\)\.')
PATTERN = re.compile(
    rf'Figure (?P<figure>\d+)\(a\) shows the temperature \(T\) dependence of '
    rf'conductivities \([^() ]+\) of electrolyte solutions in '
    rf'(?P<solvents>(?P<s1>{order.CODE}), (?P<s2>{order.CODE}), and (?P<s3>{order.CODE}))\. '
    rf'We used (?P<salt>{order.CODE}) \((?P<concentration>{order.NUMBER}) (?P<unit>{order.UNIT}) '
    rf'at (?P<temperature>{order.NUMBER})(?P<temperature_unit>°C)\) as the electrolyte\. '
    rf'The solubility of (?P<salt2>{order.CODE}) in (?P<excluded>{order.CODE}) was '
    rf'(?P<comparison>much less than) (?P<limit>{order.NUMBER}) (?P<limit_unit>{order.UNIT})\.')


def parse(v: SourceView, identity: re.Match[str], m: re.Match[str], *, salt: str, base: str,
          concentration: str) -> tuple[list[Fact], str]:
    solvents = [m[k] for k in ('s1', 's2', 's3')]
    if (len(set(solvents)) != 3 or base in solvents or identity['sample'] not in solvents
            or base != identity['base'] or base != m['excluded'] or salt != m['salt'] or salt != m['salt2']
            or identity.end() > m.start() or Decimal(concentration) <= 0
            or Decimal(m['concentration']) != Decimal(concentration) or Decimal(m['limit']) != Decimal(concentration)):
        raise FactPatternError('solubility_limit_identity_salt_solvent_or_comparison_concentration_mismatch')
    facts = [Fact('unfluorinated_reference_solvent_identity', v.value(identity, 'base'), v.value(identity, 'name'), None,
        'literal_diethoxyethane_name_and_alias_not_general_structure_validation', None,
        {'alias': v.value(identity, 'alias')}, 'source_declared_identity', v.support(identity))]
    conditions = {k: v.value(m, g) for k, g in (
        ('concentration_reference_temperature', 'temperature'), ('temperature_unit', 'temperature_unit'),
        ('solvent_set', 'solvents'), ('figure', 'figure'))}
    facts.append(Fact('conductivity_comparison_concentration', v.value(m, 'salt'), v.value(m, 'concentration'),
        v.value(m, 'unit'), 'source_reported_method', None, conditions, 'source_reported_quantity', v.support(m)))
    facts.append(Fact('solubility_below_comparison_concentration', v.value(m, 'excluded'), v.value(m, 'comparison'),
        v.value(m, 'limit_unit'), 'source_reported_qualitative_limit_not_exact_solubility', None,
        {'salt': v.value(m, 'salt2'), 'comparison_concentration': v.value(m, 'limit')}, 'source_reported_qualitative_limit',
        v.support(m), ('exact_solubility', 'solubility_measurement_temperature', 'preparation_attempt', 'conductivity_value')))
    text = (f"В температурном сравнении проводимости (рис. {m['figure']}(a)) авторы использовали растворы "
        f"{salt} концентрации {m['concentration']} {m['unit']} в {m['s1']}, {m['s2']} и {m['s3']}; "
        f"концентрация указана при {m['temperature']}{m['temperature_unit']}. "
        f"Для {base} ({identity['name']}, {identity['alias']}) в том же фрагменте прямо указано: "
        f"растворимость {salt} была «значительно меньше {m['limit']} {m['limit_unit']}». "
        f"Ограничение для сравнения {concentration} M раствора в {base} — недостаточная растворимость "
        'относительно выбранной концентрации. Это сопоставление приведённых авторами условий; '
        'точная растворимость и её температура измерения здесь не указаны. Из него не следует, '
        'что соль совсем не растворяется, что проводимость равна нулю или что описана неудачная попытка приготовления.')
    return facts, text
