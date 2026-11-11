"""Finite diethoxyethane name/alias/fluorination bindings, not a structure toolkit."""
from __future__ import annotations

import re
from dataclasses import replace

from app.generation.fact_types import Fact, FactPatternError, SourceView, Value

CODE = r'[A-Z][A-Za-z0-9]{0,24}'
PREFIXES = {'mono': 1, 'di': 2, 'tri': 3, 'tetra': 4, 'penta': 5, 'hexa': 6}
ARM = r'(?:ethoxy|\([12](?:,[12])*-(?:mono|di|tri|tetra|penta)?fluoroethoxy\))'
NAME = rf'1-{ARM}-\s*2-{ARM}ethane'
DEGREE = r'(?:mono|di|tri|tetra|penta|hexa)fluorinated'
BASE = re.compile(rf'(?P<base_name>1,2-[dD]iethoxyethane) \((?P<base>{CODE}), '
                  r'(?P<base_alias>ethylene glycol diethyl ether)\)')
PATTERN = re.compile(
    r'In the present paper, we describe the physical and electrochemical properties of '
    rf'(?P<count>three) (?P<class>fluorinated dialkyl ethers): '
    rf'(?P<name1>{NAME}) \((?P<label1>{CODE})\), '
    rf'(?P<name2>{NAME}) \((?P<label2>{CODE})\), '
    rf'(?P<name3>{NAME}) \((?P<label3>{CODE})\)\. '
    rf'(?P<order1>{CODE}), (?P<order2>{CODE}), and (?P<order3>{CODE}) '
    rf'(?P<relation>correspond to) (?P<degree1>{DEGREE}), (?P<degree2>{DEGREE}), '
    rf'and (?P<degree3>{DEGREE}) (?P<base>{CODE})s\.')


def _signature(name: str) -> tuple[tuple[int, ...], ...]:
    """Only the two equivalent ends of this explicit 1,2-diethoxyethane scaffold."""
    compact = re.sub(r'\s+', '', name)
    match = re.fullmatch(rf'1-(?P<a>{ARM})-2-(?P<b>{ARM})ethane', compact)
    if match is None:
        raise FactPatternError('unsupported_ethoxy_name_grammar')
    sites: list[tuple[int, ...]] = []
    for arm in (match['a'], match['b']):
        if arm == 'ethoxy':
            sites.append(())
            continue
        locants, rest = arm[1:-1].split('-', 1)
        prefix = rest.removesuffix('fluoroethoxy')
        count = PREFIXES[prefix] if prefix else 1
        positions = locants.split(',')
        if (len(positions) != count or positions.count('1') > 2 or positions.count('2') > 3
                or positions != sorted(positions)):
            raise FactPatternError('ethoxy_locant_prefix_inconsistency')
        sites.append(tuple(int(position) for position in positions))
    return tuple(sorted(sites))


def fluorine_count(name: str) -> int:
    """Consistency check for this one explicit ethoxy nomenclature grammar only."""
    return sum(len(sites) for sites in _signature(name))


def parse(view: SourceView, match: re.Match[str], base: re.Match[str], requested_base: str) -> tuple[list[Fact], str]:
    labels = [match[f'label{i}'] for i in range(1, 4)]
    order = [match[f'order{i}'] for i in range(1, 4)]
    if (len(set(labels)) != 3 or len(set(order)) != 3 or set(labels) != set(order)
            or match['base'] != base['base'] or match['base'] != requested_base or requested_base in labels):
        raise FactPatternError('ether_identity_alias_set_or_base_mismatch')
    degrees = {label: f'degree{i}' for i, label in enumerate(order, 1)}
    names = [re.sub(r'\s+', '', match[f'name{i}']) for i in range(1, 4)]
    if len({_signature(name) for name in names}) != 3:
        raise FactPatternError('duplicate_ether_name_with_multiple_aliases')
    translations = {'mono': 'монофторированный', 'di': 'дифторированный', 'tri': 'трифторированный',
                    'tetra': 'тетрафторированный', 'penta': 'пентафторированный', 'hexa': 'гексафторированный'}
    facts, descriptions = [], []
    for i, label in enumerate(labels, 1):
        degree_group = degrees[label]
        prefix = match[degree_group].removesuffix('fluorinated')
        if fluorine_count(names[i - 1]) != PREFIXES[prefix]:
            raise FactPatternError('ether_name_and_declared_fluorination_disagree')
        name = replace(view.value(match, f'name{i}'), text=names[i - 1],
                       normalization='nfkc_dehyphenation_whitespace_then_chemical_name_whitespace_compaction')
        facts.append(Fact('source_declared_ether_identity', view.value(match, f'label{i}'), name, None,
            'source_declared_name_alias_fluorination', None,
            {'degree': view.value(match, degree_group), 'base': view.value(base, 'base'),
             'base_name': view.value(base, 'base_name'), 'base_definition': Value(base.group(), view.support(base)),
             'item_count': view.value(match, 'count', word_number=True), 'relation': view.value(match, 'relation')},
            'source_declared_chemical_identity', view.support(match)))
        descriptions.append(f'{label} — {name.text}; {translations[prefix]} вариант {requested_base}')
    text = ('В статье исследованы три фторированных диалкиловых эфира. ' + '; '.join(descriptions) + '. '
            f"Основа сравнения {requested_base}: {base['base_name']} ({base['base_alias']}). "
            'Полные названия сохранены на языке источника; соответствие обозначений и степеней '
            'фторирования взято из явного перечня статьи.')
    return facts, text
