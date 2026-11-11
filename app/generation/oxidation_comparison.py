"""Finite reported LSV/float observations; no isolated causal or operating-limit claim."""
from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

from app.generation.fact_types import Fact, FactPatternError, SourceView
from app.generation.providers import Evidence
from app.generation.reviewed_glyphs import ReviewedGlyphView

GLYPHS = (Path(__file__).resolve().parents[1] / 'resources/reviewed_oxidation_glyph_aliases_v01.json',
          'a3daa8510ebc5347be6d827aa583627be2445d3ec83ebc841f0183f4ec5c7089')
CODE = r'[A-Z][A-Za-z0-9]{0,24}'
N = r'\d+(?:\.\d+)?'
BASE = re.compile(rf'The base electrolyte was (?P<c>{N}) (?P<unit>M) (?P<salt>{CODE}) dissolved in '
    rf'(?P<solvents>{CODE}/{CODE}) at (?P<ratio>{N}/{N}) ratio (?P<basis>by volume) '
    rf'\(marked as (?P<label>{CODE})\)\.')
FORMULATION = re.compile(rf'(?P<label>{CODE}): (?P<c>{N}) (?P<unit>M) (?P<salt>{CODE}) dissolved in '
    rf'(?P<solvents>{CODE}/{CODE}/{CODE}) at (?P<ratio>{N}/{N}/{N}) ratio (?P<basis>by weight)\.')
METHOD = re.compile(rf'The (?P<float>float test) was applied in a (?P<cell>{CODE}/{CODE}) cell beginning at '
    rf'(?P<cycles>three) pre-cycles at (?P<rate>{N})(?P<rate_unit>C) and then the cell was held at '
    rf'(?P<voltage>{N}) (?P<vunit>V) for (?P<time>{N}) (?P<tunit>h)\. The '
    rf'(?P<lsv>linear sweep voltammetry \(LSV\)) was used for measuring the stable potential window '
    rf'of the electrolyte with a scanning rate of (?P<scan>{N}) (?P<scan_unit>mV s[−-]1) on a '
    rf'electrochemical workstation \((?P<instrument>[A-Za-z0-9 -]{{1,60}})\), by a '
    rf'(?P<setup>three-electrode setup) with (?P<working>[A-Z][a-z]?) as the working electrode, '
    rf'and (?P<metal>[A-Z][a-z]?) metal as the (?P<roles>counter and reference electrode)\.')
HEAD = re.compile(r'The float test results of various electrolytes are shown in Fig\. (?P<figure>\d+)a\.')
RESULT = re.compile(rf'electrolyte at a given voltage of (?P<voltage>{N}) (?P<vunit>V) '
    rf'\(vs\. (?P<reference>{CODE}\+/{CODE})\)\. (?P<leakage>Appreciable oxidative leakage current) '
    rf'is observed in the (?P<base>{CODE}), (?P<interpretation>suggesting irreversible electrolyte decomposition)\. '
    rf'In contrast, the (?P<scope>introduction of various fluorizated solvents in the electrolyte) offers '
    rf'(?P<improvement>enhanced oxidative stability in virtue of significantly reduced leakage current)\. '
    rf'The LSV measurement of Fig\. (?P<figure>\d+)b also reflects above variation trend, in which '
    rf'(?P<base2>{CODE}) delivers (?P<base_observation>continual increase in the oxidized current) beginning at '
    rf'(?P<base_approx>~)(?P<base_voltage>{N}) (?P<base_unit>V), while the '
    rf'(?P<label_kind>perfluorinated electrolyte) (?P<label>{CODE}) is (?P<state>quite stable until) '
    rf'(?P<approx>~)(?P<limit>{N}) (?P<unit>V)\. It means (?P<conclusion>wider stable potential window '
    rf'can be obtained by the synergistic oxidation resistivity of ternary fluorizated solvents)\.')


def view(source: Evidence) -> ReviewedGlyphView:
    return ReviewedGlyphView(source, catalogue_binding=GLYPHS)


