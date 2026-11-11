"""Finite cathode SEM/XPS observations, with source grouping and interpretation retained."""
from __future__ import annotations

import re
from pathlib import Path

from app.generation.fact_types import Fact, FactPatternError, SourceView
from app.generation.providers import Evidence
from app.generation.reviewed_glyphs import ReviewedGlyphView

GLYPHS = (Path(__file__).resolve().parents[1] / 'resources/reviewed_surface_glyph_aliases_v02.json',
          '4c01639fcfe86d626444e267b2bb320fd2a9ce6535f84a4b2bac0a8c450fd3fd')
CODE = r'[A-Z][A-Za-z0-9]{0,24}'
FRAME = re.compile(rf'the (?P<electrode>{CODE}) and (?P<anode>{CODE}) disassembled from the '
                   rf'(?P<cell>cycled full cell) was further analysed by SEM and XPS technology, respectively\.')
SEM = re.compile(rf'The fresh (?P<electrode>{CODE}) \(Fig\. (?P<figure>\d+)a\) particle with '
    rf'(?P<fresh>smooth surface surrounded by large quantities of conductive carbon black) is observed\. '
    rf'After cycling in (?P<base>{CODE}) \(Fig\. (?P<fbase>\d+)b\), (?P<cracks>some clear microcracks) appear '
    rf'on the (?P<electrode2>{CODE}) surface, which is usually caused by the accumulated strain within the particle '
    rf'due to phase transition at high voltage during repeated Li\+ extraction/\s*insertion process, coupled with '
    rf'the decreased Li\+ diffusivity and dramatic capacity fading in the deeply charged (?P<electrode3>{CODE})\.\d+ '
    rf'These microcracks is (?P<partial>partially preserved) in the (?P<electrode4>{CODE}) cycled in '
    rf'(?P<other1>{CODE}) \(Fig\. (?P<fother1>\d+)c\) and (?P<other2>{CODE}) \(Fig\. (?P<fother2>\d+)d\), '
    rf'and yet (?P<change>almost disappears) in the case of (?P<label>{CODE}) \(Fig\. (?P<flabel>\d+)e\)\.')
XPS = re.compile(rf'The XPS spectra measured from the cycled (?P<electrode>{CODE}) cathode in various '
    rf'electrolytes were compared in Fig\. (?P<figure>\d+)\. The (?P<c_spectrum>C 1s) spectra can be divided '
    rf'into (?P<count>five) peaks, in which the existence of (?P<co>C–O) and (?P<carbonyl>C=O) peak mean '
    rf'that the cycled (?P<electrode2>{CODE}) is covered by some (?P<products>organic/inorganic degradation products)\.\d+ '
    rf'For the (?P<o_spectrum>O 1s) spectra, the (?P<carbonate>{CODE}) peak is (?P<o_change>clearly stronger) in '
    rf'(?P<group>two (?P<component>{CODE})-contained electrolytes) than (?P<o_reference>those without it), '
    rf'which is (?P<o_status>considered to be mainly from (?P<origin>{CODE}) decomposition)\d+ and contribute to '
    rf'(?P<o_interpretation>CEI amelioration)\. A bit stronger intensities of metal–O peak \(from '
    rf'(?P<electrode3>{CODE})\) and C–F peak \(usually from PVDF binder\)\d+ in the (?P<other1>{CODE}) '
    rf'compared to other cases implies defective/weak protective film formed on (?P<electrode4>{CODE}) surface '
    rf'and hence results in high interfacial resistance confirmed in Fig\. \d+\. Besides, the '
    rf'(?P<f_spectrum>F 1s) spectra demonstrates a (?P<f_change>lower) (?P<phosphate>{CODE}) peak '
    rf'\(the byproduct of (?P<salt>{CODE})\)\d+ in the (?P<other2>{CODE}) and (?P<label>{CODE}) than '
    rf'(?P<base>{CODE}), (?P<f_status>suggesting the effective restraint towards electrolyte degradation)\. '
    rf'All of these results (?P<status>suggest) that the fluorinated solvents cooperatively modify '
    rf'(?P<film>CEI) on the (?P<electrode5>{CODE}) by (?P<interpretation>moderate modulation of the interfacial constitution)\.')
CAPTION = re.compile(rf'Fig\. (?P<figure>\d+) XPS patterns of the cycled (?P<electrode>{CODE}) in '
    rf'\(a\) (?P<base>{CODE}), \(b\) (?P<other1>{CODE}), \(c\) (?P<other2>{CODE}) and \(d\) (?P<label>{CODE})\.')


def view(source: Evidence) -> ReviewedGlyphView:
    return ReviewedGlyphView(source, catalogue_binding=GLYPHS)


