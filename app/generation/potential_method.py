"""Finite source method, electrode-reference direction and relative-zero bindings."""
from __future__ import annotations

import re
from decimal import Decimal

from app.generation.fact_types import Fact, FactPatternError, SourceView

CODE = r'[A-Z][A-Za-z0-9]{0,24}'
METAL = r'[A-Z][a-z]?'
MU = rf'[μµ]{METAL}\s*\+'
ELECTRODE = rf'E\s*{METAL}'
PAIR = rf'{CODE}/{CODE}\+'
NUMBER = r'\d+(?:\.\d+)?'
RATIO = rf'{NUMBER}/{NUMBER}'
PREPARATION = re.compile(
    rf'The (?P<salt>{CODE}) salt was dissolved in electrolyte solvents to prepare electrolyte solutions '
    rf'in an (?P<atmosphere>[A-Z][a-z]?)-filled glove box\. The electrolyte containing '
    rf'(?P<concentration>{NUMBER}) (?P<unit>mmol dm[−-]3) \((?P<short>mM|mm)\) '
    rf'(?P<additive>{CODE}) \([^()]{{1,80}}\) was also prepared for measuring '
    rf'(?P<electrode>{ELECTRODE}) with reference to (?P<pair>{PAIR})\.')
PATTERN = re.compile(
    rf'Evaluation of (?P<symbol>{MU}): To quantify (?P<symbol2>{MU}) in an electrolyte, '
    rf'(?P<electrode>{ELECTRODE}) was measured with reference to the redox potential of (?P<pair>{PAIR})\. '
    rf'The electrochemical cell used in this experiment was composed of (?P<count>three) electrodes '
    rf'\(Figure [A-Za-z0-9]+, Supporting Information\): a (?P<working>{METAL}) plate working electrode '
    rf'\([^()]{{1,80}}\) and (?P<metal>{METAL}) metal (?P<roles>reference and counter electrodes) '
    rf'\([^()]{{1,80}}\) with electrolytes containing (?P<concentration>{NUMBER}) '
    rf'(?P<short>mM|mm) (?P<additive>{CODE})\. '
    rf'(?P<method>Cyclic voltammetry) was conducted using a (?P<instrument>[A-Za-z0-9+ -]{{1,80}}) '
    rf'\([^()]{{1,80}}\) to measure the (?P<observable>redox potential of (?P<pair2>{PAIR}) '
    rf'with reference to (?P<reference>{METAL}) reference electrode), from the '
    rf'(?P<readout>midpoint of the oxidation/reduction peaks)\. Here, '
    rf'(?P<assumption>supposing that the redox potential of (?P<pair3>{PAIR}) was constant),\[\d+\] '
    rf'(?P<electrode2>{ELECTRODE}) was defined as (?P<definition>(?P<metal2>{METAL}) electrode potential '
    rf'with reference to the (?P<pair4>{PAIR}) redox potential)\. As shown in Note S\d+ '
    rf'\(Supporting Information\), (?P<symbol3>{MU}) in an electrolyte can be derived from the '
    rf'(?P<electrode3>{ELECTRODE}) (?P<same>evaluated in the same electrolyte)\. '
    rf'(?P<equation>(?P<symbol4>{MU}) = F(?P<electrode4>{ELECTRODE}) \+ constant) \(\d+\) '
    rf'Here, (?P<symbol5>{MU}) was defined to be (?P<zero>zero) in a standard electrolyte, '
    rf'(?P<basis>(?P<salt>{CODE})/(?P<solvent>{CODE})) \((?P<ratio>{RATIO}) (?P<ratio_unit>by mol)\), '
    rf'and (?P<symbol6>{MU}) in various electrolytes was obtained as (?P<relative>relative values) '
    rf'with reference to that in (?P<basis2>{CODE}/{CODE}) \((?P<ratio2>{RATIO}) by mol\)\.')


def compact(text: str) -> str:
    return re.sub(r'\s+', '', text).replace('µ', 'μ')