def parse(v: SourceView, base: re.Match[str], formulation: re.Match[str], method: re.Match[str],
          head: re.Match[str], result: re.Match[str]) -> tuple[list[Fact], str]:
    b, f, m, h, r = base, formulation, method, head, result
    if (b['label'] != r['base'] or r['base'] != r['base2'] or f['label'] != r['label']
            or b['label'] == f['label'] or b['salt'] != f['salt'] or h['figure'] != r['figure']
            or Decimal(b['c']) != Decimal(f['c']) or Decimal(b['c']) <= 0
            or Decimal(m['voltage']) != Decimal(r['voltage']) or Decimal(m['voltage']) <= 0
            or any(Decimal(m[k]) <= 0 for k in ('rate', 'time', 'scan'))
            or Decimal(r['base_voltage']) <= 0 or Decimal(r['base_voltage']) >= Decimal(r['limit'])
            or r['reference'] != m['metal'] + '+/' + m['metal']
            or m['cell'].split('/')[-1] != m['metal']
            or any(Decimal(n) <= 0 for row in (b, f) for n in row['ratio'].split('/'))
            or len(set(b['solvents'].split('/'))) != 2 or len(set(f['solvents'].split('/'))) != 3):
        raise FactPatternError('oxidation_labels_salt_dose_voltage_reference_or_comparison_mismatch')

    def fact(row: re.Match[str], prop: str, sample: str | None, value: str, unit: str | None,
             keys: tuple[str, ...], *, operation: str = 'source_reported_conditions') -> Fact:
        return Fact(prop, v.value(row, sample) if sample else None, v.value(row, value),
            v.value(row, unit) if unit else None, operation, None, {k: v.value(row, k) for k in keys},
            'source_reported_conditions_or_observation', v.support(row), ('measurement_temperature',))

    formulations = [fact(row, 'solution_formulation', 'label', 'solvents', None,
                         ('c', 'unit', 'salt', 'ratio', 'basis')) for row in (b, f)]
    float_fact = fact(m, 'float_hold_voltage', 'cell', 'voltage', 'vunit', ('cycles', 'rate', 'rate_unit', 'time', 'tunit'))
    float_fact.conditions.update(reference=v.value(r, 'reference'), figure=v.value(h, 'figure'))
    lsv = fact(m, 'lsv_scan_rate', None, 'scan', 'scan_unit', ('setup', 'working', 'metal', 'roles', 'instrument'))
    lsv = Fact(lsv.property, lsv.sample, lsv.value, lsv.unit, lsv.operation, v.value(m, 'lsv'), lsv.conditions,
               lsv.epistemic_status, lsv.support, lsv.unknown_fields)
    comparison = fact(r, 'float_leakage_comparison', 'scope', 'improvement', None,
                      ('base', 'leakage', 'interpretation', 'voltage', 'vunit', 'reference'),
                      operation='reported_comparison_with_suggestive_interpretation')
    first = fact(r, 'lsv_current_increase_beginning', 'base', 'base_voltage', 'base_unit',
                 ('base_approx', 'base_observation', 'figure'), operation='reported_approximate_lsv_observation')
    last = fact(r, 'lsv_reported_stable_until', 'label', 'limit', 'unit',
                ('approx', 'state', 'label_kind', 'figure', 'conclusion'), operation='reported_approximate_lsv_observation')
    text = (f"По двум измерениям авторы сообщают о повышении устойчивости исследованных электролитов к окислению. "
        f"Базовый {b['label']}: {b['c']} {b['unit']} {b['salt']} в {b['solvents']} ({b['ratio']} по объёму); "
        f"{f['label']}: {f['c']} {f['unit']} {f['salt']} в {f['solvents']} ({f['ratio']} по массе), "
        'обозначенный авторами как perfluorinated. '
        f"Float-test: {m['cell']}, три предварительных цикла при {m['rate']}{m['rate_unit']}, затем выдержка "
        f"при {m['voltage']} {m['vunit']} (относительно {r['reference']}) {m['time']} {m['tunit']}. "
        f"У {r['base']} наблюдали заметный окислительный ток утечки, который авторы трактуют как признак "
        'необратимого разложения. Введение фторированных растворителей сопровождалось значительно меньшим током утечки. '
        f"LSV: скорость {m['scan']} {m['scan_unit']}, рабочий электрод {m['working']}, "
        f"{m['metal']} — электрод сравнения и вспомогательный. У {r['base']} ток окисления начинает непрерывно расти "
        f"примерно с {r['base_voltage']} {r['base_unit']}; {r['label']} описан как устойчивый примерно до "
        f"{r['limit']} {r['unit']}. Авторы связывают это с более широким окном устойчивости. "
        'Это наблюдения для указанных составов и режимов; предел LSV не задаёт рабочее напряжение полной ячейки. '
        'Отдельный причинный вклад каждого растворителя здесь не определяется.')
    return [*formulations, float_fact, lsv, comparison, first, last], text
