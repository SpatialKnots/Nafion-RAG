"""Finite raw-bound quantitative records; F-ID selection and server-side rendering."""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Mapping
from dataclasses import asdict, replace
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

from app.generation import (
    cathode_surface,
    concentration_counterexample,
    conductivity_explanation,
    pure_concentration,
    sei_sufficiency,
    solubility_limit,
    solvation_trends,
    threshold_scope,
)
from app.generation import cell_solution_conditions as cell_conditions
from app.generation import oxidation_comparison as oxidation
from app.generation.answer_facts import SOURCE_TYPE, VERSION, Bundle
from app.generation.conductivity_order import PATTERN as CONDUCTIVITY_ORDER
from app.generation.conductivity_order import parse as parse_conductivity_order
from app.generation.conductivity_order import view as conductivity_view
from app.generation.ether_identity import BASE as ETHER_BASE
from app.generation.ether_identity import PATTERN as ETHER_IDENTITIES
from app.generation.ether_identity import parse as parse_ether_identities
from app.generation.fact_types import Fact, FactPatternError, SourceView, Value
from app.generation.potential_method import PATTERN as POTENTIAL_METHOD
from app.generation.potential_method import PREPARATION as POTENTIAL_PREPARATION
from app.generation.potential_method import parse as parse_potential_method
from app.generation.providers import Evidence, GenerationOutputError
from app.generation.resistance_table import TABLE as RESISTANCE_TABLE
from app.generation.resistance_table import parse as parse_resistance_table
from app.generation.reviewed_glyphs import ReviewedGlyphView
from app.retrieval.source_reference import reference

POLICY = 'quantitative_source_binding_v0.1'
BEST_CE_GLYPHS = (Path(__file__).resolve().parents[1] / 'resources/reviewed_best_ce_glyph_aliases_v01.json',
                  '3ab2492d50293918f9bfa3413f1de2f98726e38e9bd139f4e951a664609168c5')
N = r'\d+(?:\.\d+)?'
SIGNED = rf'[−-]?{N}'
RATIO = rf'{N}/{N}'
CODE = r'[A-Z][A-Za-z0-9]{0,24}'
ION = r'[A-Z][a-z]?\s*\+'
MU = r'[μµ][A-Z][a-z]?\s*\+'
ENERGY_UNIT = r'(?:kJ|J)\s*mol[−-]1'
CAP_UNIT = r'mA\s*h\s*g[−-]1'
BAD_SOURCE = re.compile(r'\b(?:previous|prior|earlier|hypothes\w*|may|might|could|no|not|never|without|proposed|future)\b', re.I)
FUNCTION_WORDS = set(('по статье в как какой какая какие каков каковы каким при и с к от до для его их '
                      'авторы авторами установленный получены исследовали использовали изменяется переходе '
                      'самого качестве что проверки общей результаты при').split())
VOCABULARY = {
    'solvation_trends': set('влияют сольватирующая способность растворителя концентрация соли на'.split()),
    'cathode_surface': set('изменения морфологии состава поверхностной плёнки пленки наблюдали после циклирования'.split()),
    'oxidation_comparison': set('фторирование повлияло на устойчивость электролита окислению данным lsv float test'.split()),
    'cell_solution_conditions': set('концентрации смеси растворителей применяли сравнительных испытаниях'.split()),
    'threshold': set('пороговый порогового диапазон подавления совместной интеркаляции растворителем'.split()),
    'ratio_reactions': set('реакция реакции графита графите соотношения соотношении соль растворитель'.split()),
    'formulation_count': set('сколько электролитных составов показатель нормальной интеркаляции корреляции'.split()),
    'initial_capacity_ce': set('начальная разрядная ёмкость емкость кулоновская эффективность полуячейки'.split()),
    'full_capacity_retention': set('начальная удельная ёмкость емкость сохранность ёмкости емкости полной '
                                  'ячейки повышенном верхнем напряжении'.split()),
    'resistance_before_after': set('изменились сопротивления полуячейках после предварительных циклов'.split()),
    'conductivity_order': set('порядок ионной проводимости растворов исследованных фторированных эфирах'.split()),
    'best_initial_ce': set('электролит показал наилучшие результаты полуячейке какова начальная '
                           'кулоновская эффективность'.split()),
    'descriptor_definition': set('параметр предложили количественного дескриптора интеркаляции '
                                 'графит каков термодинамический смысл'.split()),
    'ether_identity': set('фторированных диалкиловых эфира исследовались какова степень '
                          'фторирования относительно'.split()),
    'potential_method': set('экспериментально оценивали относительно какого состава задавали нулевое значение'.split()),
}
THRESHOLD = re.compile(rf'(?:We found|We identified|We established) a threshold of (?P<symbol>{MU}) at '
    rf'(?P<low>{SIGNED})\s*[–−-]\s*(?P<high>{SIGNED})\s*(?P<unit>{ENERGY_UNIT}) that dominantly determined whether '
    rf'(?P<ion>{ION}) intercalation or (?P<ion2>{ION})[–−-]solvent cointercalation occurred', re.I)
FIRST = re.compile(rf'in dilute (?P<salt>{CODE})/(?P<solvent>{CODE}) \((?P<ratio>{RATIO}) by mol\) '
    rf'with low (?P<symbol>{MU}) \((?P<mu>{SIGNED})\s*(?P<unit>{ENERGY_UNIT})\), '
    rf'(?P<state>(?P<ion>{ION})[–−-]solvent cointercalation) occurred at '
    rf'(?P<vlo>{N})\s*[–−-]\s*(?P<vhi>{N}) V', re.I)
SECOND = re.compile(rf'\. At an intermediate concentration \((?P<ratio>{RATIO}) by mol\) with intermediate '
    rf'(?P<symbol>{MU}) \((?P<mu>{SIGNED})\s*(?P<unit>{ENERGY_UNIT})\), we observed '
    rf'(?P<state>both (?P<ion>{ION}) intercalation \((?P<vlo>{N})\s*[–−-]\s*(?P<vhi>{N}) V\) and '
    rf'(?P<ion2>{ION})[–−-]solvent cointercalation \(sloping curve in (?P<clo>{N})\s*[–−-]\s*(?P<chi>{N}) V\))', re.I)
THIRD = re.compile(rf'\. In contrast, at a high concentration \((?P<ratio>{RATIO}) by mol\) with high '
    rf'(?P<symbol>{MU}) \((?P<mu>{SIGNED})\s*(?P<unit>{ENERGY_UNIT})\), we observed '
    rf'(?P<state>(?P<ion>{ION}) intercalation)', re.I)
COUNT = re.compile(rf'we studied (?P<count>\d+) (?P<objects>electrolyte formulations) '
    rf'with different solvents and salt concentrations.{{0,180}}?To judge which reaction '
    rf'\((?P<ion>{ION}) intercalation or (?P<ion2>{ION})[–−-]solvent cointercalation\) predominantly occurred, '
    rf'we extracted the (?P<indicator>reversible capacities) in a voltage range of '
    rf'(?P<low>{N})\s*[–−-]\s*(?P<high>{N})\s*(?P<unit>V) for (?P<cell>graphite\|[A-Z][a-z]?) cells, '
    rf'which are fully attributed to (?P<ion3>{ION}) intercalation', re.I)
INITIAL = re.compile(rf'(?:an?|a) initial discharge capacity of (?P<capacity>{N})\s*(?P<unit>{CAP_UNIT}) '
    rf'with (?:an?|a) initial (?P<ce_name>CE|coulombic efficiency) of (?P<ce>{N})% '
    rf'is obtained in the (?P<label>{CODE}) cell', re.I)
