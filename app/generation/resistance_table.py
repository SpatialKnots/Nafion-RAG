"""Finite six-column resistance table grammar; no inferred or converted units."""

from __future__ import annotations

import re
from decimal import Decimal

from app.generation.fact_types import Fact, FactPatternError, SourceView

NUMBER = r'\d+(?:\.\d+)?'
ROW = re.compile(r'(?P<label>[A-Z][A-Za-z0-9]{0,24}) ' + ' '.join(
    rf'(?P<{key}>{NUMBER})' for key in ('before_r0', 'before_sum', 'after_r0', 'after_rs', 'after_rct', 'after_sum')))
TABLE = re.compile(
    r'Table (?P<table>\d+) Fitted resistance data from the equivalent circuit Electrolyte '
    r'(?P<before>Before cycle) (?P<after>After (?P<cycles>\d+)(?:st|nd|rd|th) cycles) '
    r'(?P<before_r0>R0) (?P<before_sum>Rs \+ Rct) '
    r'(?P<after_r0>R0) (?P<after_rs>Rs) (?P<after_rct>Rct) (?P<after_sum>Rs \+ Rct) '
    r'(?P<body>.*?)(?= Fig\.? \d+\b|$)')
KEYS = ('before_r0', 'before_sum', 'after_r0', 'after_rs', 'after_rct', 'after_sum')


def parse(view: SourceView, table: re.Match[str], cell: re.Match[str],
          labels: list[str], cycles: str) -> tuple[list[Fact], str]:
    """Bind every column to its explicit group header and every value to its row."""
    if table['cycles'] != cycles or int(cycles) < 1:
        raise FactPatternError('resistance_table_cycle_condition_mismatch')
    rows = list(ROW.finditer(view.text, table.start('body'), table.end('body')))
    position = table.start('body')
    for row in rows:
        if view.text[position:row.start()].strip():
            raise FactPatternError('resistance_table_row_shape_unresolved')
        position = row.end()
    if not rows or view.text[position:table.end('body')].strip():
        raise FactPatternError('resistance_table_row_shape_unresolved')
    by_label = {row['label']: row for row in rows}
    if len(by_label) != len(rows) or any(label not in by_label for label in labels):
        raise FactPatternError('resistance_table_missing_or_duplicate_electrolyte')
    # The source explicitly reports the sum; check its exact displayed arithmetic.
    # No tolerance, rounding repair, new delta or inferred pre-cycle components.
    if any(Decimal(row['after_rs']) + Decimal(row['after_rct']) != Decimal(row['after_sum']) for row in rows):
        raise FactPatternError('resistance_table_reported_sum_inconsistent')
    facts, descriptions = [], []
    for label in labels:
        row = by_label[label]
        for key in KEYS:
            state = 'before' if key.startswith('before_') else 'after'
            facts.append(Fact(
                'fitted_resistance_' + key, view.value(row, 'label'), view.value(row, key), None,
                'reported_equivalent_circuit_fit', None,
                {'cell': view.value(cell, 'cell'), 'cell_kind': view.value(cell, 'kind'),
                 'table': view.value(table, 'table'), 'cycle_state': view.value(table, state),
                 'column': view.value(table, key), 'pre_cycles': view.value(table, 'cycles')},
                'reported', view.support(table), ('unit', 'temperature')))
        before, after = Decimal(row['before_sum']), Decimal(row['after_sum'])
        trend = 'увеличилась' if after > before else 'уменьшилась' if after < before else 'не изменилась'
        descriptions.append(
            f"{label}: R0 {row['before_r0']} → {row['after_r0']}; "
            f"Rs + Rct {row['before_sum']} → {row['after_sum']} ({trend}); "
            f"после циклов Rs = {row['after_rs']}, Rct = {row['after_rct']}")
    text = (f"Полуячейки {cell['cell']}, таблица {table['table']}, до циклирования → после {cycles} "
            f"предварительных циклов. " + '; '.join(descriptions) + '. '
            'Это параметры подгонки эквивалентной схемы. До циклирования Rs и Rct по отдельности '
            'в таблице не приведены. Единица в самой таблице не указана; значения сохранены '
            'в записи источника без приписывания единицы или пересчёта.')
    return facts, text
