"""Synthetic inventory invariants; not independent scientific keyword labels."""
from copy import deepcopy
from dataclasses import asdict

import pytest

from scripts.tac_experiment import digest, span
from scripts.tac_review_html import render_table
from scripts.tac_terms import INVENTORY_VERSION, PREVIEW_POLICY, inventory_digest, main, propose_article, propose_inventory, validate_terms
from tests.unit.test_tac_review_html import fixture
from tests.unit.test_tac_terms import source_profile


def inventory_fixture(tmp_path):
    snapshot, profiles, metadata = fixture(tmp_path)
    p = snapshot['articles'][0]['pages'][0]
    p['text'] = 'Nafion membranes; ionic conductivity; LiCoO2 electrodes.\nOutside TAC body.'
    p['text_sha256'] = digest(p['text'].encode())
    profile = profiles['profiles'][0]
    profile['sections'] = [asdict(span(p, 'T', 0, p['text'].index('\n'), 'synthetic'))]
    rows = [propose_inventory(profile, [], 1)]
    terms = {'schema': INVENTORY_VERSION, 'state': 'proposed_for_article_review',
             'snapshot_sha256': profiles['snapshot_sha256'], 'profiles_sha256': 'c' * 64, 'glossary_sha256': 'd' * 64,
             'settings': {'preview_limit': 1, 'preview_policy': PREVIEW_POLICY}, 'articles': rows}
    return snapshot, profiles, metadata, terms


def test_preview_limits_leave_complete_inventory_and_exact_occurrences_identical():
    text = 'Naﬁon membranes; ionic conductivity; LiCoO2 electrodes.'
    page, profile = source_profile(text)
    original = deepcopy(profile)
    small = propose_inventory(profile, [], 1)
    large = propose_inventory(profile, [], 12)
    assert small['inventory'] == large['inventory']
    assert small['inventory_sha256'] == large['inventory_sha256']
    assert small['candidate_count'] > len(small['preview']['candidate_ids'])
    assert {'nafion', 'membranes', 'nafion membranes'} <= {t['term'] for t in small['inventory']}
    assert any(d['state'] == 'nested_surface_suppressed' for d in large['preview']['decisions'])
    assert any(d['state'] == 'preview_limit' for d in small['preview']['decisions'])
    assert profile == original and page['text'] == text
    for t in small['inventory']:
        for e in t['evidence']:
            assert text[e['start']:e['end']] == e['quote']


@pytest.mark.parametrize('limit', [1, 2, 12, 50])
def test_inventory_preview_matches_legacy_without_changing_candidate_fields(limit):
    _, profile = source_profile('PFSA membranes; ionic conductivity; LiCoO2 electrodes; Nafion solvent swelling.')
    legacy = propose_article(profile, [], limit)
    new = propose_inventory(profile, [], limit)
    by_id = {t['candidate_id']: t for t in new['inventory']}
    selected = [{k: v for k, v in by_id[identifier].items() if k not in {'candidate_id', 'rank', 'rank_features'}}
                for identifier in new['preview']['candidate_ids']]
    assert selected == legacy['terms']
    assert new['candidate_count'] == legacy['candidate_count']
    assert sum(d['state'] == 'nested_surface_suppressed' for d in new['preview']['decisions']) == legacy['nested_candidates_suppressed']


def test_inventory_is_not_capped_at_legacy_maximum_of_50():
    text = '; '.join(f'LiX{i} electrodes' for i in range(60)) + '.'
    _, profile = source_profile(text)
    new = propose_inventory(profile, [], 12)
    assert len(new['inventory']) > 50
    assert all(any(t['label'] == f'LiX{i}' for t in new['inventory']) for i in range(60))
    assert len(new['preview']['candidate_ids']) <= 12