FULL = re.compile(rf'the cell in (?P<label>{CODE}) favors (?:an?|a) initial capacity of '
    rf'(?P<approx>~|≈|about |approximately )?(?P<capacity>{N})\s*(?P<unit>{CAP_UNIT}) and capacity retention '
    rf'of (?P<retention>{N})% after (?P<cycles>\d+) cycles', re.I)
CELL_FRAME = re.compile(rf'(?P<cell>{CODE}[/|‖]{CODE})\s+(?P<kind>half|full)[ -]cells?', re.I)
BEST_CE = re.compile(rf'The (?P<label>{CODE}) exhibits (?P<ce_rank>highest initial CE) '
    rf'\((?P<approx>~|≈|about |approximately )?(?P<ce>{N})(?P<percent>%)\) and '
    rf'(?P<cycle_rank>best cycle performance) (?P<comparison>among several cases)')
DESCRIPTOR = re.compile(rf'Herein, we report the (?P<ion>{ION}) (?P<parameter>chemical potential) '
    rf'\((?P<symbol>{MU})\) in electrolytes as a (?P<role>quantitative factor that strongly correlates with '
    rf'the (?P<behavior_ion>{ION}) intercalation behavior of graphite negative electrodes)\. '
    rf'By definition, (?P<symbol2>{MU}) is the (?P<definition>partial molar Gibbs free energy of '
    rf'(?P<definition_ion>{ION})), which quantitatively describes the (?P<meaning>thermodynamic stability '
    rf'of (?P<meaning_ion>{ION}) in the electrolyte)\. Specifically, '
    rf'(?P<interpretation>(?P<higher>higher) \((?P<lower>lower)\) (?P<symbol3>{MU}) means '
    rf'(?P<higher_state>unstable) \((?P<lower_state>stable)\) (?P<state_ion>{ION}) in the '
    rf'(?P<environment>solvation environment))\.')


def _norm(text: str) -> str:
    return unicodedata.normalize('NFKC', text)


def _symbol(value: str) -> str:
    return re.sub(r'\s+', '', value).replace('µ', 'μ')


def _decimal(value: str) -> Decimal:
    return Decimal(value.replace('−', '-'))


def family(question: str) -> str | None:
    q = _norm(question).casefold()
    if ('концентрации' in q and 'смеси растворителей' in q and 'сравнительных испытаниях' in q
            and re.search(cell_conditions.TAIL, q)):
        return 'cell_solution_conditions'
    if solubility_limit.QUERY.search(_norm(question)):
        return 'solubility_limit'
    if conductivity_explanation.QUERY.search(_norm(question)):
        return 'conductivity_explanation'
    if pure_concentration.QUERY.search(_norm(question)):
        return 'pure_concentration'
    if threshold_scope.QUERY.search(_norm(question)):
        return 'threshold_scope'
    if sei_sufficiency.QUERY.search(_norm(question)):
        return 'sei_sufficiency'
    if concentration_counterexample.QUERY.search(_norm(question)):
        return 'concentration_counterexample'
    if re.search(r'почему|объясня|доказыва|достаточ|гарант', q):
        return None
    if 'сольватирующая способность' in q and 'концентрация соли' in q:
        return 'solvation_trends'
    if 'морфологии' in q and 'поверхностной' in q and ('плёнки' in q or 'пленки' in q):
        return 'cathode_surface'
    if 'фторирование' in q and 'окислению' in q and 'lsv' in q and 'float-test' in q:
        return 'oxidation_comparison'
    if 'экспериментально' in q and 'нулев' in q:
        return 'potential_method'
    if 'диалкилов' in q and 'степень' in q and 'фторирован' in q:
        return 'ether_identity'
    if 'дескриптор' in q and 'термодинамическ' in q:
        return 'descriptor_definition'
    if 'порогов' in q and 'диапазон' in q:
        return 'threshold'
    if 'реакци' in q and 'соотношени' in q:
        return 'ratio_reactions'
    if 'сколько' in q and 'состав' in q and 'показател' in q:
        return 'formulation_count'
    if 'порядок' in q and 'проводимости' in q:
        return 'conductivity_order'
    if 'сопротивлен' in q:
        return 'resistance_before_after'
    if 'наилучш' in q and 'эффективност' in q:
        return 'best_initial_ce'
    if 'ёмкость' in q or 'емкость' in q:
        if 'сохранност' in q and 'полной' in q:
            return 'full_capacity_retention'
        if 'кулоновск' in q:
            return 'initial_capacity_ce'
    return None


