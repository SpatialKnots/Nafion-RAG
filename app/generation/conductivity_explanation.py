"""Finite salt/solvent conductivity comparison and author modal anion-solvation explanation."""
from __future__ import annotations

import re
from pathlib import Path

from app.generation import conductivity_order as order
from app.generation.fact_types import Fact, FactPatternError
from app.generation.providers import Evidence
from app.generation.reviewed_glyphs import ReviewedGlyphView

GLYPHS = (Path(__file__).resolve().parents[1] / 'resources/reviewed_conductivity_explanation_glyph_aliases_v01.json',
          '11b451b4695515a5247e50b835f53333b046afc2fced3fcd2a656a92b03bf055')
QUERY = re.compile(rf'Как авторы объясняют более высокую проводимость раствора (?P<salt>{order.CODE}) '
    rf'в (?P<higher>{order.CODE}) по сравнению с (?P<lower>{order.CODE})\?\s*$', re.I)
PATTERN = re.compile(order.PATTERN.pattern +
    r' The (?P<partial>partial fluorination) (?P<ability>can increase the ability of the solvent molecules '
    r'to form hydrogen bonds)\. Therefore, the (?P<acceptability>acceptability of an electron-pair of a '
    r'donor atom from a solute molecule becomes high)\. This effect (?P<modal>may result in the increased '
    rf'solvation of (?P<anion>{order.CODE})(?P<charge>−) ions and, consequently, in the higher degree of ionic dissociation)\. '
    r'The (?P<group>fluoromethyl group) \((?P<formula>CH2F-)\) (?P<role>may serve as an anion-attracting group)\.')


def view(source: Evidence) -> ReviewedGlyphView:
    return ReviewedGlyphView(source, catalogue_binding=GLYPHS)


def parse(v: ReviewedGlyphView, m: re.Match[str], *, salt: str, higher: str, lower: str) -> tuple[list[Fact], str]:
    if (m['higher'] != higher or m['lower'] != lower or higher == lower
            or re.fullmatch(r'[A-Z][a-z]?' + re.escape(m['anion']), salt) is None):
        raise FactPatternError('conductivity_explanation_pair_or_monovalent_salt_anion_mismatch')
    facts, _ = order.parse(v, m, salt=salt, concentration=m['concentration'])
    shared = {k: v.value(m, g) for k, g in (
        ('salt', 'salt'), ('pair_higher', 'higher'), ('pair_lower', 'lower'),
        ('concentration', 'concentration'), ('concentration_unit', 'unit'),
        ('concentration_reference_temperature', 'temperature'), ('temperature_unit', 'temperature_unit'))}
    facts.append(Fact('proposed_partial_fluorination_effect', v.value(m, 'partial'), v.value(m, 'ability'), None,
        'source_author_possible_explanation', None, {**shared, 'electron_pair_acceptability': v.value(m, 'acceptability')},
        'source_author_possible_explanation', v.support(m)))
    facts.append(Fact('proposed_anion_solvation_and_dissociation', v.value(m, 'anion'), v.value(m, 'modal'), None,
        'source_author_possible_explanation', None, {**shared, 'ion_charge': v.value(m, 'charge')},
        'source_author_possible_explanation', v.support(m), ('independent_mechanism_validation', 'numeric_dissociation_fraction')))
    facts.append(Fact('proposed_fluoromethyl_anion_attraction', v.value(m, 'group'), v.value(m, 'role'), None,
        'source_author_possible_explanation', None, {**shared, 'formula': v.value(m, 'formula')},
        'source_author_possible_explanation', v.support(m)))
    text = (f"Для растворов {salt} концентрации {m['concentration']} {m['unit']} "
        f"(концентрация указана при {m['temperature']}{m['temperature_unit']}) авторы приводят порядок "
        f"проводимости {m['order']}; в {higher} она выше, чем в {lower}. "
        'Предлагаемое объяснение: частичное фторирование может повысить способность молекул растворителя '
        'образовывать водородные связи и, по описанию авторов, повышает способность принимать электронную '
        'пару донорного атома молекулы растворённого вещества. '
        f"Этот эффект может усилить сольватацию анионов {m['anion']}{m['charge']} и, вследствие этого, "
        'повысить степень ионной диссоциации. Фторметильная группа (CH2F-) может служить группой, '
        'притягивающей анионы. Это авторская возможная интерпретация; независимое доказательство '
        'механизма и численная степень диссоциации здесь не установлены.')
    return facts, text