def parse(view: SourceView, match: re.Match[str], prep: re.Match[str], symbol: str) -> tuple[list[Fact], str]:
    metal = match['metal']
    electrode = 'E' + metal
    pairs = [match[k] for k in ('pair', 'pair2', 'pair3', 'pair4')] + [prep['pair']]
    pair = pairs[0]
    reduced, oxidized = pair.split('/')
    if (any(compact(match[k]) != symbol for k in ('symbol', 'symbol2', 'symbol3', 'symbol4', 'symbol5', 'symbol6'))
            or symbol != 'μ' + metal + '+' or match['reference'] != metal or match['metal2'] != metal
            or any(compact(match[k]) != electrode for k in ('electrode', 'electrode2', 'electrode3', 'electrode4'))
            or compact(prep['electrode']) != electrode or len(set(pairs)) != 1
            or oxidized != reduced + '+' or match['additive'] != reduced or prep['additive'] != reduced
            or match['salt'] != prep['salt'] or match['basis'] != match['basis2'] or match['ratio'] != match['ratio2']
            or any(Decimal(v) <= 0 for v in match['ratio'].split('/'))
            or Decimal(match['concentration']) != Decimal(prep['concentration'])
            or Decimal(prep['concentration']) <= 0 or match['short'] != prep['short']):
        raise FactPatternError('potential_method_reference_symbol_dose_or_zero_basis_mismatch')
    support = view.support(match)

    def fact(prop: str, value: str, *, sample: str = 'symbol', conditions: tuple[str, ...] = (),
             operation: str = 'source_reported_method') -> Fact:
        return Fact(prop, view.value(match, sample), view.value(match, value), None, operation, None,
                    {key: view.value(match, key) for key in conditions}, 'source_reported_method_or_convention',
                    support, ('measurement_temperature',))

    method = fact('cv_redox_measurement', 'observable', conditions=('working', 'metal', 'roles', 'readout', 'instrument'))
    method = Fact(method.property, method.sample, method.value, None, method.operation, view.value(match, 'method'),
                  method.conditions, method.epistemic_status, support, method.unknown_fields)
    dose = Fact('prepared_redox_additive_concentration', view.value(prep, 'additive'), view.value(prep, 'concentration'),
        view.value(prep, 'unit'), 'source_reported_preparation', None,
        {'salt': view.value(prep, 'salt'), 'electrode': view.value(prep, 'electrode'), 'pair': view.value(prep, 'pair')},
        'source_reported_method_or_convention', view.support(prep))
    definition = fact('electrode_potential_reference_definition', 'definition', sample='electrode2',
                      conditions=('assumption',), operation='source_defined_reference_direction')
    equation = fact('chemical_potential_relation', 'equation', conditions=('same', 'assumption'),
                    operation='reported_relation_without_numeric_calculation')
    zero = fact('relative_zero_reference', 'zero', conditions=('basis', 'ratio', 'ratio_unit', 'relative'),
                operation='chosen_relative_zero_convention')
    text = (f"Авторы оценивали {symbol} через {electrode}. Циклической вольтамперометрией "
            f"({match['instrument']}) измеряли редокс-потенциал {pair} относительно {metal}-электрода сравнения "
            f"по средней точке между пиками окисления и восстановления. В трёхэлектродной ячейке рабочим "
            f"электродом служила {match['working']}-пластина, а электродом сравнения и вспомогательным — металлический {metal}; "
            f"электролит содержал {prep['concentration']} {prep['unit']} {reduced}. "
            f"Предполагая постоянство редокс-потенциала {pair}, {electrode} задавали как потенциал "
            f"{metal}-электрода относительно {pair}; затем использовали соотношение "
            f"{symbol} = F{electrode} + constant для того же электролита. "
            f"Относительный ноль {symbol} выбран для стандартного электролита {match['basis']} "
            f"({match['ratio']} по молям). Остальные значения приведены относительно этого состава. "
            'Температура CV в выбранном фрагменте не указана.')
    return [method, dose, definition, equation, zero], text
