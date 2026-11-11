"""Finite source counterexample to a solvent-independent concentration criterion."""
from __future__ import annotations

import re
from decimal import Decimal
from fractions import Fraction

from app.generation.fact_types import Fact, FactPatternError, SourceView

CODE = r'[A-Z][A-Za-z0-9]{0,24}'
N = r'\d+(?:\.\d+)?'
SIGNED = rf'[−-]?{N}'
RATIO = rf'{N}/{N}'
ION = r'[A-Z][a-z]?\s*\+'
MU = rf'[μµ]{ION}'
QUERY = re.compile(rf'Почему сама по себе концентрация (?P<salt>{CODE}) не является универсальным '
                   rf'критерием подавления совместной интеркаляции\?\s*$', re.I)
BASIS = re.compile(rf'Herein, (?P<symbol>{MU}) is shown as a (?P<status>relative value) to that in '
    rf'(?P<salt>{CODE})/(?P<solvent_name>[A-Za-z0-9,-]{{1,100}}) \((?P<solvent>{CODE})\) '
    rf'\((?P<ratio>{RATIO}) (?P<basis>by mol)\)\.')
PATTERN = re.compile(rf'It should be noted that the (?P<reactions>graphite reactions) '
    rf'(?P<limitation>cannot be defined by the salt concentration)\. For example, the threshold concentrations '
    rf'for (?P<reaction>reversible (?P<ion>{ION}) intercalation) are (?P<difference>remarkably different) for '
    rf'(?P<pair1>(?P<salt1>{CODE})/(?P<solvent1>{CODE})) '
    rf'\((?P<ratio1>{RATIO}) (?P<basis1>by mol), Figure (?P<figure1>S\d+[a-z]), Supporting Information\) and '
    rf'(?P<pair2>(?P<salt2>{CODE})/(?P<solvent2>{CODE})) '
    rf'\((?P<ratio2>{RATIO}) (?P<basis2>by mol), Figure (?P<figure2>S\d+[a-z]), Supporting Information\), '
    rf'but their (?P<symbol>{MU}) values are (?P<similarity>similar) \((?P<value1>{SIGNED}) and '
    rf'(?P<value2>{SIGNED}) (?P<unit>kJ mol[−-]1), (?P<binding>respectively)\)\. This result '
    rf'(?P<status>indicates) that (?P<symbol2>{MU}) (?P<descriptor>can be a descriptor of graphite reactions)\.')


def compact(text: str) -> str:
    return re.sub(r'\s+', '', text).replace('µ', 'μ')


def ratio(text: str) -> Fraction:
    left, right = (Decimal(n) for n in text.split('/'))
    if left <= 0 or right <= 0:
        raise FactPatternError('positive_salt_solvent_molar_ratio_required')
    return Fraction(left) / Fraction(right)


def parse(v: SourceView, basis: re.Match[str], m: re.Match[str], *, salt: str) -> tuple[list[Fact], str]:
    ion = compact(m['ion'])
    symbol = 'μ' + ion
    if (any(compact(row[key]) != symbol for row, keys in ((basis, ('symbol',)), (m, ('symbol', 'symbol2')))
            for key in keys) or any(row[key] != salt for row, keys in ((basis, ('salt',)), (m, ('salt1', 'salt2')))
            for key in keys) or not salt.startswith(ion[:-1]) or len(salt) <= len(ion[:-1])
            or m['solvent1'] == m['solvent2'] or ratio(m['ratio1']) == ratio(m['ratio2'])
            or m['figure1'] == m['figure2'] or basis.end() > m.start()):
        raise FactPatternError('concentration_counterexample_salt_ion_solvent_ratio_or_binding_mismatch')
    ratio(basis['ratio'])
    limitation = Fact('reported_concentration_limitation', v.value(m, 'reactions'), v.value(m, 'limitation'), None,
        'source_reported_limitation', None, {'reaction': v.value(m, 'reaction')}, 'source_reported_limitation', v.support(m))
    pairs = []
    for index in ('1', '2'):
        pairs.append(Fact('solvent_specific_reversible_intercalation_threshold', v.value(m, 'pair' + index),
            v.value(m, 'ratio' + index), None, 'reported_salt_solvent_molar_ratio', None,
            {'molar_basis': v.value(m, 'basis' + index), 'mu': v.value(m, 'value' + index), 'mu_unit': v.value(m, 'unit'),
             'symbol': v.value(m, 'symbol'), 'reported_similarity': v.value(m, 'similarity'),
             'respectively': v.value(m, 'binding'), 'source_figure': v.value(m, 'figure' + index),
             **{'reference_' + key: v.value(basis, key) for key in ('status', 'salt', 'solvent_name', 'solvent', 'ratio', 'basis')}},
            'source_reported_counterexample_pair', v.support(m), ('temperature', 'measurement_uncertainty')))
    descriptor = Fact('chemical_potential_descriptor_interpretation', v.value(m, 'symbol2'), v.value(m, 'descriptor'), None,
        'source_author_interpretation', None, {'status': v.value(m, 'status')}, 'source_author_interpretation', v.support(m))
    text = (f"Авторы приводят контрпример единому порогу концентрации: для обратимой интеркаляции {ion} "
        f"в графит пороги {m['pair1']} и {m['pair2']} составляют соответственно {m['ratio1']} и {m['ratio2']} "
        f"по молям (соль/растворитель), тогда как значения {symbol} равны соответственно {m['value1']} "
        f"и {m['value2']} {m['unit']} и названы авторами близкими. Значения {symbol} приведены относительно "
        f"{basis['salt']}/{basis['solvent']} ({basis['ratio']} по молям). Следовательно, в этом сравнении "
        'один порог концентрации не переносится между растворителями. Авторы указывают, что химический '
        'потенциал может служить дескриптором реакций графита. Это не означает отсутствия влияния концентрации '
        'и не устанавливает универсальный закон для любых солей и растворителей.')
    return [limitation, *pairs, descriptor], text
