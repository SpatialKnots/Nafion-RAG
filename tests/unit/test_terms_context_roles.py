"""Bounded role/origin cues; negation, future, attribution and source isolation."""
import json
from copy import deepcopy

import pytest

from app.terms.classification import Taxonomy, classify_article, subset
from scripts.tac_term_classification import DEFAULT_TAXONOMY
from tests.unit.test_term_classification import assigned, fixture


def classify(row):
    return classify_article(row, Taxonomy.model_validate(json.loads(DEFAULT_TAXONOMY.read_bytes())), 'a' * 64)


def categories(row, result, term, axis):
    return [{p['category'] for p in a['proposals']} for a in assigned(row, result, term, axis)]


def test_roles_bind_exact_mentions_and_intersection_does_not_join_uses(tmp_path):
    row = fixture(tmp_path, 'We prepared Nafion. Com-\npared with the Nafion, conductivity improved. Water was used as a solvent. '
                  'Membranes were pre-\npared. Electrolyte containing lithium was prepared.')
    before = deepcopy(row)
    result = classify(row)
    assert {'study_object'} in categories(row, result, 'nafion', 'role')
    assert {'comparison'} in categories(row, result, 'nafion', 'role')
    assert categories(row, result, 'water', 'role') == [{'composition_component'}]
    assert categories(row, result, 'membranes', 'role') == [{'study_object'}]
    assert categories(row, result, 'lithium', 'role') == [{'composition_component'}]
    assert subset(row, result['assignments'], {'role': 'comparison', 'origin': 'own_report'}, 'rank')['count'] == 0
    assert row == before


def test_attribution_does_not_leak_to_adjacent_sentence_and_abstains_on_negated_future(tmp_path):
    row = fixture(tmp_path, 'We have measured ionic conductivity. Nafion was present. '
                  'We measured no conductivity. We observed that water will evaporate. '
                  'Earlier studies reported conductivity. We assume that Nafion is stable.')
    result = classify(row)
    assert categories(row, result, 'ionic conductivity', 'origin') == [{'own_report'}]
    assert set().union(*categories(row, result, 'conductivity', 'origin')) == {'own_report', 'cited_work'}
    assert sum(a['state'] == 'unclassified' for a in assigned(row, result, 'conductivity', 'origin')) == 1
    assert categories(row, result, 'water', 'origin') == [set()]
    assert categories(row, result, 'nafion', 'origin') == [set(), {'hypothesis'}]


def test_method_role_needs_unique_type_and_keeps_word_per_line_source(tmp_path):
    row = fixture(tmp_path, 'Using the impedance\nspectroscopy, we measured conductivity. '
                  'Using impedance spectroscopy, we measured conductivity. Using Nafion, we prepared membranes.',
                  [{'concept': 'synthetic_method', 'alias': 'impedance spectroscopy', 'language': 'en'}])
    result = classify(row)
    assert categories(row, result, 'impedance spectroscopy', 'role') == [{'method'}, {'method'}]
    assert categories(row, result, 'nafion', 'role') == [set()]
    policy = json.loads(DEFAULT_TAXONOMY.read_bytes())
    rule = next(r for r in policy['rules'] if r['rule_id'] == 'type_material_exact_v01')
    rule['phrases'].append('impedance spectroscopy')
    ambiguous = classify_article(row, Taxonomy.model_validate(policy), 'b' * 64)
    # Both new and inherited adjacent cues must abstain on conflicting type in v0.3.
    assert categories(row, ambiguous, 'impedance spectroscopy', 'role') == [set(), set()]


def test_named_citation_and_hypothesis_have_exact_source_bound_basis(tmp_path):
    row = fixture(tmp_path, 'Smith et al. reported conductivity. We hypothesize that ionic conductivity increases.')
    result = classify(row)
    assert {'cited_work'} in categories(row, result, 'conductivity', 'origin')
    assert categories(row, result, 'ionic conductivity', 'origin') == [{'hypothesis'}]
    sources = {c['source']['region_id']: c['source'] for c in row['contexts']}
    for assignment in result['assignments']:
        if assignment['axis'] == 'type':
            continue
        for proposal in assignment['proposals']:
            for basis in proposal['basis']:
                source = sources[basis['source_region_id']]
                assert basis['quote'] == source['quote'][basis['start']-source['start']:basis['end']-source['start']]


def test_invalid_anchor_cannot_be_introduced_into_archived_policy():
    data = json.loads(DEFAULT_TAXONOMY.read_bytes())
    data['schema'] = 'tac_terms_taxonomy_v0.2'
    with pytest.raises(ValueError, match='anchored-context'):
        Taxonomy.model_validate(data)