def _query(question: str, kind: str) -> dict[str, Any]:
    cite = reference(question)
    if cite is None or re.fullmatch(re.escape(cite.surname) + r'\s*\(' + cite.year + r'\)',
                                    question[cite.start:cite.end]) is None:
        raise FactPatternError('single_surname_year_reference_required')
    q = _norm(question[:cite.start] + ' ' + question[cite.end:])
    if kind == 'solubility_limit':
        body = re.sub(r'^\s*(?:По\s+статье\s*)?:\s*', '', q, flags=re.I).strip()
        match = solubility_limit.QUERY.fullmatch(body)
        if match is None:
            raise FactPatternError('exact_conductivity_solubility_exclusion_question_required')
        return {key: match[key] for key in ('salt', 'base', 'concentration', 'query_unit')}
    if kind == 'conductivity_explanation':
        body = re.sub(r'^\s*(?:По\s+статье\s*)?:\s*', '', q, flags=re.I).strip()
        match = conductivity_explanation.QUERY.fullmatch(body)
        if match is None:
            raise FactPatternError('exact_salt_solvent_conductivity_explanation_question_required')
        return {key: match[key] for key in ('salt', 'higher', 'lower')}
    if kind == 'pure_concentration':
        body = re.sub(r'^\s*(?:По\s+статье\s*)?:\s*', '', q, flags=re.I).strip()
        match = pure_concentration.QUERY.fullmatch(body)
        if match is None:
            raise FactPatternError('exact_pure_solvent_mass_concentration_question_required')
        return {key: match[key] for key in ('higher', 'lower', 'temperature')}
    if kind == 'threshold_scope':
        body = re.sub(r'^\s*(?:По\s+статье\s*)?:\s*', '', q, flags=re.I).strip()
        match = threshold_scope.QUERY.fullmatch(body)
        if match is None:
            raise FactPatternError('exact_threshold_universal_invariance_question_required')
        return {'symbol': _symbol(match['symbol'])}
    if kind == 'sei_sufficiency':
        body = re.sub(r'^\s*(?:По\s+статье\s*)?:\s*', '', q, flags=re.I).strip()
        match = sei_sufficiency.QUERY.fullmatch(body)
        if match is None:
            raise FactPatternError('exact_anion_sei_sufficiency_question_required')
        return {'anion': match['anion']}
    if kind == 'concentration_counterexample':
        body = re.sub(r'^\s*(?:По\s+статье\s*)?:\s*', '', q, flags=re.I).strip()
        match = concentration_counterexample.QUERY.fullmatch(body)
        if match is None:
            raise FactPatternError('exact_concentration_nonuniversality_counterexample_question_required')
        return {'salt': match['salt']}
    if kind == 'cell_solution_conditions':
        if not re.search(cell_conditions.TAIL, q, re.I):
            raise FactPatternError('exact_methodological_nontransfer_caveat_required')
        q = re.sub(cell_conditions.TAIL, ' ', q, flags=re.I)
    if re.search(r'\b(?:не|нет|без|доказан|подтверждён|универсаль\w*|любых|всех)\b', q, re.I):
        raise FactPatternError('unsupported_negative_epistemic_or_universal_constraint')
    params: dict[str, Any] = {}
    known: list[str] = []
    if kind == 'solvation_trends':
        symbols = re.findall(MU, q)
        if len(symbols) != 1:
            raise FactPatternError('one_explicit_solvation_potential_symbol_required')
        params['symbol'] = _symbol(symbols[0])
        known.extend(symbols)
    elif kind == 'cathode_surface':
        electrodes = re.findall(rf'морфологии\s+({CODE})(?!\w)', q)
        labels = re.findall(rf'\bв\s+({CODE})(?!\w)', q)
        if len(electrodes) != 1 or len(labels) != 1:
            raise FactPatternError('one_cathode_and_one_cycling_electrolyte_required')
        params.update(electrode=electrodes[0], label=labels[0])
        known.extend([electrodes[0], labels[0]])
    elif kind == 'oxidation_comparison':
        if not re.search(r'\bLSV\s+и\s+float-test\b', q, re.I):
            raise FactPatternError('both_lsv_and_float_comparison_required')
    elif kind == 'cell_solution_conditions':
        salts = re.findall(rf'концентрации\s+({CODE})(?!\w)', q)
        cells = re.findall(rf'({CODE})/({CODE})', q)
        if len(salts) != 1 or len(cells) != 1:
            raise FactPatternError('one_salt_and_one_comparative_cell_required')
        params.update(salt=salts[0], cell='/'.join(cells[0]))
        known.extend([salts[0], *cells[0]])
    elif kind in ('threshold', 'ratio_reactions', 'formulation_count'):
        symbols = re.findall(MU, q)
        ions = re.findall(ION, q)
        params['ion'] = _symbol(ions[0]) if ions else None
        if symbols:
            params['symbol'] = _symbol(symbols[0])
            params['ion'] = params['symbol'][1:]
        if (len({_symbol(s) for s in symbols}) > 1
                or any(_symbol(ion) != params['ion'] for ion in ions)):
            raise FactPatternError('conflicting_query_ion_selectors')
        known.extend(symbols + ions)
        if kind == 'ratio_reactions':
            codes = re.findall(rf'({CODE})/({CODE})', q)
            ratios = re.findall(RATIO, q)
            if len(codes) != 1 or len(ratios) != 3 or len(set(ratios)) != 3:
                raise FactPatternError('one_electrolyte_and_three_unique_molar_ratios_required')
            params.update(salt=codes[0][0], solvent=codes[0][1], ratios=ratios)
            known.extend([*codes[0], *ratios])
        elif params['ion'] is None:
            raise FactPatternError('explicit_ion_required')
    elif kind == 'potential_method':
        symbols = re.findall(MU, q)
        if len(symbols) != 1:
            raise FactPatternError('one_explicit_potential_symbol_required')
        params['symbol'] = _symbol(symbols[0])
        known.extend(symbols)
    elif kind == 'ether_identity':
        bases = re.findall(rf'относительно\s+({CODE})\b', q)
        counts = re.findall(r'\bтри\b', q, re.I)
        if len(bases) != 1 or len(counts) != 1:
            raise FactPatternError('three_ethers_and_one_explicit_reference_base_required')
        params['base'] = bases[0]
        known.extend([bases[0], counts[0]])
    elif kind == 'descriptor_definition':
        ions = re.findall(ION, q)
        if len(ions) != 1:
            raise FactPatternError('one_explicit_descriptor_ion_required')
        params['ion'] = _symbol(ions[0])
        known.extend(ions)
    elif kind == 'best_initial_ce':
        cells = re.findall(rf'({CODE})/({CODE})', q)
        if len(cells) != 1:
            raise FactPatternError('one_explicit_half_cell_required')
        params['cell'] = '/'.join(cells[0])
        known.extend(cells[0])
    elif kind == 'conductivity_order':
        selector = re.findall(rf'(?<![\w.])({N})\s+(M)\s+растворов\s+({CODE})(?!\w)', q)
        if len(selector) != 1 or Decimal(selector[0][0]) <= 0:
            raise FactPatternError('one_positive_molar_concentration_and_salt_required')
        concentration, unit, salt = selector[0]
        params.update(concentration=concentration, query_unit=unit, salt=salt)
        known.extend(selector[0])
    elif kind == 'resistance_before_after':
        cells = re.findall(rf'({CODE})/({CODE})', q)
        labels = re.findall(rf'\bс\s+({CODE})\s+и\s+({CODE})\b', q)
        cycle = re.findall(r'после\s+(\d+|одного|двух|трёх|трех|четырёх|четырех)\s+предварительных\s+циклов', q, re.I)
        if len(cells) != 1 or len(labels) != 1 or len(set(labels[0])) != 2 or len(cycle) != 1:
            raise FactPatternError('one_half_cell_two_distinct_labels_and_cycle_count_required')
        numbers = {'одного': '1', 'двух': '2', 'трёх': '3', 'трех': '3', 'четырёх': '4', 'четырех': '4'}
        count = numbers.get(cycle[0].casefold(), cycle[0])
        if int(count) < 1:
            raise FactPatternError('positive_pre_cycle_count_required')
        params.update(cell='/'.join(cells[0]), labels=list(labels[0]), cycles=count)
        known.extend([*cells[0], *labels[0], cycle[0]])
    else:
        cell = re.findall(rf'({CODE})/({CODE})', q)
        label = re.findall(rf'\bс\s+({CODE})\b', q)
        if len(cell) != 1 or len(label) != 1:
            raise FactPatternError('one_cell_and_one_electrolyte_label_required')
        params.update(cell='/'.join(cell[0]), label=label[0])
        known.extend([*cell[0], label[0]])
    # Mask only explicitly parsed selectors, never arbitrary Latin tokens or numeric conditions.
    for token in sorted(set(known), key=len, reverse=True):
        q = re.sub(r'(?<!\w)' + re.escape(token) + r'(?!\w)', ' ', q)
    unknown = sorted(set(re.findall(r'[^\W_]+', q.casefold())) - FUNCTION_WORDS - VOCABULARY[kind])
    if unknown:
        raise FactPatternError('unrecognized_query_tokens:' + ','.join(unknown))
    return params


def _current(view: SourceView, start: int, end: int) -> bool:
    refs = re.search(r'(?im)^\s*(?:references|bibliography)\s*$', view.source.text)
    if refs and view.anchor(start, end).start >= refs.start():
        return False
    lead = re.split(r'[.!?;]\s+', view.text[max(0, start - 200):start])[-1]
    return BAD_SOURCE.search(lead + view.text[start:end]) is None


def _fact(view: SourceView, match: re.Match[str], prop: str, value: str, unit: str | None,
          *, sample: str | None = None, conditions: tuple[str, ...] = (), support_end: int | None = None) -> Fact:
    return Fact(prop, view.value(match, sample) if sample else None, view.value(match, value),
                view.value(match, unit) if unit else None, 'reported_quantitative_observation', None,
                {key: view.value(match, key) for key in conditions}, 'reported',
                view.anchor(match.start(), support_end or match.end()), ('temperature',) if 'temperature' not in conditions else ())


