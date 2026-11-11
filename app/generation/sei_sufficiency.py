"""Finite evidence against a sole-SEI guarantee; preserve partial contribution and modality."""
from __future__ import annotations

import re
from decimal import Decimal
from fractions import Fraction

from app.generation.fact_types import Fact, FactPatternError, SourceView

CODE = r'[A-Z][A-Za-z0-9]{0,24}'
N = r'\d+(?:\.\d+)?'
RATIO = rf'{N}/{N}'
ION = r'[A-Z][a-z]?\s*\+'
MU = rf'[μµ]{ION}'
QUERY = re.compile(rf'Достаточно ли одного образования SEI из продуктов разложения аниона '
    rf'(?P<anion>{CODE})[−-], чтобы гарантировать отсутствие совместной интеркаляции растворителя\?\s*$', re.I)
PROPOSAL = re.compile(rf'On this basis, (?P<status>we suppose) that (?P<ion>{ION}) intercalation in '
    rf'high-(?P<symbol>{MU}) electrolytes is enabled by (?P<count>two) mechanisms depending on (?P<symbol2>{MU}): '
    rf'i\) (?P<first>formation of (?P<anion>{CODE}) anion-derived SEI) and ii\) '
    rf'(?P<second>destabilization of solvated (?P<ion2>{ION}))\. The SEI is known to be essential for '
    rf'(?P<electrode>graphite negative electrodes)\.')
CONTRIBUTION = re.compile(rf'This unique SEI (?P<contribution>contributes, to some extent, to reversible '
    rf'(?P<ion>{ION}) intercalation) by (?P<action>blocking solvated (?P<ion2>{ION}) from intercalation)\.')
OBSERVATIONS = re.compile(rf'However, we found that the SEI chemistry (?P<no_change>did not remarkably change) '
    rf'in the boundary (?P<symbol>{MU}) region\. As shown in Figure (?P<similar_figure>S\d+) '
    rf'\(Supporting Information\), both (?P<pair>(?P<salt>{CODE})/(?P<solvent>{CODE})) '
    rf'\((?P<ratio1>{RATIO}) and (?P<ratio2>{RATIO}) (?P<basis>by mol)\) resulted in '
    rf'(?P<similar>similar (?P<anion>{CODE}) anion-derived SEI) but showed '
    rf'(?P<difference>remarkably different graphite reactions)\. In addition, (?P<reaction>solvent cointercalation) '
    rf'(?P<not_suppressed>could not be suppressed) in (?P<challenge_pair>{CODE}/{CODE}) '
    rf'\((?P<challenge>{RATIO}) (?P<challenge_basis>by mol)\) (?P<sequence>even after forming SEI) in '
    rf'(?P<formed_pair>{CODE}/{CODE}) \((?P<formed>{RATIO}) (?P<formed_basis>by mol)\) with '
    rf'(?P<state>higher (?P<symbol2>{MU})) \(Figure (?P<transfer_figure>S\d+), Supporting Information\)\.')
CONCLUSION = re.compile(r'Hence, although the SEI is (?P<essential>essential for suppressing electrolyte decomposition), '
    r'it (?P<limitation>may not be the only dominant factor)\.')


def compact(text: str) -> str:
    return re.sub(r'\s+', '', text).replace('µ', 'μ')


def ratio(text: str) -> Fraction:
    left, right = (Decimal(n) for n in text.split('/'))
    if left <= 0 or right <= 0:
        raise FactPatternError('positive_sei_formation_and_challenge_molar_ratios_required')
    return Fraction(left) / Fraction(right)


def parse(v: SourceView, proposal: re.Match[str], contribution: re.Match[str], observations: re.Match[str],
          conclusion: re.Match[str], *, anion: str) -> tuple[list[Fact], str]:
    p, c, o, final = proposal, contribution, observations, conclusion
    ion = compact(p['ion'])
    symbol = 'μ' + ion
    if (any(compact(row[key]) != symbol for row, keys in ((p, ('symbol', 'symbol2')), (o, ('symbol', 'symbol2')))
            for key in keys) or any(compact(row[key]) != ion for row, keys in ((p, ('ion2',)), (c, ('ion', 'ion2')))
            for key in keys) or p['anion'] != anion or o['anion'] != anion or o['salt'] != ion[:-1] + anion
            or o['pair'] != o['challenge_pair'] or o['pair'] != o['formed_pair']
            or ratio(o['ratio1']) == ratio(o['ratio2']) or ratio(o['formed']) != ratio(o['ratio1'])
            or ratio(o['challenge']) != ratio(o['ratio2']) or o['similar_figure'] == o['transfer_figure']
            or not p.end() <= c.start() < c.end() <= o.start() < o.end() <= final.start()):
        raise FactPatternError('sei_sufficiency_ion_origin_electrolyte_sequence_or_ratio_binding_mismatch')

    if re.search(r'(?<!\S)\d+\.\d+\.\s', v.anchor(p.start(), final.end()).text):
        raise FactPatternError('sei_sufficiency_statements_cross_subsection_boundary')

    def fact(row: re.Match[str], prop: str, value: str, keys: tuple[str, ...], status: str) -> Fact:
        return Fact(prop, v.value(p, 'electrode'), v.value(row, value), None, status, None,
            {**{k: v.value(row, k) for k in keys}, 'anion_origin': v.value(p, 'anion')},
            status, v.support(row), ('temperature', 'film_composition_quantities', 'film_thickness'))

    mechanism = fact(p, 'two_proposed_mechanisms', 'second', ('first', 'status', 'count', 'symbol'), 'source_author_supposition')
    partial = fact(c, 'sei_partial_contribution', 'contribution', ('action',), 'source_author_partial_contribution')
    similar = fact(o, 'similar_sei_different_graphite_reactions', 'difference',
        ('pair', 'ratio1', 'ratio2', 'basis', 'similar', 'no_change', 'similar_figure'), 'source_reported_comparison')
    challenge = fact(o, 'cointercalation_after_preformed_sei', 'not_suppressed',
        ('reaction', 'challenge_pair', 'challenge', 'challenge_basis', 'formed_pair', 'formed', 'formed_basis',
         'sequence', 'state', 'transfer_figure'), 'source_reported_preformation_counterexample')
    limit = fact(final, 'sei_essential_but_not_sole_factor', 'limitation', ('essential',), 'source_author_modal_limitation')
    text = (f"Нет: приведённые наблюдения не позволяют считать одно образование {anion}-производной SEI "
        'гарантией отсутствия совместной интеркаляции растворителя в исследованной системе. '
        f"Авторы сообщают, что в {o['pair']} при мольных отношениях соль/растворитель {o['ratio1']} и {o['ratio2']} "
        f"получалась похожая {anion}-производная SEI, но реакции графита заметно различались. "
        f"В {o['challenge_pair']} ({o['challenge']} по молям) совместная интеркаляция не подавлялась даже после "
        f"предварительного формирования SEI в {o['formed_pair']} ({o['formed']} по молям) с более высоким {symbol}. "
        'При этом авторы сохраняют частичный вклад SEI в обратимую интеркаляцию: она в некоторой степени '
        f"препятствует интеркаляции сольватированного {ion}. Они предполагают два механизма: образование "
        f"{anion}-производной SEI и дестабилизацию сольватированного {ion}. В выводе SEI названа существенной "
        'для подавления разложения электролита, но она может быть не единственным определяющим фактором. '
        'Это ограничение достаточности в приведённых опытах, а не утверждение об отсутствии вклада SEI.')
    return [mechanism, partial, similar, challenge, limit], text
