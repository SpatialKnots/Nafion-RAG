"""Finite caption/body bindings separating cycling and conductivity solutions."""
from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

from app.generation.fact_types import Fact, FactPatternError, SourceView
from app.generation.providers import Evidence
from app.generation.reviewed_glyphs import ReviewedGlyphView

GLYPHS = (Path(__file__).resolve().parents[1] / 'resources/reviewed_cell_conditions_glyph_aliases_v01.json',
          'f765573b70ecccf78916da9cc1d0a9c96fb1d4ff41de06f0af809794d0f39183')
TAIL = r'и почему важно не смешивать эти условия\?\s*$'
CODE = r'[A-Z][A-Za-z0-9]{0,24}'
N = r'\d+(?:\.\d+)?'
UNIT = r'mol dm[−-]3'
MIX = rf'{CODE}[–-]{CODE}'
BODY = re.compile(
    rf'Figure (?P<figure>\d+)\(a\) shows the temperature \(T\) dependence of conductivities '
    rf'\([^()]{{1,8}}\) of electrolyte solutions in (?P<s1>{CODE}), (?P<s2>{CODE}), and (?P<s3>{CODE})\. '
    rf'We used (?P<salt>{CODE}) \((?P<c>{N}) (?P<unit>{UNIT}) at (?P<temp>{N})(?P<tunit>°C)\) as the electrolyte\.')
CAPTION = re.compile(
    rf'Figure (?P<figure>\d+)\. \(Color online\) \(a\) Electrolytic conductivities \([^()]{{1,8}}\) of '
    rf'(?P<ac>{N}) (?P<aunit>{UNIT}) (?P<asalt>{CODE}) solutions in '
    rf'(?P<s1>{CODE}), (?P<s2>{CODE}), and (?P<s3>{CODE}) as a function of temperature \(T\) from '
    rf'(?P<minK>{N}) K \((?P<minC>[−-]?{N})°C\) to (?P<maxK>{N}) K \((?P<maxC>[−-]?{N})°C\)\. '
    rf'\(b\) Variation of discharge capacities of (?P<cell>{CODE} \| {CODE}) coin cells with respect to '
    rf'the cycle number at (?P<temp>{N})(?P<tunit>°C)\. Electrolyte solutions: '
    rf'(?P<c1>{N}) (?P<unit1>{UNIT}) (?P<salt1>{CODE}) solutions in '
    rf'(?P<m1>{MIX}), (?P<m2>{MIX}), and (?P<m3>{MIX}) (?P<basis1>equimolar binary mixtures) and '
    rf'(?P<c2>{N}) (?P<unit2>{UNIT}) (?P<salt2>{CODE}) solution in an '
    rf'(?P<m4>{MIX}) (?P<basis2>equimolar binary mixture)\.')


def view(source: Evidence) -> ReviewedGlyphView:
    return ReviewedGlyphView(source, catalogue_binding=GLYPHS)


def parse(v: SourceView, body: re.Match[str], caption: re.Match[str], *, salt: str, cell: str) -> tuple[list[Fact], str]:
    b, c = body, caption
    solvents = [b[k] for k in ('s1', 's2', 's3')]
    mixes = [c[k] for k in ('m1', 'm2', 'm3', 'm4')]
    parts = [re.split('[–-]', mix) for mix in mixes]
    def number(s: str) -> Decimal:
        return Decimal(s.replace('−', '-'))
    if (b['figure'] != c['figure'] or len(set(solvents)) != 3
            or set(solvents) != {c[k] for k in ('s1', 's2', 's3')}
            or any(s != salt for s in (b['salt'], c['asalt'], c['salt1'], c['salt2']))
            or c['cell'].replace(' | ', '/') != cell
            or number(b['c']) != number(c['ac']) or number(b['c']) <= 0
            or any(number(c[k]) <= 0 for k in ('c1', 'c2')) or number(c['c1']) == number(c['c2'])
            or len(set(mixes)) != 4 or len({p[0] for p in parts}) != 1
            or not set(solvents).issubset({p[1] for p in parts})
            or len({p[1] for p in parts}) != 4 or any(p[0] == p[1] for p in parts)
            or number(c['minK']) >= number(c['maxK']) or number(c['minC']) >= number(c['maxC'])):
        raise FactPatternError('cell_solution_salt_cell_figure_concentration_or_mixture_mismatch')
    facts = []
    for i in range(1, 5):
        group = '1' if i < 4 else '2'
        facts.append(Fact('cycling_solution_concentration', v.value(c, f'm{i}'), v.value(c, 'c' + group),
            v.value(c, 'unit' + group), 'source_reported_conditions', None,
            {k: v.value(c, name) for k, name in [('salt', 'salt' + group), ('cell', 'cell'), ('figure', 'figure'),
                ('mixing_basis', 'basis' + group), ('temperature', 'temp'), ('temperature_unit', 'tunit')]},
            'source_reported_conditions', v.support(c)))
    facts.append(Fact('conductivity_solution_concentration', v.value(b, 'salt'), v.value(b, 'c'), v.value(b, 'unit'),
        'source_reported_conditions_separate_experiment', None,
        {**{k: v.value(b, k) for k in ('s1', 's2', 's3', 'figure')},
         **{k: v.value(c, k) for k in ('ac', 'aunit', 'asalt', 'minK', 'maxK', 'minC', 'maxC')},
         'concentration_reference_temperature': v.value(b, 'temp'), 'temperature_unit': v.value(b, 'tunit')},
        'source_reported_conditions', v.support(b)))
    text = (f"Испытания {cell}, рис. {c['figure']}(b), при {c['temp']}{c['tunit']}: "
            f"{salt} в эквимолярных бинарных смесях "
            + '; '.join(f"{mix} — {c['c1' if i < 3 else 'c2']} {c['unit1' if i < 3 else 'unit2']}"
                        for i, mix in enumerate(mixes)) + '. '
            + f"Отдельное измерение проводимости, рис. {b['figure']}(a): {b['c']} {b['unit']} {salt} "
            f"в {', '.join(solvents)}; концентрация указана при {b['temp']}{b['tunit']}, "
            f"диапазон измерений {c['minK']}–{c['maxK']} K ({c['minC']}–{c['maxC']}°C). "
            'Концентрации двух групп смесей различаются; перенос одного значения на все смеси изменил бы '
            'указанные условия. Условия измерения проводимости относятся к отдельному эксперименту. '
            'Эта сводка не определяет отдельные причинные вклады концентрации и растворителя.')
    return facts, text