def _parse(kind: str, source: Evidence, params: dict[str, Any]) -> list[tuple[list[Fact], str]]:
    view = (ReviewedGlyphView(source, catalogue_binding=solubility_limit.GLYPHS) if kind == 'solubility_limit' else
            conductivity_explanation.view(source) if kind == 'conductivity_explanation' else
            pure_concentration.view(source) if kind == 'pure_concentration' else
            cathode_surface.view(source) if kind == 'cathode_surface' else
            oxidation.view(source) if kind == 'oxidation_comparison' else
            cell_conditions.view(source) if kind == 'cell_solution_conditions' else
            ReviewedGlyphView(source, catalogue_binding=BEST_CE_GLYPHS) if kind == 'best_initial_ce' else
            conductivity_view(source) if kind == 'conductivity_order' else
            ReviewedGlyphView(source) if kind in ('initial_capacity_ce', 'full_capacity_retention',
                                                  'resistance_before_after', 'best_initial_ce')
            else SourceView(source, join_soft_hyphen_lines=True))
    result = []
    if kind == 'solubility_limit':
        limit_identities = list(solubility_limit.IDENTITY.finditer(view.text))
        limit_comparisons = list(solubility_limit.PATTERN.finditer(view.text))
        if len(limit_identities) > 1 or len(limit_comparisons) > 1:
            raise FactPatternError('ambiguous_solubility_limit_identity_or_comparison')
        if limit_identities and limit_comparisons:
            for match in (limit_identities[0], limit_comparisons[0]):
                lead = re.split(r'[.!?;]\s+', view.text[max(0, match.start() - 200):match.start()])[-1]
                refs = re.search(r'(?im)^\s*(?:references|bibliography)\s*$', source.text)
                if ((refs and view.support(match).start >= refs.start()) or BAD_SOURCE.search(lead + match.group())
                        or re.search(r'\b(?:previously|literature|hypothetical|unmeasured|references|bibliography)\b', lead, re.I)):
                    return []
            result.append(solubility_limit.parse(view, limit_identities[0], limit_comparisons[0],
                salt=params['salt'], base=params['base'], concentration=params['concentration']))
    elif kind == 'conductivity_explanation':
        explanation_candidates = list(conductivity_explanation.PATTERN.finditer(view.text))
        if len(explanation_candidates) > 1:
            raise FactPatternError('ambiguous_conductivity_explanation')
        for match in explanation_candidates:
            lead = re.split(r'[.!?;]\s+', view.text[max(0, match.start() - 200):match.start()])[-1]
            status = match.group()
            for field in ('ability', 'modal', 'role'):
                status = status.replace(match[field], 'bound_author_possible_explanation')
            refs = re.search(r'(?im)^\s*(?:references|bibliography)\s*$', source.text)
            if ((refs and view.support(match).start >= refs.start()) or BAD_SOURCE.search(lead + status)
                    or re.search(r'\b(?:previously|literature|hypothetical|unmeasured|references|bibliography)\b', lead, re.I)):
                continue
            result.append(conductivity_explanation.parse(cast(ReviewedGlyphView, view), match, salt=params['salt'],
                higher=params['higher'], lower=params['lower']))
    elif kind == 'pure_concentration':
        pure_frames = list(pure_concentration.FRAME.finditer(view.text))
        pure_comparisons = list(pure_concentration.PATTERN.finditer(view.text))
        if len(pure_frames) > 1 or len(pure_comparisons) > 1:
            raise FactPatternError('ambiguous_pure_solvent_frame_or_comparison')
        if pure_frames and pure_comparisons:
            for match in (pure_frames[0], pure_comparisons[0]):
                lead = re.split(r'[.!?;]\s+', view.text[max(0, match.start() - 200):match.start()])[-1]
                status = match.group()
                if match is pure_comparisons[0]:
                    status = status.replace(match['modal'], 'bound_possible_liquid_contraction')
                refs = re.search(r'(?im)^\s*(?:references|bibliography)\s*$', source.text)
                if ((refs and view.support(match).start >= refs.start()) or BAD_SOURCE.search(lead + status)
                        or re.search(r'\b(?:previously|literature|hypothetical|unmeasured|references|bibliography)\b', lead, re.I)):
                    return []
            result.append(pure_concentration.parse(view, pure_frames[0], pure_comparisons[0],
                higher=params['higher'], lower=params['lower'], temperature=params['temperature']))
    elif kind == 'threshold_scope':
        threshold_candidates = list(threshold_scope.PATTERN.finditer(view.text))
        if len(threshold_candidates) > 1:
            raise FactPatternError('ambiguous_threshold_applicability_and_shift_caveat')
        for match in threshold_candidates:
            lead = re.split(r'[.!?;]\s+', view.text[max(0, match.start() - 200):match.start()])[-1]
            status = match.group().replace(match['modal'], 'bound_possible_threshold_shift')
            refs = re.search(r'(?im)^\s*(?:references|bibliography)\s*$', source.text)
            if ((refs and view.support(match).start >= refs.start()) or BAD_SOURCE.search(lead + status)
                    or re.search(r'\b(?:previously|literature|hypothetical|unmeasured|references|bibliography)\b', lead, re.I)):
                continue
            result.append(threshold_scope.parse(view, match, symbol=params['symbol']))
    elif kind == 'sei_sufficiency':
        matches = [list(pattern.finditer(view.text)) for pattern in (sei_sufficiency.PROPOSAL, sei_sufficiency.CONTRIBUTION,
                                                                   sei_sufficiency.OBSERVATIONS, sei_sufficiency.CONCLUSION)]
        if any(len(rows) > 1 for rows in matches):
            raise FactPatternError('ambiguous_sei_proposal_observation_or_conclusion')
        if all(matches):
            proposal, contribution, observations, conclusion = (rows[0] for rows in matches)
            for match in (proposal, contribution, observations, conclusion):
                lead = re.split(r'[.!?;]\s+', view.text[max(0, match.start() - 200):match.start()])[-1]
                status = match.group()
                if match is observations:
                    status = status.replace(observations['no_change'], 'bound_non_change')
                    status = status.replace(observations['not_suppressed'], 'bound_non_suppression')
                if match is conclusion:
                    status = status.replace(conclusion['limitation'], 'bound_modal_limitation')
                refs = re.search(r'(?im)^\s*(?:references|bibliography)\s*$', source.text)
                if ((refs and view.support(match).start >= refs.start()) or BAD_SOURCE.search(lead + status)
                        or re.search(r'\b(?:previously|literature|hypothetical|unmeasured|references|bibliography)\b', lead, re.I)):
                    return []
            result.append(sei_sufficiency.parse(view, proposal, contribution, observations, conclusion, anion=params['anion']))
    elif kind == 'concentration_counterexample':
        bases = list(concentration_counterexample.BASIS.finditer(view.text))
        examples = list(concentration_counterexample.PATTERN.finditer(view.text))
        if len(bases) > 1 or len(examples) > 1:
            raise FactPatternError('ambiguous_counterexample_reference_or_comparison')
        if bases and examples:
            for match in (bases[0], examples[0]):
                lead = re.split(r'[.!?;]\s+', view.text[max(0, match.start() - 200):match.start()])[-1]
                if (not _current(view, match.start(), match.end()) or re.search(
                        r'\b(?:previously|literature|hypothetical|unmeasured|references|bibliography)\b', lead, re.I)):
                    return []
            result.append(concentration_counterexample.parse(view, bases[0], examples[0], salt=params['salt']))
    elif kind == 'solvation_trends':
        matches = [list(pattern.finditer(view.text)) for pattern in
                   (solvation_trends.PREPARATION, solvation_trends.TREND, solvation_trends.CORRELATION)]
        if any(len(rows) > 1 for rows in matches):
            raise FactPatternError('ambiguous_solvation_preparation_trend_or_correlation')
        if all(matches):
            preparation, trend, correlation = (rows[0] for rows in matches)
            for match in (preparation, trend, correlation):
                lead = re.split(r'[.!?;]\s+', view.text[max(0, match.start() - 200):match.start()])[-1]
                if (not _current(view, match.start(), match.end()) or re.search(
                        r'\b(?:previously|literature|hypothetical|unmeasured|references|bibliography)\b', lead, re.I)):
                    return []
            result.append(solvation_trends.parse(view, preparation, trend, correlation, symbol=params['symbol']))
    elif kind == 'cathode_surface':
        matches = [list(pattern.finditer(view.text)) for pattern in (cathode_surface.FRAME, cathode_surface.SEM, cathode_surface.XPS)]
        matches.append([m for m in cathode_surface.CAPTION.finditer(view.text) if m['electrode'] == params['electrode']])
        if any(len(rows) > 1 for rows in matches):
            raise FactPatternError('ambiguous_cathode_surface_frame_sem_or_xps')
        if all(matches):
            frame, sem, xps, caption = (rows[0] for rows in matches)
            for match in (frame, sem, xps, caption):
                lead = re.split(r'[.!?;]\s+', view.text[max(0, match.start() - 200):match.start()])[-1]
                current = _current(view, match.start(), match.end())
                if match is xps:
                    refs = re.search(r'(?im)^\s*(?:references|bibliography)\s*$', source.text)
                    # Only the already-bound comparison group is exempt from the generic status-token veto.
                    status = lead + match.group().replace('than ' + xps['o_reference'], 'than comparison_group')
                    current = (not refs or view.support(match).start < refs.start()) and BAD_SOURCE.search(status) is None
                if (not current or re.search(
                        r'\b(?:previously|literature|hypothetical|unmeasured|references|bibliography)\b', lead, re.I)):
                    return []
            result.append(cathode_surface.parse(view, frame, sem, xps, caption, electrode=params['electrode'], label=params['label']))
    elif kind == 'oxidation_comparison':
        matches = [list(pattern.finditer(view.text)) for pattern in (oxidation.BASE, oxidation.METHOD,
                                                                   oxidation.HEAD, oxidation.RESULT)]
        if any(len(rows) > 1 for rows in matches):
            raise FactPatternError('ambiguous_oxidation_base_method_head_or_results')
        if all(matches):
            base, method, head, observed = (rows[0] for rows in matches)
            formulations = [m for m in oxidation.FORMULATION.finditer(view.text) if m['label'] == observed['label']]
            if len(formulations) != 1 or len(re.findall(r'\b' + re.escape(observed['label']) + ':', view.text)) != 1:
                raise FactPatternError('missing_or_ambiguous_oxidation_formulation')
            scope_matches = [base, method, head, observed, formulations[0]]
            for match in scope_matches:
                lead = re.split(r'[.!?;]\s+', view.text[max(0, match.start() - 200):match.start()])[-1]
                if (not _current(view, match.start(), match.end()) or re.search(
                        r'\b(?:previously|literature|hypothetical|unmeasured|references|bibliography)\b', lead, re.I)):
                    return []
            result.append(oxidation.parse(view, base, formulations[0], method, head, observed))
    elif kind == 'cell_solution_conditions':
        bodies = list(cell_conditions.BODY.finditer(view.text))
        captions = list(cell_conditions.CAPTION.finditer(view.text))
        if len(bodies) > 1 or len(captions) > 1:
            raise FactPatternError('ambiguous_cell_solution_body_or_caption')
        if bodies and captions:
            for match in (bodies[0], captions[0]):
                lead = re.split(r'[.!?;]\s+', view.text[max(0, match.start() - 200):match.start()])[-1]
                # PDF reading order places the complete figure caption after the bibliography.
                # Its explicit (a)/(b) grammar and local status remain mandatory.
                if ((match is bodies[0] and not _current(view, match.start(), match.end()))
                        or BAD_SOURCE.search(lead + match.group()) or re.search(
                        r'\b(?:previously|literature|hypothetical|unmeasured|references|bibliography)\b', lead, re.I)):
                    return []
            result.append(cell_conditions.parse(view, bodies[0], captions[0], salt=params['salt'], cell=params['cell']))
    elif kind == 'threshold':
        for m in THRESHOLD.finditer(view.text):
            if (not _current(view, m.start(), m.end()) or _symbol(m['symbol']) != params.get('symbol')
                    or _symbol(m['ion']) != params['ion'] or _symbol(m['ion2']) != params['ion']
                    or _decimal(m['low']) >= _decimal(m['high'])):
                continue
            facts = [_fact(view, m, 'threshold_' + key, key, 'unit', sample='symbol') for key in ('low', 'high')]
            text = (f"В рассмотренных авторами электролитах пороговый диапазон {params['symbol']}: "
                    f"{m['low']}–{m['high']} {m['unit']}. Он разделяет режимы интеркаляции {params['ion']} "
                    f"и совместной интеркаляции {params['ion']} с растворителем.")
            result.append((facts, text))
    elif kind == 'ratio_reactions':
        for first in FIRST.finditer(view.text):
            second = SECOND.match(view.text, first.end())
            third = THIRD.match(view.text, second.end()) if second else None
            if second is None or third is None or not _current(view, first.start(), third.end()):
                continue
            if (first['salt'], first['solvent']) != (params['salt'], params['solvent']):
                continue
            rows = (first, second, third)
            if [m['ratio'] for m in rows] != params['ratios'] or len({_symbol(m['symbol']) for m in rows}) != 1:
                continue
            if (not _decimal(first['mu']) < _decimal(second['mu']) < _decimal(third['mu'])
                    or len({re.sub(r'\s+', '', m['unit']) for m in rows}) != 1):
                continue
            ion = _symbol(first['ion'])
            if any(_symbol(m['ion']) != ion for m in rows) or _symbol(second['ion2']) != ion:
                continue
            if any(_symbol(m['symbol'])[1:] != ion for m in rows):
                continue
            sample = Value(first['salt'] + '/' + first['solvent'], view.anchor(first.start('salt'), first.end('solvent')))
            facts = [replace(_fact(view, m, 'reaction_at_molar_ratio', 'state', None,
                                   conditions=('ratio', 'mu', 'unit')), sample=sample) for m in rows]
            descriptions = (f'совместная интеркаляция {ion} с растворителем',
                            f'оба режима: интеркаляция {ion} и совместная интеркаляция с растворителем',
                            f'наблюдалась интеркаляция {ion}')
            text = f"{sample.text}, соль/растворитель (мольное соотношение): " + '; '.join(
                f"{m['ratio']} — {description} (μ: {m['mu']} {m['unit']})" for m, description in zip(rows, descriptions, strict=True)) + '.'
            result.append((facts, text))
    elif kind == 'formulation_count':
        for m in COUNT.finditer(view.text):
            if (not _current(view, m.start(), m.end()) or int(m['count']) < 1 or Decimal(m['low']) >= Decimal(m['high'])
                    or any(_symbol(m[k]) != params['ion'] for k in ('ion', 'ion2', 'ion3'))
                    or m['cell'].split('|')[-1] + '+' != params['ion']):
                continue
            facts = [_fact(view, m, 'formulation_count', 'count', 'objects'),
                     _fact(view, m, 'intercalation_indicator', 'indicator', None, sample='cell', conditions=('low', 'high', 'unit'))]
            text = (f"Авторы исследовали {m['count']} электролитных составов. Показатель интеркаляции {params['ion']}: "
                    f"обратимая ёмкость ячейки {m['cell']} в диапазоне {m['low']}–{m['high']} {m['unit']}; "
                    f"в этом диапазоне источник относит ёмкость к интеркаляции {params['ion']}.")
            result.append((facts, text))
    elif kind == 'potential_method':
        for match in POTENTIAL_METHOD.finditer(view.text):
            lead = re.split(r'[.!?;]\s+', view.text[max(0, match.start() - 200):match.start()])[-1]
            if (not _current(view, match.start(), match.end()) or re.search(
                    r'\b(?:previously|literature|hypothetical|unmeasured|references|bibliography)\b', lead, re.I)):
                continue
            preps = []
            for prep in POTENTIAL_PREPARATION.finditer(view.text, 0, match.start()):
                prep_lead = re.split(r'[.!?;]\s+', view.text[max(0, prep.start() - 200):prep.start()])[-1]
                if (_current(view, prep.start(), prep.end()) and not re.search(
                        r'\b(?:previously|literature|hypothetical|unmeasured|references|bibliography)\b', prep_lead, re.I)):
                    preps.append(prep)
            if not preps:
                continue
            if len({p.group() for p in preps}) != 1:
                raise FactPatternError('ambiguous_redox_additive_preparation')
            result.append(parse_potential_method(view, match, preps[-1], params['symbol']))
    elif kind == 'ether_identity':
        for match in ETHER_IDENTITIES.finditer(view.text):
            lead = re.split(r'[.!?;]\s+', view.text[max(0, match.start() - 200):match.start()])[-1]
            if (not _current(view, match.start(), match.end())
                    or re.search(r'\b(?:previously|literature|hypothetical|unmeasured|references|bibliography)\b', lead, re.I)):
                continue
            bases = [m for m in ETHER_BASE.finditer(view.text, 0, match.start()) if _current(view, m.start(), m.end())]
            if not bases:
                continue
            result.append(parse_ether_identities(view, match, bases[-1], params['base']))
    elif kind == 'descriptor_definition':
        for match in DESCRIPTOR.finditer(view.text):
            lead = re.split(r'[.!?;]\s+', view.text[max(0, match.start() - 200):match.start()])[-1]
            if (not _current(view, match.start(), match.end())
                    or re.search(r'\b(?:previously|literature|hypothetical|unmeasured)\b', lead, re.I)
                    or any(_symbol(match[key]) != params['ion'] for key in
                           ('ion', 'behavior_ion', 'definition_ion', 'meaning_ion', 'state_ion'))
                    or any(_symbol(match[key]) != 'μ' + params['ion'] for key in ('symbol', 'symbol2', 'symbol3'))):
                continue
            facts = [replace(_fact(view, match, prop, value, None, sample='symbol', conditions=conditions),
                             operation=operation, epistemic_status='source_reported_definition', unknown_fields=())
                     for prop, value, operation, conditions in (
                         ('descriptor_parameter', 'parameter', 'reported_source_descriptor', ('ion', 'role')),
                         ('thermodynamic_definition', 'definition', 'reported_thermodynamic_definition', ('meaning',)),
                         ('stability_interpretation', 'interpretation', 'reported_source_stability_interpretation',
                          ('higher', 'lower', 'higher_state', 'lower_state', 'environment')))]
            ion, symbol = params['ion'], _symbol(match['symbol'])
            text = (f'Авторы предложили химический потенциал {ion} в электролите ({symbol}) как количественный '
                    f'дескриптор интеркаляции {ion} в графит. По определению в источнике, это парциальная молярная '
                    f'энергия Гиббса {ion}, характеризующая термодинамическую устойчивость иона в электролите. '
                    f'При более высоком {symbol} авторы описывают ион в сольватационном окружении как неустойчивый, '
                    'при более низком — как устойчивый. Связь с интеркаляционным поведением графита '
                    'сформулирована в источнике как сильная корреляция.')
            result.append((facts, text))
    elif kind == 'best_initial_ce':
        for match in BEST_CE.finditer(view.text):
            lead = re.split(r'[.!?;]\s+', view.text[max(0, match.start() - 200):match.start()])[-1]
            if (not _current(view, match.start(), match.end()) or not 0 <= Decimal(match['ce']) <= 100
                    or re.search(r'\b(?:previously|literature|hypothetical|unmeasured)\b', lead, re.I)):
                continue
            frames = list(CELL_FRAME.finditer(view.text, max(0, match.start() - 2000), match.start()))
            if not frames:
                continue
            frame = frames[-1]
            owners = re.findall(rf'{CODE}[/|‖]{CODE}', view.text[frame.start():match.end()])
            if (frame['kind'].casefold() != 'half' or not _current(view, frame.start(), match.end())
                    or any(re.sub(r'[|‖]', '/', owner) != params['cell'] for owner in owners)):
                continue
            conditions = {'cell': view.value(frame, 'cell'), 'cell_kind': view.value(frame, 'kind'),
                'comparison': view.value(match, 'comparison'), 'ce_rank': view.value(match, 'ce_rank')}
            if match['approx']:
                conditions['approximation'] = view.value(match, 'approx')
            facts = [replace(_fact(view, match, 'highest_initial_coulombic_efficiency', 'ce', 'percent', sample='label'),
                             conditions=conditions),
                     replace(_fact(view, match, 'best_cycle_performance', 'cycle_rank', None, sample='label'),
                             conditions={key: conditions[key] for key in ('cell', 'cell_kind', 'comparison')})]
            approx = 'приблизительно ' if match['approx'] else ''
            text = (f"В сравнении электролитов для полуячейки {params['cell']} авторы выделяют {match['label']}: "
                    f"наибольшая начальная кулоновская эффективность — {approx}{match['ce']}%; "
                    'лучшие характеристики при циклировании среди рассмотренных вариантов. '
                    'Область вывода: электролиты, сравниваемые в статье, и указанная полуячейка.')
            result.append((facts, text))
    elif kind == 'conductivity_order':
        for match in CONDUCTIVITY_ORDER.finditer(view.text):
            lead = re.split(r'[.!?;]\s+', view.text[max(0, match.start() - 200):match.start()])[-1]
            if (not _current(view, match.start(), match.end())
                    or re.search(r'\b(?:previously|literature|hypothetical|unmeasured)\b', lead, re.I)):
                continue
            if not isinstance(view, ReviewedGlyphView):
                raise FactPatternError('reviewed_conductivity_view_required')
            result.append(parse_conductivity_order(view, match, salt=params['salt'], concentration=params['concentration']))
    elif kind == 'resistance_before_after':
        for table in RESISTANCE_TABLE.finditer(view.text):
            lead = re.split(r'[.!?;]\s+', view.text[max(0, table.start() - 200):table.start()])[-1]
            if (not _current(view, table.start(), table.end())
                    or re.search(r'\b(?:previously|literature|hypothetical|unmeasured)\b', lead, re.I)):
                continue
            frames = list(CELL_FRAME.finditer(view.text, max(0, table.start() - 5000), table.start()))
            if not frames:
                continue
            frame = frames[-1]
            if (not _current(view, frame.start(), frame.end()) or frame['kind'].casefold() != 'half'
                    or re.sub(r'[|‖]', '/', frame['cell']) != params['cell']):
                continue
            owners = re.findall(rf'{CODE}[/|‖]{CODE}', view.text[frame.start():table.end()])
            if any(re.sub(r'[|‖]', '/', owner) != params['cell'] for owner in owners):
                continue
            result.append(parse_resistance_table(view, table, frame, params['labels'], params['cycles']))
    else:
        pattern = INITIAL if kind == 'initial_capacity_ce' else FULL
        for m in pattern.finditer(view.text):
            if not _current(view, m.start(), m.end()) or m['label'] != params['label']:
                continue
            frames = list(CELL_FRAME.finditer(view.text, max(0, m.start() - 1800), m.start()))
            if not frames:
                continue
            frame = frames[-1]
            if not _current(view, frame.start(), m.end()):
                continue
            if re.sub(r'[|‖]', '/', frame['cell']) != params['cell'] or frame['kind'].lower() != (
                    'half' if kind == 'initial_capacity_ce' else 'full'):
                continue
            later = view.text[frame.end():m.start()]
            if BAD_SOURCE.search(later) or re.search(r'\b(?:another|different|other)\s+(?:cell|electrolyte)\b', later, re.I):
                continue
            facts = [_fact(view, m, 'initial_discharge_capacity', 'capacity', 'unit', sample='label')]
            scope_value = Value(frame['cell'], view.anchor(frame.start('cell'), frame.end('cell')))
            facts = [replace(facts[0], conditions={'cell': scope_value})]
            if kind == 'initial_capacity_ce':
                facts.append(replace(_fact(view, m, 'initial_coulombic_efficiency_percent', 'ce', None, sample='label'),
                                     conditions={'cell': scope_value}))
                text = (f"Полуячейка {params['cell']}, электролит {m['label']}: начальная разрядная ёмкость "
                        f"{m['capacity']} {m['unit']}, начальная кулоновская эффективность {m['ce']}%.")
            else:
                voltages = list(re.finditer(rf'upper voltage of (?P<voltage>{N}) (?P<vunit>V)', later, re.I))
                if len(voltages) != 1 or int(m['cycles']) < 1:
                    continue
                v = voltages[0]
                vstart = frame.end() + v.start('voltage')
                voltage = Value(v['voltage'], view.anchor(vstart, vstart + len(v['voltage'])), numeric_value=v['voltage'])
                facts = [replace(facts[0], conditions={'cell': scope_value, 'upper_voltage_V': voltage})]
                if isinstance(view, ReviewedGlyphView) and view.operations and m['approx']:
                    facts = [replace(facts[0], conditions={**facts[0].conditions,
                                                         'capacity_approximation': view.value(m, 'approx')})]
                facts.append(replace(_fact(view, m, 'capacity_retention_percent', 'retention', None,
                                           sample='label', conditions=('cycles',)),
                                     conditions={'cell': scope_value, 'cycles': view.value(m, 'cycles'), 'upper_voltage_V': voltage}))
                approx = 'приблизительно ' if m['approx'] else ''
                text = (f"Полная ячейка {params['cell']}, электролит {m['label']}, верхнее напряжение {v['voltage']} V: "
                        f"начальная ёмкость {approx}{m['capacity']} {m['unit']}; сохранность ёмкости "
                        f"{m['retention']}% после {m['cycles']} циклов.")
            result.append((facts, text))
    return result


