"""Finite reported solvation/concentration trends and a qualified Raman association."""
from __future__ import annotations

import re

from app.generation.fact_types import Fact, FactPatternError, SourceView

CODE = r'[A-Z][A-Za-z0-9]{0,24}'
ION = r'[A-Z][a-z]?\s*\+'
MU = rf'[μµ]{ION}'
ANION = rf'{CODE}[−-]'
PREPARATION = re.compile(rf'Various organic electrolytes were prepared by mixing (?P<salt>{CODE}) and '
    rf'(?P<solvents>organic solvents with different solvation abilities) '
    rf'\(Figure S\d+, Supporting Information\)\.')
TREND = re.compile(rf'Overall, (?P<symbol>{MU}) (?P<direction>increases) \(thus, (?P<ion>{ION}) '
    rf'is (?P<stability>destabilized)\) under the conditions of i\) a (?P<solvation>weaker solvation ability of solvents) '
    rf'and ii\) a (?P<concentration>higher salt concentration) \((?P<localized>including a localized '
    rf'high-concentration state)\) as demonstrated in Figure (?P<figure>\d+)\.')
CORRELATION = re.compile(rf'To corroborate the importance of ion pairing, the (?P<symbol>{MU}) values in '
    rf'(?P<scope>various (?P<salt>{CODE}) electrolytes with different solvents and salt concentrations) '
    rf'are plotted versus the (?P<method>Raman peak positions) of (?P<anion>{ANION})\s*vibration '
    rf'\(Figure (?P<figure>\d+)c\)\. As a result, there is a (?P<correlation>linear correlation) between the '
    rf'(?P<symbol2>{MU}) values and the Raman peak positions, (?P<status>suggesting) that the '
    rf'(?P<direction>increase) in (?P<symbol3>{MU}) is (?P<qualifier>commonly related) to '
    rf'(?P<pairing>extensive ion pairing of (?P<ion>{ION}) and (?P<anion2>{ANION}))\. In summary, '
    rf'(?P<symbol4>{MU}) in electrolytes is (?P<summary>predominantly determined by the interaction between '
    rf'(?P<ion2>{ION}) and anion)\. Hence, the (?P<coordination>coordination number) '
    rf'\(i\.e\., the (?P<extent>extent of ion pairing)\) and the (?P<basicity>Lewis basicity of the anion) '
    rf'are the (?P<role>important factors to control) the (?P<symbol5>{MU})\.')


def compact(text: str) -> str:
    return re.sub(r'\s+', '', text).replace('µ', 'μ').replace('−', '-')


def parse(v: SourceView, preparation: re.Match[str], trend: re.Match[str], correlation: re.Match[str],
          *, symbol: str) -> tuple[list[Fact], str]:
    p, t, c = preparation, trend, correlation
    ion = compact(t['ion'])
    anion = compact(c['anion'])
    if (compact(t['symbol']) != symbol or symbol != 'μ' + ion
            or any(compact(c[k]) != symbol for k in ('symbol', 'symbol2', 'symbol3', 'symbol4', 'symbol5'))
            or any(compact(c[k]) != ion for k in ('ion', 'ion2')) or compact(c['anion2']) != anion
            or p['salt'] != c['salt'] or c['salt'] != ion[:-1] + anion[:-1]
            or t['figure'] != c['figure'] or not p.end() <= t.start() < t.end() <= c.start()):
        raise FactPatternError('solvation_potential_ion_salt_figure_or_source_order_mismatch')
    interval = v.anchor(p.start(), c.end())
    if re.search(r'(?m)^\s*\d+\.\d+\.\s', interval.text):
        raise FactPatternError('solvation_statements_cross_section_boundary')

    def fact(prop: str, value: str, *, row: re.Match[str], keys: tuple[str, ...], status: str) -> Fact:
        return Fact(prop, v.value(row, 'symbol'), v.value(row, value), None, status, None,
            {**{k: v.value(row, k) for k in keys}, 'prepared_salt': v.value(p, 'salt'),
             'preparation_scope': v.value(p, 'solvents')}, status, v.support(row),
            ('numerical_response_coefficient', 'temperature'))

    solvent = fact('weaker_solvation_potential_trend', 'direction', row=t,
        keys=('solvation', 'ion', 'stability', 'figure'), status='source_reported_direction')
    concentration = fact('higher_concentration_potential_trend', 'direction', row=t,
        keys=('concentration', 'localized', 'ion', 'stability', 'figure'), status='source_reported_direction')
    association = fact('raman_potential_pairing_correlation', 'correlation', row=c,
        keys=('scope', 'method', 'anion', 'status', 'direction', 'qualifier', 'pairing', 'figure'),
        status='source_reported_correlation_with_suggestive_interpretation')
    factors = fact('anion_interaction_author_summary', 'summary', row=c,
        keys=('coordination', 'extent', 'basicity', 'role'), status='source_author_interpretation')
    text = (f"В исследованных электролитах {p['salt']} авторы сообщают, что {symbol} повышается при "
        'ослаблении сольватирующей способности растворителя и при повышении концентрации соли, '
        f"в том числе в локализованном высококонцентрированном состоянии. Это соответствует дестабилизации {ion} "
        'в сольватационном окружении. Авторы связывают рост химического потенциала с более выраженным '
        f"ионным спариванием {ion} и {c['anion']}: они приводят линейную корреляцию {symbol} с положением "
        f"Raman-пиков колебаний {c['anion']} в электролитах с разными растворителями и концентрациями. "
        'Это корреляция и предложенная авторами интерпретация связи. В их итоговом объяснении важны '
        'взаимодействие катиона с анионом, координационное число (степень ионного спаривания) и '
        'основность аниона по Льюису. Отдельное направление эффекта основности аниона и численный '
        'коэффициент зависимости в этом выводе не заданы.')
    return [solvent, concentration, association, factors], text
