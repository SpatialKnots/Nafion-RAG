"""Finite pure-solvent concentration/molar-mass comparison with a possible-contraction interpretation."""
from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

from app.generation.fact_types import Fact, FactPatternError, SourceView
from app.generation.providers import Evidence
from app.generation.reviewed_glyphs import ReviewedGlyphView

GLYPHS = (Path(__file__).resolve().parents[1] / 'resources/reviewed_pure_concentration_glyph_aliases_v01.json',
          'f9d4bc4425c8932e704856f32e7a90723fd4d953230d9adc8f1494995f793862')
CODE = r'[A-Z][A-Za-z0-9]{0,24}'
N = r'\d+(?:\.\d+)?'
SIGNED = rf'[−-]?{N}'
QUERY = re.compile(rf'Почему молярная концентрация чистого (?P<higher>{CODE}) при (?P<temperature>{SIGNED})\s*°C '
                   rf'выше, чем (?P<lower>{CODE}), несмотря на большую молярную массу\?\s*$', re.I)
FRAME = re.compile(rf'Figure \d+ shows the temperature \([^()]{{1,8}}\) dependence of relative permittivities of '
    rf'(?P<s1>{CODE}), (?P<s2>{CODE}), (?P<s3>{CODE}), and (?P<s4>{CODE}) (?P<state>single solvents)\.')
PATTERN = re.compile(rf'The molar concentration of (?P<higher>{CODE}) \((?P<c1>{N}) (?P<unit1>mol dm[−-]3) '
    rf'at (?P<t1>{SIGNED})(?P<tunit1>°C)\) was higher than that of (?P<lower>{CODE}) '
    rf'\((?P<c2>{N}) (?P<unit2>mol dm[−-]3) at (?P<t2>{SIGNED})(?P<tunit2>°C)\) in spite of the high molar mass '
    rf'\((?P<m1>{N}) (?P<munit1>g mol[−-]1) for (?P<higher2>{CODE}) and (?P<m2>{N}) '
    rf'(?P<munit2>g mol[−-]1) for (?P<lower2>{CODE})\)\. The liquid (?P<modal>may contract to some extent) '
    rf'because of the (?P<cause>strong attractive forces between (?P<higher3>{CODE}) molecules), and consequently '
    rf'the (?P<consequence>molar concentration of (?P<higher4>{CODE}) increased)\.')


def view(source: Evidence) -> ReviewedGlyphView:
    return ReviewedGlyphView(source, catalogue_binding=GLYPHS)


def number(text: str) -> Decimal:
    return Decimal(text.replace('−', '-'))


def parse(v: SourceView, frame: re.Match[str], m: re.Match[str], *, higher: str, lower: str,
          temperature: str) -> tuple[list[Fact], str]:
    solvents = [frame[k] for k in ('s1', 's2', 's3', 's4')]
    if (len(set(solvents)) != 4 or higher == lower or not {higher, lower}.issubset(solvents)
            or any(m[k] != higher for k in ('higher', 'higher2', 'higher3', 'higher4'))
            or any(m[k] != lower for k in ('lower', 'lower2'))
            or number(m['c1']) <= number(m['c2']) or number(m['c2']) <= 0
            or number(m['m1']) <= number(m['m2']) or number(m['m2']) <= 0
            or any(number(m[k]) != number(temperature) for k in ('t1', 't2')) or frame.end() > m.start()):
        raise FactPatternError('pure_solvent_membership_pair_temperature_concentration_or_mass_mismatch')
    if re.search(r'(?<!\S)\d+\.\d+\.?\s+[A-ZА-Я]', v.anchor(frame.start(), m.end()).text):
        raise FactPatternError('pure_solvent_comparison_crosses_subsection_boundary')
    facts = []
    for index, sample in (('1', 'higher'), ('2', 'lower')):
        facts.append(Fact('pure_solvent_molar_concentration', v.value(m, sample), v.value(m, 'c' + index),
            v.value(m, 'unit' + index), 'source_reported_same_temperature_comparison', None,
            {'temperature': v.value(m, 't' + index), 'temperature_unit': v.value(m, 'tunit' + index),
             'molar_mass': v.value(m, 'm' + index), 'molar_mass_unit': v.value(m, 'munit' + index),
             'specimen_state': v.value(frame, 'state')}, 'source_reported_quantity', v.support(m)))
    facts.append(Fact('possible_liquid_contraction', v.value(m, 'higher3'), v.value(m, 'modal'), None,
        'source_author_possible_explanation', None,
        {'cause': v.value(m, 'cause'), 'reported_consequence': v.value(m, 'consequence'),
         'specimen_state': v.value(frame, 'state')}, 'source_author_possible_explanation', v.support(m),
        ('numerical_mass_density', 'volume_contraction_fraction', 'independent_structural_validation')))
    text = (f"Для чистых растворителей при {m['t1']}{m['tunit1']} авторы приводят молярные концентрации "
        f"{higher}: {m['c1']} {m['unit1']} и {lower}: {m['c2']} {m['unit2']}. При этом молярная масса "
        f"{higher} больше: {m['m1']} {m['munit1']} против {m['m2']} {m['munit2']} для {lower}. "
        f"Авторы объясняют это возможным сжатием жидкости из-за сильного притяжения между молекулами {higher}: "
        'жидкость «может в некоторой степени сжиматься», что они связывают с увеличением молярной концентрации. '
        'Это предложенное авторами объяснение; численная плотность и степень сжатия в этом фрагменте не заданы.')
    return facts, text