def _record(kind: str, source: Evidence, facts: list[Fact], text: str) -> dict[str, Any]:
    result: dict[str, Any] = json.loads(json.dumps({'selection_id': 'F1', 'recipe': kind, 'citation_id': source.citation_id,
        'article_id': source.article_id, 'chunk_id': source.chunk_id, 'facts': [asdict(f) for f in facts],
        'arithmetic': None, 'allowed_claim': text, 'source_grammar': {'version': POLICY}}, ensure_ascii=False))
    return result


def prepare(question: str, sources: list[Evidence], metadata: object, *, answer_language: str = 'auto') -> Bundle | None:
    kind = family(question)
    if kind is None:
        return None
    diagnostics: list[dict[str, str]] = []

    def stop(reason: str) -> Bundle:
        return Bundle(False, reason, kind, [], [], [], diagnostics)

    if answer_language == 'en' or not re.search('[а-яё]', question, re.I):
        return stop('russian_quantitative_contract_not_requested')
    cite = reference(question)
    if (cite is None or not isinstance(metadata, Mapping) or metadata.get('resolved') is not True or not sources
            or metadata.get('matching_article_ids') != [metadata.get('article_id')]
            or metadata.get('surname') != cite.surname or str(metadata.get('year')) != cite.year
            or any(e.article_id != metadata.get('article_id') or e.source_type.endswith('_derived') for e in sources)):
        return stop('quantitative_reference_or_raw_scope_unresolved')
    try:
        params = _query(question, kind)
    except FactPatternError as exc:
        return stop(str(exc))
    candidates = []
    for source in sources:
        if source.source_type not in {'main_text', 'method', 'figure_caption', 'table_caption'}:
            continue
        try:
            parsed = _parse(kind, source, params)
        except FactPatternError as exc:
            diagnostics.append({'citation_id': source.citation_id, 'reason': str(exc)})
            if kind == 'solubility_limit':
                return stop('solubility_limit_or_existing_reviewed_glyph_binding_unresolved')
            if kind == 'conductivity_explanation':
                return stop('conductivity_explanation_or_reviewed_glyph_binding_unresolved')
            if kind == 'pure_concentration':
                return stop('pure_solvent_comparison_or_reviewed_glyph_binding_unresolved')
            if kind == 'threshold_scope':
                return stop('threshold_scope_or_modal_shift_binding_unresolved')
            if kind == 'sei_sufficiency':
                return stop('sei_sufficiency_observations_or_modal_limitation_binding_unresolved')
            if kind == 'concentration_counterexample':
                return stop('concentration_counterexample_or_reference_binding_unresolved')
            if kind == 'solvation_trends':
                return stop('solvation_trend_or_qualified_correlation_binding_unresolved')
            if kind == 'cathode_surface':
                return stop('cathode_surface_or_reviewed_glyph_binding_unresolved')
            if kind == 'oxidation_comparison':
                return stop('oxidation_comparison_or_reviewed_glyph_binding_unresolved')
            if kind == 'cell_solution_conditions':
                return stop('cell_solution_conditions_or_reviewed_glyph_binding_unresolved')
            if kind == 'ether_identity':
                return stop('ether_identity_or_fluorination_binding_unresolved')
            if kind == 'potential_method':
                return stop('potential_method_reference_or_zero_binding_unresolved')
            if kind == 'resistance_before_after':
                return stop('resistance_table_or_reviewed_glyph_binding_unresolved')
            if kind == 'conductivity_order':
                return stop('conductivity_order_or_reviewed_glyph_binding_unresolved')
            return stop('reviewed_pdf_glyph_binding_unresolved')
        if not parsed:
            diagnostics.append({'citation_id': source.citation_id, 'reason': 'source_grammar_missing_or_scope_unresolved'})
            if kind in ('initial_capacity_ce', 'full_capacity_retention'):
                view = SourceView(source)
                for match in re.finditer(r'initial (?:discharge )?capacity of.{0,100}?[\x00-\x08]', view.text, re.I):
                    anchor = view.anchor(match.start(), min(match.end() + 20, len(view.text)))
                    diagnostics.append({'citation_id': source.citation_id, 'reason': 'raw_quantity_encoding_marker',
                        'raw_start': str(anchor.start), 'raw_end': str(anchor.end), 'raw_excerpt': anchor.text,
                        'raw_sha256': anchor.raw_chunk_sha256})
        for facts, text in parsed:
            record = _record(kind, source, facts, text)
            if kind in ('initial_capacity_ce', 'full_capacity_retention', 'resistance_before_after', 'best_initial_ce'):
                provenance = (ReviewedGlyphView(source, catalogue_binding=BEST_CE_GLYPHS) if kind == 'best_initial_ce'
                              else ReviewedGlyphView(source)).provenance()
                if provenance:
                    record['source_grammar']['glyph_decoding'] = provenance
            if kind == 'resistance_before_after':
                record['source_grammar'].update(table_policy='six_column_resistance_table_v0.1',
                    unit_status='not_printed_in_table_no_inference', comparison='literal_decimal_order')
            if kind == 'conductivity_order':
                record['source_grammar'].update(order_policy='three_solvent_conductivity_order_v0.1',
                    concentration_unit_alias='M_equals_mol_dm_minus3_same_numeric_value', query_unit=params['query_unit'])
                provenance = conductivity_view(source).provenance()
                if provenance:
                    record['source_grammar']['glyph_decoding'] = provenance
            if kind == 'best_initial_ce':
                record['source_grammar']['ranking_policy'] = 'reported_half_cell_best_initial_ce_v0.1'
            if kind == 'descriptor_definition':
                record['source_grammar']['definition_policy'] = 'reported_descriptor_definition_v0.1'
                record['source_grammar']['claim_kind'] = 'source_definition_and_reported_correlation_no_numeric_measurement'
            if kind == 'ether_identity':
                record['source_grammar'].update(identity_policy='three_declared_diethoxyethane_identities_v0.1',
                    name_consistency='finite_ethoxy_locant_fluoro_prefix_count_not_general_structure_validation',
                    claim_kind='source_declared_chemical_identity_not_measurement')
            if kind == 'potential_method':
                record['source_grammar'].update(method_policy='electrode_potential_method_relative_zero_v0.1',
                    additive_unit='explicit_mmol_dm_minus3_no_shorthand_interpretation',
                    claim_kind='reported_method_assumption_relation_and_relative_zero_no_numeric_calculation')
            if kind == 'cell_solution_conditions':
                record['source_grammar'].update(conditions_policy='separate_cycling_conductivity_conditions_v0.1',
                    caveat='distinct_source_conditions_no_isolated_causal_attribution',
                    unit_policy='literal_mol_dm_minus3_no_conversion',
                    glyph_decoding=cell_conditions.view(source).provenance())
            if kind == 'oxidation_comparison':
                record['source_grammar'].update(comparison_policy='paired_lsv_float_observations_v0.1',
                    claim_kind='reported_comparison_not_isolated_causality_or_operating_limit',
                    approximate_lsv_limits=True, glyph_decoding=oxidation.view(source).provenance())
            if kind == 'cathode_surface':
                record['source_grammar'].update(surface_policy='cathode_sem_xps_observations_v0.1',
                    claim_kind='sem_observation_xps_assignment_and_author_interpretation',
                    oxygen_scope='two_component_containing_electrolytes_not_individually_assigned',
                    status_exception='exact_bound_O1s_comparator_without_it_only',
                    glyph_decoding=cathode_surface.view(source).provenance())
            if kind == 'solvation_trends':
                record['source_grammar'].update(trend_policy='solvation_concentration_mu_directions_v0.1',
                    claim_kind='reported_directions_correlation_and_author_interpretation',
                    salt_binding='literal_monovalent_cation_anion_code_concatenation_not_general_stoichiometry',
                    causality='not_independently_evaluated', basicity_direction='not_asserted')
            if kind == 'concentration_counterexample':
                record['source_grammar'].update(counterexample_policy='solvent_specific_concentration_counterexample_v0.1',
                    query_scope='exact_nonuniversality_question_not_general_why_or_negation_removal',
                    ratio_comparison='exact_positive_rational_inequality_no_conversion',
                    similarity='source_reported_not_independent_tolerance',
                    salt_binding='literal_monovalent_metal_prefix_not_general_formula_validation',
                    claim_kind='reported_counterexample_and_modal_descriptor_interpretation')
            if kind == 'sei_sufficiency':
                record['source_grammar'].update(sufficiency_policy='anion_sei_preformation_counterexample_v0.1',
                    query_scope='exact_anion_sei_sufficiency_question_only',
                    status_exception='exact_bound_non_change_non_suppression_and_modal_limitation_only',
                    ratio_binding='positive_exact_rational_first_formation_second_challenge',
                    salt_binding='literal_monovalent_cation_anion_code_concatenation',
                    claim_kind='observations_partial_contribution_and_supposed_mechanisms_not_guarantee')
            if kind == 'threshold_scope':
                record['source_grammar'].update(scope_policy='threshold_applicability_possible_shift_v0.1',
                    query_scope='exact_universal_invariance_question_only', status_exception='exact_bound_may_be_shifted_only',
                    salt_binding='literal_monovalent_metal_prefix_not_general_formula_validation',
                    shift_direction='not_asserted', shift_magnitude='not_asserted',
                    claim_kind='scoped_applicability_and_author_modal_caveat_not_universal_constant')
            if kind == 'solubility_limit':
                record['source_grammar'].update(limit_policy='solubility_below_conductivity_comparison_concentration_v0.1',
                    query_scope='exact_salt_concentration_unfluorinated_reference_exclusion_question_only',
                    concentration_unit_alias='M_equals_mol_dm_minus3_same_numeric_value', query_unit=params['query_unit'],
                    claim_kind='source_bound_methodological_limitation_not_failed_preparation_or_zero_conductivity',
                    solubility_temperature='not_assigned_from_concentration_reference_temperature',
                    glyph_decoding=ReviewedGlyphView(source, catalogue_binding=solubility_limit.GLYPHS).provenance())
            if kind == 'conductivity_explanation':
                record['source_grammar'].update(explanation_policy='conductivity_anion_solvation_possible_explanation_v0.1',
                    query_scope='exact_salt_and_solvent_pair_explanation_question_only',
                    status_exception='three_exact_bound_can_may_clauses_only',
                    salt_binding='literal_monovalent_metal_prefix_and_anion_not_general_formula_validation',
                    claim_kind='reported_order_and_author_possible_anion_solvation_dissociation_not_proven_mechanism',
                    glyph_decoding=conductivity_explanation.view(source).provenance())
            if kind == 'pure_concentration':
                record['source_grammar'].update(pure_policy='pure_solvent_concentration_mass_possible_contraction_v0.1',
                    query_scope='exact_pure_solvent_pair_temperature_question_only',
                    status_exception='exact_bound_may_contract_to_some_extent_only',
                    density_calculation='not_performed', unit_conversion='not_performed',
                    claim_kind='reported_quantities_and_author_possible_contraction_not_structural_measurement',
                    glyph_decoding=pure_concentration.view(source).provenance())
            candidates.append((source, record))
    if not candidates:
        if any(d['reason'] == 'raw_quantity_encoding_marker' for d in diagnostics):
            return stop('raw_quantity_unit_or_approximation_encoding_unresolved')
        return stop('quantitative_fields_or_conditions_unresolved')
    if len({r['allowed_claim'] for _, r in candidates}) != 1:
        return stop('conflicting_quantitative_values_or_conditions')
    source, record = min(candidates, key=lambda pair: (len(pair[0].text), pair[0].chunk_id))
    payload = {'version': VERSION, 'quantitative_policy': POLICY, 'family': kind, 'question': question,
               'raw_source': source.text, 'raw_source_type': source.source_type, 'reference': dict(metadata), 'records': [record]}
    derived = replace(source, source_type=SOURCE_TYPE, text=json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return Bundle(True, 'complete_source_bound_quantitative_bundle', kind, [derived], [source], [record], diagnostics)


def selection_records(evidence: list[Evidence]) -> dict[str, dict[str, Any]]:
    if len(evidence) != 1 or evidence[0].source_type != SOURCE_TYPE:
        raise GenerationOutputError('Quantitative facts require exactly one complete raw-bound parent')
    source = evidence[0]
    try:
        payload = json.loads(source.text)
        if (not isinstance(payload, dict) or set(payload) != {'version', 'quantitative_policy', 'family', 'question',
                'raw_source', 'raw_source_type', 'reference', 'records'} or payload['version'] != VERSION
                or payload['quantitative_policy'] != POLICY or not isinstance(payload['raw_source'], str)
                or not isinstance(payload['question'], str) or not isinstance(payload['raw_source_type'], str)):
            raise GenerationOutputError('Invalid quantitative fact payload')
        raw = replace(source, text=payload['raw_source'], source_type=payload['raw_source_type'])
        recomputed = prepare(payload['question'], [raw], payload['reference'], answer_language='ru')
        if recomputed is None or not recomputed.eligible or json.loads(recomputed.evidence[0].text) != payload:
            raise GenerationOutputError('Quantitative facts do not recompute from exact raw source')
        return {'F1': payload['records'][0]}
    except (ValueError, TypeError, KeyError, IndexError) as exc:
        raise GenerationOutputError('Malformed quantitative raw binding') from exc


def verify_raw_binding(text: str, raw: str, *, article_id: str, chunk_id: str, citation_id: str,
                       page_start: int, page_end: int, source_type: str | None) -> None:
    payload = json.loads(text)
    if (payload.get('raw_source') != raw or payload.get('raw_source_type') != source_type or source_type is None):
        raise ValueError('Quantitative registered raw text/source type differs')
    parent = Evidence(citation_id, article_id, chunk_id, None, None, page_start, page_end, SOURCE_TYPE, text, 0, 'binding', {}, {})
    selection_records([parent])