def test_empty_inventory_and_article_scoped_ids_remain_explicit():
    _, empty = source_profile('The study was conducted. 2026.')
    row = propose_inventory(empty, [], 12)
    assert row['inventory'] == [] and row['preview']['candidate_ids'] == [] and row['status'] == 'not_detected'
    _, p = source_profile('Nafion membranes.')
    other = {**p, 'article_id': 'other-upload'}
    first, second = propose_inventory(p, [], 12), propose_inventory(other, [], 12)
    assert {t['candidate_id'] for t in first['inventory']}.isdisjoint(t['candidate_id'] for t in second['inventory'])


@pytest.mark.parametrize('mutation', ['unknown_schema', 'dropped', 'forged_count', 'duplicate_id', 'rank_features', 'score',
                                    'quote', 'layer', 'accepted', 'unknown_preview', 'duplicate_preview', 'false_decision',
                                    'order', 'preview_limit', 'hash', 'duplicate_evidence'])
def test_inventory_validator_rejects_corrupted_hidden_candidates_and_preview(tmp_path, mutation):
    snapshot, profiles, _, data = inventory_fixture(tmp_path)
    validate_terms(snapshot, profiles, data, 'c' * 64)
    row = data['articles'][0]
    t = row['inventory'][-1]  # Hidden evidence must be checked too.
    if mutation == 'unknown_schema':
        data['schema'] = 'tac_term_inventory_v999'
    elif mutation == 'dropped':
        row['inventory'].pop()
        row['candidate_count'] -= 1
        row['inventory_sha256'] = inventory_digest(row['inventory'])
    elif mutation == 'forged_count':
        row['candidate_count'] += 1
    elif mutation == 'duplicate_id':
        t['candidate_id'] = row['inventory'][0]['candidate_id']
    elif mutation == 'rank_features':
        t['rank_features']['token_count'] += 1
    elif mutation == 'score':
        t['score'] += 1
    elif mutation == 'quote':
        t['evidence'][0]['quote'] = 'Invented quote'
    elif mutation == 'layer':
        t['evidence'][0]['layer_id'] = 'wrong'
    elif mutation == 'accepted':
        t['status'] = 'accepted'
    elif mutation == 'unknown_preview':
        row['preview']['candidate_ids'] = ['not-in-inventory']
    elif mutation == 'duplicate_preview':
        row['preview']['candidate_ids'] *= 2
    elif mutation == 'false_decision':
        row['preview']['decisions'][-1]['state'] = 'selected'
    elif mutation == 'order':
        row['inventory'].reverse()
    elif mutation == 'preview_limit':
        row['preview']['limit'] = 50
    elif mutation == 'hash':
        row['inventory_sha256'] = 'f' * 64
    elif mutation == 'duplicate_evidence':
        t['evidence'].append(deepcopy(t['evidence'][0]))
        t['occurrences'] += 1
    with pytest.raises(ValueError, match='[Tt]erm'):
        validate_terms(snapshot, profiles, data, 'c' * 64)


def test_inventory_html_retains_hidden_quotes_and_search_labels_with_lazy_groups(tmp_path):
    snapshot, profiles, metadata, data = inventory_fixture(tmp_path)
    html = render_table(snapshot, profiles, metadata, tmp_path, 'c' * 64, terms=data)
    assert html.count('<th>') == 8 and '<template>' in html and 'Все кандидаты:' in html
    assert 'data-preview-count="1"' in html and 'data-search=' in html
    row = data['articles'][0]
    for t in row['inventory']:
        assert f'data-candidate-id="{t["candidate_id"]}"' in html
    assert 'LiCoO2' in html and 'Outside TAC body' not in html
    assert 'Вне превью:' in html and 'materialize' in html


@pytest.mark.parametrize('options', [
    ['--format', 'inventory', '--max-terms', '12'],
    ['--preview-limit', '12'],
    ['--format', 'inventory', '--preview-limit', '0'],
])
def test_cli_rejects_ambiguous_limit_semantics_before_reading_sources(monkeypatch, tmp_path, options):
    output = tmp_path / 'must-not-exist.json'
    monkeypatch.setattr('sys.argv', ['tac_terms', '--snapshot', 'missing.json', '--profiles', 'missing.json',
                                   '--output', str(output), *options])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2 and not output.exists()
