"""New full-name inventory is additive, exact and separate from acronym equivalence."""
import json
from copy import deepcopy
from dataclasses import asdict

from app.records.schema import text_hash
from app.terms.classification import Taxonomy, classify_article
from app.terms.contexts import build_article
from app.terms.relations import build_relations, content_hash
from scripts.tac_experiment import span
from scripts.tac_term_classification import DEFAULT_TAXONOMY, build_classification
from scripts.tac_terms import propose_inventory
from tests.unit.test_tac_terms import source_profile
from tests.unit.test_term_classification import assigned
from tests.unit.test_term_contexts import inputs


def test_long_method_unicode_and_full_object_names_preserve_legacy_candidates():
    text = '19F nuclear magnetic resonance spectroscopy. Electrochemical impedance spectroscopy. '
    text += 'Naﬁon commercial water dispersions. Solution cast Nafion membranes. DSC. Raman spectroscopy.'
    _, profile = source_profile(text)
    before = deepcopy(profile)
    legacy = propose_inventory(profile, [], 12)
    enriched = propose_inventory(profile, [], 12, full_phrases=True)
    old = {t['term']: t for t in legacy['inventory']}
    new = {t['term']: t for t in enriched['inventory']}
    assert set(old) <= set(new)
    assert '19f nuclear magnetic resonance spectroscopy' in new
    assert 'nafion commercial water dispersions' in new
    assert 'solution cast nafion membranes' in new
    for name in old:
        assert old[name]['candidate_id'] == new[name]['candidate_id']
        assert all(e in new[name]['evidence'] for e in old[name]['evidence'])
    for term in new.values():
        for e in term['evidence']:
            assert text[e['start']:e['end']] == e['quote']
    assert profile == before
    assert not any('calorimetry' in t['term'] for t in enriched['inventory'])  # DSC alone is not expanded.


def enriched_row(tmp_path, text):
    snapshot, profiles, _, _ = inputs(tmp_path)
    article, profile = snapshot['articles'][0], profiles['profiles'][0]
    page = article['pages'][0]
    page.update(text=text, text_sha256=text_hash(text))
    profile['sections'] = [asdict(span(page, 'A', 0, len(text), 'synthetic'))]
    inventory = propose_inventory(profile, [], 12, {'A': {'status': 'pass'}}, full_phrases=True)
    row = build_article(article, profile, inventory).model_dump(mode='json')
    return row


def test_new_full_methods_and_component_names_receive_bounded_types_roles(tmp_path):
    row = enriched_row(tmp_path, 'Using electrochemical impedance spectroscopy, we measured conductivity. '
                       'Electrolytes containing fluorinated solvents were prepared. Nafion membranes were studied.')
    policy = Taxonomy.model_validate(json.loads(DEFAULT_TAXONOMY.read_bytes()))
    result = classify_article(row, policy, 'b' * 64)
    assert assigned(row, result, 'electrochemical impedance spectroscopy', 'type')[0]['proposals'][0]['category'] == 'method'
    assert assigned(row, result, 'electrochemical impedance spectroscopy', 'role')[0]['proposals'][0]['category'] == 'method'
    assert assigned(row, result, 'fluorinated solvents', 'role')[0]['proposals'][0]['category'] == 'composition_component'
    assert assigned(row, result, 'nafion membranes', 'role')[0]['proposals'][0]['category'] == 'study_object'


def test_instrument_name_is_not_silently_retyped_as_measurement_method(tmp_path):
    row=enriched_row(tmp_path,'Using scanning electron microscopy, we studied membranes. '
                     'A scanning electron microscope was used.')
    policy=Taxonomy.model_validate(json.loads(DEFAULT_TAXONOMY.read_bytes()))
    result=classify_article(row,policy,'b'*64)
    assert assigned(row,result,'scanning electron microscopy','type')[0]['proposals'][0]['category']=='method'
    assert assigned(row,result,'scanning electron microscope','type')[0]['proposals'][0]['category']=='object'


def test_measured_by_requires_full_exact_method_and_preserves_model_qualifier(tmp_path):
    row = enriched_row(tmp_path, 'Conductivity was measured by electrochemical impedance spectroscopy. '
                       'Mobility was measured by 19F NMR. '
                       'Conductivity was measured by impedance spectroscopy combined with interface modeling.')
    contexts = {'articles': [row]}
    bindings = {'contexts': content_hash(contexts), 'classification': 'c' * 64}
    taxonomy = json.loads(DEFAULT_TAXONOMY.read_bytes())
    classes = build_classification(contexts, taxonomy, bindings['contexts'], content_hash(taxonomy))
    result = build_relations(contexts, classes, bindings)
    measured = [r for r in result['articles'][0]['relations'] if r['predicate'] == 'measured-by']
    assert sum(r['state'] == 'proposed' for r in measured) == 2
    assert any(r['state'] == 'deferred' and 'modeling' in r['evidence']['quote'] for r in measured)
