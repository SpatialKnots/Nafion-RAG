"""A finite same-salt/concentration three-solvent conductivity ordering contract."""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

from app.generation.fact_types import Fact, FactPatternError
from app.generation.providers import Evidence
from app.generation.reviewed_glyphs import ReviewedGlyphView

GLYPH_CATALOGUE = (Path(__file__).resolve().parents[1] / 'resources/reviewed_conductivity_glyph_aliases_v01.json',
                   '3f38c59fb8c6819b9f7808bb0b5b78594d8286e846917558b342a640042fc8e3')
CODE = r'[A-Z][A-Za-z0-9]{0,24}'
NUMBER = r'\d+(?:\.\d+)?'
UNIT = r'mol dm[−-]3'
PATTERN = re.compile(
    rf'Figure (?P<figure>\d+)\(a\) shows the temperature \(T\) dependence of '
    rf'conductivities \((?P<symbol>[^() ]+)\) of electrolyte solutions in '
    rf'(?P<solvents>(?P<s1>{CODE}), (?P<s2>{CODE}), and (?P<s3>{CODE}))\. '
    rf'We used (?P<salt>{CODE}) \((?P<concentration>{NUMBER}) (?P<unit>{UNIT}) '
    rf'at (?P<temperature>{NUMBER})(?P<temperature_unit>°C)\) as the electrolyte\. '
    rf'The solubility of (?P<salt3>{CODE}) in (?P<excluded>{CODE}) was much less than '
    rf'(?P<limit>{NUMBER}) (?P<limit_unit>{UNIT})\. '
    rf'The conductivities increased with an increase in temperature\. '
    rf'The viscosities of the (?P<category>fluorinated DEEs) decreased rapidly with an '
    rf'increase in temperature and approached that of (?P<excluded2>{CODE}) at high '
    rf'temperatures, as shown in Fig\. \d+\(a\)\. '
    rf'Interestingly, the conductivity of (?P<salt2>{CODE}) solution in (?P<higher>{CODE}) was '
    rf'higher than that in (?P<lower>{CODE}): '
    rf'(?P<order>(?P<rank1>{CODE}) > (?P<rank2>{CODE}) > (?P<rank3>{CODE}))\.')


def view(source: Evidence) -> ReviewedGlyphView:
    # Only this family uses this separate trusted, SHA-pinned resource.
    # No resource paths/operations are accepted from a client or model payload.
    return ReviewedGlyphView(source, catalogue_binding=GLYPH_CATALOGUE)


def parse(source_view: ReviewedGlyphView, match: re.Match[str], *, salt: str,
          concentration: str) -> tuple[list[Fact], str]:
    solvents = [match[k] for k in ('s1', 's2', 's3')]
    ranking = [match[k] for k in ('rank1', 'rank2', 'rank3')]
    if (len(set(solvents)) != 3 or len(set(ranking)) != 3 or set(solvents) != set(ranking)
            or not match['salt'] == match['salt2'] == match['salt3'] == salt
            or Decimal(match['concentration']) != Decimal(concentration)
            or Decimal(match['limit']) != Decimal(concentration)
            or match['excluded'] != match['excluded2'] or match['excluded'] in solvents
            or match['higher'] not in ranking or match['lower'] not in ranking
            or ranking.index(match['higher']) >= ranking.index(match['lower'])):
        raise FactPatternError('conductivity_order_salt_concentration_membership_or_relation_mismatch')
    conditions = {key: source_view.value(match, group) for key, group in (
        ('concentration', 'concentration'), ('concentration_unit', 'unit'),
        ('concentration_reference_temperature', 'temperature'), ('reference_temperature_unit', 'temperature_unit'),
        ('solvent_set', 'solvents'), ('solvent_class', 'category'), ('figure', 'figure'),
        ('pair_higher', 'higher'), ('pair_lower', 'lower'))}
    fact = Fact('reported_conductivity_order', source_view.value(match, 'salt'), source_view.value(match, 'order'),
        None, 'reported_strict_order_not_numeric_estimate', None, conditions, 'reported', source_view.support(match),
        ('absolute_conductivity_values', 'measurement_temperature_range'))
    text = (f"Для растворов {match['salt']} концентрации {match['concentration']} {match['unit']} "
            f"в исследованных фторированных эфирах авторы приводят порядок ионной проводимости: "
            f"{match['order']}. Концентрация указана при {match['temperature']}{match['temperature_unit']}; "
            f"порядок относится к температурным зависимостям на рис. {match['figure']}(a). "
            'Обозначение M в вопросе соответствует mol dm⁻³ в источнике; численное значение концентрации '
            'не пересчитывается. Абсолютные значения проводимости здесь не определяются.')
    return [fact], text
