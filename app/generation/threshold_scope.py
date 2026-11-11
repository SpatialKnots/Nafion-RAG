"""Finite stated threshold applicability and possible shifts; no universal value or shift prediction."""
from __future__ import annotations

import re

from app.generation.fact_types import Fact, FactPatternError, SourceView

CODE = r'[A-Z][A-Za-z0-9]{0,24}'
ION = r'[A-Z][a-z]?\s*\+'
MU = rf'[μµ]{ION}'
QUERY = re.compile(rf'Доказывает ли работа универсальное неизменное значение порога (?P<symbol>{MU}) '
                   r'для любых солей, добавок и поверхностных покрытий\?\s*$', re.I)
PATTERN = re.compile(rf'We discovered that (?P<symbol>{MU}) is a quantitative descriptor of the '
    rf'(?P<ion>{ION}) intercalation behavior of (?P<electrode>graphite negative electrodes)\. '
    rf'Unfavorable (?P<ion2>{ION})[–-]solvent cointercalation is (?P<frequency>commonly suppressed) when '
    rf'(?P<symbol2>{MU}) is (?P<direction>increased) \(thus, (?P<ion3>{ION}) is destabilized in the electrolyte\) '
    rf'to above a certain threshold\. This threshold is (?P<applicability>generally applicable) to '
    rf'(?P<scope>various types of (?P<salt>{CODE})-based electrolytes) \(e\.g\., '
    rf'(?P<type1>highly concentrated electrolytes), (?P<type2>localized highly concentrated electrolytes), '
    rf'and (?P<type3>weakly coordinating electrolytes)\) to form (?P<film>inorganic-rich SEI)\. '
    rf'On the basis of this insight, new electrolytes can be rationally designed, with a focus on '
    rf'(?P<symbol3>{MU}) to ensure the reversible reaction of (?P<electrode2>graphite negative electrodes)\. '
    rf'The (?P<symbol4>{MU}) threshold (?P<modal>may be shifted) when the (?P<condition>nature of SEI is '
    rf'significantly changed) with (?P<factor1>SEI forming additives), '
    rf'(?P<factor2>extremely unstable solvent/salt for reduction), (?P<factor3>passivating binders), '
    rf'and (?P<factor4>functional surface coatings)\.')


def compact(text: str) -> str:
    return re.sub(r'\s+', '', text).replace('µ', 'μ')


def parse(v: SourceView, m: re.Match[str], *, symbol: str) -> tuple[list[Fact], str]:
    ion = compact(m['ion'])
    if (symbol != 'μ' + ion or any(compact(m[k]) != symbol for k in ('symbol', 'symbol2', 'symbol3', 'symbol4'))
            or any(compact(m[k]) != ion for k in ('ion2', 'ion3')) or m['electrode'] != m['electrode2']
            or not m['salt'].startswith(ion[:-1]) or len(m['salt']) <= len(ion[:-1])):
        raise FactPatternError('threshold_scope_potential_ion_salt_or_electrode_mismatch')

    def fact(prop: str, value: str, keys: tuple[str, ...], status: str) -> Fact:
        return Fact(prop, v.value(m, 'symbol'), v.value(m, value), None, status, None,
            {**{k: v.value(m, k) for k in keys}, 'electrode': v.value(m, 'electrode')},
            status, v.support(m), ('universal_threshold_value', 'shift_direction', 'shift_magnitude'))

    scope = fact('reported_threshold_applicability', 'scope',
        ('applicability', 'type1', 'type2', 'type3', 'film'), 'source_reported_scoped_applicability')
    possible = fact('possible_threshold_shift', 'modal', ('condition',), 'source_author_modal_caveat')
    factors = [fact('threshold_shift_context', key, ('condition', 'modal'), 'source_author_modal_caveat')
               for key in ('factor1', 'factor2', 'factor3', 'factor4')]
    text = (f"Нет: работа не устанавливает универсального неизменного порога {symbol} для любых солей, добавок "
        f"и покрытий. В Conclusion авторы описывают порог как в целом применимый к различным типам {m['salt']}-based электролитов: "
        'высококонцентрированных, локализованных высококонцентрированных и слабо координирующих, '
        'формирующих неорганически обогащённую SEI на графитовых отрицательных электродах. '
        'При этом они прямо оговаривают, что порог может сдвигаться, если характер SEI существенно меняется '
        'при использовании SEI-формирующих добавок, крайне нестабильных к восстановлению растворителей '
        'или солей, пассивирующих связующих и функциональных поверхностных покрытий. '
        'Это оговорка о возможности сдвига, а не утверждение, что он обязательно происходит. '
        'Знак и величина сдвига в этой оговорке не заданы.')
    return [scope, possible, *factors], text
