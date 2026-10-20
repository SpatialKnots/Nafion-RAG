"""Relation direction, traceability, source isolation and conservative abstention."""
import json
from copy import deepcopy

import pytest

from app.terms.relations import build_relations, content_hash, validate_relations
from app.terms.schema import SourceFragment
from scripts.tac_term_classification import DEFAULT_TAXONOMY, build_classification
from tests.unit.test_term_classification import fixture


def inputs(tmp_path, text, boundary='pass'):
    row = fixture(tmp_path, text, [{'concept': 'synthetic_method', 'alias': 'impedance spectroscopy', 'language': 'en'}])
    for context in row['contexts']:
        context['boundary_status'] = boundary
    contexts = {'articles': [row]}
    bindings = {'contexts': content_hash(contexts), 'classification': 'b' * 64, 'snapshot': 'c' * 64, 'algorithm': 'd' * 64}
    taxonomy = json.loads(DEFAULT_TAXONOMY.read_bytes())
    classification = build_classification(contexts, taxonomy, bindings['contexts'], content_hash(taxonomy))
    return contexts, classification, bindings


def records(result):
    return result['articles'][0]['relations']


def test_explicit_property_and_measurement_have_existing_disjoint_endpoints_and_exact_evidence(tmp_path):
    contexts, classification, bindings = inputs(tmp_path, 'Ionic conductivity of Nafion increased. '
                                                'Viscosity was measured by impedance spectroscopy.')
    before = deepcopy(contexts)
    result = build_relations(contexts, classification, bindings)
    proposed = [r for r in records(result) if r['state'] == 'proposed']
    assert {r['predicate'] for r in proposed} == {'property-of', 'measured-by'}
    row = contexts['articles'][0]
    uses = {u['use_id']: u for u in row['uses']}
    mentions = {m['mention_id']: m['source'] for m in row['mentions']}
    for relation in proposed:
        s = mentions[uses[relation['subject_use_id']]['mention_id']]
        o = mentions[uses[relation['object_use_id']]['mention_id']]
        assert s['end'] < o['start']
        evidence = SourceFragment.model_validate(relation['evidence'])
        context = next(c['source'] for c in row['contexts'] if c['context_id'] == relation['context_id'])
        assert evidence.quote == context['quote'][evidence.start-context['start']:evidence.end-context['start']]
        assert relation['human_confirmation'] is False
    validate_relations(contexts, classification, result, bindings)
    assert contexts == before


@pytest.mark.parametrize('text', [
    'Conductivity of Nafion was not measured.',
    'Conductivity of Nafion will be measured.',
    'We hypothesize that conductivity of Nafion increases.',
    'Smith et al. reported conductivity of Nafion.',
    'Conductivity of Nafion and membranes increased.',
    'Conductivity of Nafion was derived from modeling.',
    'Conductivity of Nafion was higher than water.',
    'Conductivity of lithium metal increased.',
    'References: [1] Conductivity of Nafion increased.',
])
def test_negation_future_citation_multi_object_models_and_comparisons_defer(tmp_path, text):
    contexts, classification, bindings = inputs(tmp_path, text)
    result = build_relations(contexts, classification, bindings)
    assert records(result)
    assert all(r['state'] == 'deferred' for r in records(result))


def test_missing_method_unknown_boundary_and_no_cross_sentence_join(tmp_path):
    contexts, classification, bindings = inputs(tmp_path, 'Conductivity was measured by an unknown instrument. '
                                                'Viscosity. Nafion. Impedance spectroscopy.')
    result = build_relations(contexts, classification, bindings)
    assert records(result) and all(r['state'] == 'deferred' for r in records(result))
    assert any('missing_or_ambiguous_existing_endpoint' in r['diagnostics'] for r in records(result))
    (tmp_path / 'boundary').mkdir()
    contexts, classification, bindings = inputs(tmp_path / 'boundary', 'Conductivity of Nafion increased.', 'boundary_error')
    assert all(r['state'] == 'deferred' for r in records(build_relations(contexts, classification, bindings)))


@pytest.mark.parametrize('mutation', ['direction', 'endpoint', 'quote', 'page', 'layer', 'bindings', 'policy'])
def test_changed_endpoints_sources_and_snapshot_are_rejected(tmp_path, mutation):
    contexts, classification, bindings = inputs(tmp_path, 'Conductivity of Nafion increased.')
    data = build_relations(contexts, classification, bindings)
    assert records(data)
    relation = records(data)[0]
    if mutation == 'direction':
        relation['subject_use_id'], relation['object_use_id'] = relation['object_use_id'], relation['subject_use_id']
    elif mutation == 'endpoint':
        relation['object_use_id'] = 'f' * 64
    elif mutation in {'quote', 'page', 'layer'}:
        key, value = {'quote': ('quote', 'invented'), 'page': ('page_number', 99), 'layer': ('text_layer_id', 'stale')}[mutation]
        relation['evidence'][key] = value
    elif mutation == 'bindings':
        data['input_sha256']['snapshot'] = 'e' * 64
        bindings = dict(bindings, snapshot='c' * 64)
    else:
        data['policy'] = dict(data['policy'], version='unsupported')
    with pytest.raises(ValueError, match='Relation source'):
        validate_relations(contexts, classification, data, bindings)


def test_fabricated_endpoint_classification_is_not_trusted(tmp_path):
    contexts, classification, bindings = inputs(tmp_path, 'Conductivity of Nafion increased.')
    classification['articles'][0]['assignments'][0]['state'] = 'accepted'
    with pytest.raises(ValueError, match='does not reproduce'):
        build_relations(contexts, classification, bindings)