def parse(v: SourceView, frame: re.Match[str], sem: re.Match[str], xps: re.Match[str], caption: re.Match[str], *,
          electrode: str, label: str) -> tuple[list[Fact], str]:
    f, s, x = frame, sem, xps
    if (any(row[key] != electrode for row, keys in ((s, ('electrode', 'electrode2', 'electrode3', 'electrode4')),
             (x, ('electrode', 'electrode2', 'electrode3', 'electrode4', 'electrode5')),
             (f, ('electrode',))) for key in keys)
            or f['anode'] == electrode or s['label'] != label or x['label'] != label
            or any(s[k] != x[k] for k in ('base', 'other1', 'other2'))
            or any(caption[k] != x[k] for k in ('figure', 'electrode', 'base', 'other1', 'other2', 'label'))
            or len({s[k] for k in ('base', 'other1', 'other2', 'label')}) != 4
            or any(s[k] != s['figure'] for k in ('fbase', 'fother1', 'fother2', 'flabel'))
            or x['component'] != x['origin']):
        raise FactPatternError('cathode_surface_owner_label_figure_or_group_origin_mismatch')

    def fact(row: re.Match[str], prop: str, value: str, keys: tuple[str, ...], status: str) -> Fact:
        return Fact(prop, v.value(row, 'electrode'), v.value(row, value), None, status, None,
            {**{k: v.value(row, k) for k in keys}, 'cell_scope': v.value(f, 'cell')},
            status, v.support(row), ('cycle_count', 'cycling_voltage', 'temperature'))

    fresh = fact(s, 'fresh_cathode_surface', 'fresh', ('figure',), 'source_reported_sem_observation')
    morphology = fact(s, 'cycled_cathode_microcracks', 'change',
                      ('label', 'base', 'cracks', 'other1', 'other2', 'partial', 'figure'), 'source_reported_sem_observation')
    carbon = fact(x, 'cathode_c1s_assignment', 'products', ('c_spectrum', 'count', 'co', 'carbonyl', 'figure'),
                  'source_xps_assignment')
    oxygen = fact(x, 'cathode_o1s_group_comparison', 'carbonate',
                  ('o_spectrum', 'o_change', 'group', 'o_reference', 'o_status', 'o_interpretation', 'figure'),
                  'source_group_observation_not_named_formulation_assignment')
    oxygen = Fact(oxygen.property, oxygen.sample, oxygen.value, None, oxygen.operation, None, oxygen.conditions,
                  oxygen.epistemic_status, oxygen.support, (*oxygen.unknown_fields, 'named_formulations_for_component_group'))
    fluorine = fact(x, 'cathode_f1s_comparison', 'phosphate',
                    ('f_spectrum', 'f_change', 'other2', 'label', 'base', 'salt', 'f_status', 'figure'),
                    'source_xps_assignment_with_suggestive_interpretation')
    interpretation = fact(x, 'cathode_cei_interpretation', 'interpretation', ('status', 'film'),
                          'source_author_interpretation')
    for observed in (carbon, oxygen, fluorine, interpretation):
        keys = ('figure', 'electrode', 'base', 'other1', 'other2', 'label') if observed is fluorine else ('figure', 'electrode')
        observed.conditions.update({'caption_' + key: v.value(caption, key) for key in keys})
    text = (f"После циклирования полной ячейки авторы описывают следующие изменения на {electrode}. "
        f"SEM (рис. {s['figure']}): исходные частицы имеют гладкую поверхность; после циклирования в {s['base']} "
        f"видны микротрещины, в {s['other1']} и {s['other2']} они частично сохраняются, а в {label} почти исчезают. "
        f"XPS (рис. {x['figure']}): пики {x['co']} и {x['carbonyl']} в C 1s авторы связывают с органическими/"
        f"неорганическими продуктами разложения на {electrode}. Усиление пика {x['carbonate']} в O 1s описано "
        f"для группы из двух {x['component']}-содержащих электролитов относительно электролитов без него; "
        f"авторы считают его преимущественно результатом разложения {x['origin']} и связывают с улучшением CEI. "
        f"В F 1s у {x['other2']} и {label} пик {x['phosphate']} слабее, чем у {s['base']}; авторы трактуют "
        'это как признак сдерживания разложения электролита. Их общий вывод — совместное изменение CEI '
        f"на {electrode} за счёт умеренного изменения межфазного состава. Это назначения пиков и авторская "
        'интерпретация; количественные доли компонентов и толщина плёнки в этих абзацах не указаны.')
    return [fresh, morphology, carbon, oxygen, fluorine, interpretation], text
