"""Constructed necessary-mention references, not scientific answer labels or network tests."""

import copy
import json
from dataclasses import replace
from unittest.mock import patch

import pytest

from app.evaluation.query_qualifiers_run import FIXTURE, constructed_evidence, export, load, prepare
from app.generation.providers import ProviderResult
from app.generation.query_qualifiers import (
    VERSION,
    QualifierGuardProvider,
    assess_query_qualifiers,
    extract_qualifiers,
    occurrences,
)
from app.records.sources import file_hash

CASES = json.loads(FIXTURE.read_bytes())


def assess(question, texts, **kwargs):
    evidence = [constructed_evidence({'article_id': 'A', 'text': t}, i) for i, t in enumerate(texts, 1)]
    return assess_query_qualifiers(question, evidence, baseline_allowed=True, **kwargs)


@pytest.mark.parametrize('case', CASES, ids=[c['id'] for c in CASES])
def test_constructed_necessary_mention_reference(case):
    before = copy.deepcopy(case)
    evidence = [constructed_evidence(e, i) for i, e in enumerate(case['evidence'], 1)]
    result = assess_query_qualifiers(case['question'], evidence, baseline_allowed=case['baseline_allowed'],
                                     article_metadata=case.get('article_metadata', {}))
    assert result['candidate_allowed'] is case['expected_candidate_allowed']
    assert result['scientific_admission'] == 'not_evaluated'
    for q in result['qualifiers']:
        assert case['question'][q['start']:q['end']] == q['text']
    for row in result['articles']:
        for check in row['checks']:
            for span in check['occurrences']:
                if 'citation_id' in span:
                    text = next(e.text for e in evidence if e.citation_id == span['citation_id'])
                    assert text[span['start']:span['end']] == span['text']
    assert case == before


@pytest.mark.parametrize('raw,phrase', [('ﬁlm', 'film'), ('boron-\nnitride', 'boron nitride'),
                                      ('EC/SL', 'EC/SL'), ("O'Neil", "O'Neil")])
def test_raw_unicode_offsets_preserve_original_source(raw, phrase):
    text = 'prefix ' + raw + ' suffix'
    assert occurrences(text, phrase) == [{'start': 7, 'end': 7 + len(raw), 'text': raw}]


@pytest.mark.parametrize('texts', [[], ['DSC'], ['No relevant evidence.']])
def test_baseline_rejection_cannot_be_upgraded(texts):
    result = assess_query_qualifiers('DSC?', [constructed_evidence({'article_id': 'A', 'text': t}, i)
        for i, t in enumerate(texts, 1)], baseline_allowed=False)
    assert result['candidate_allowed'] is False and result['reason'] == 'baseline_rejection_preserved'


def test_surnames_and_materials_are_extracted_generically_without_observed_name_rules():
    q, _ = extract_qualifiers('For Tanaka 2022, what TGA protocol applies to films containing hafnium boride?')
    assert [(x.kind, x.key) for x in q] == [('article', 'Tanaka'),
        ('method_or_property_mention', 'thermogravimetric_analysis'), ('material_literal', 'hafnium boride')]


def test_missing_article_metadata_stays_unknown_even_when_body_title_mentions_author():
    e = replace(constructed_evidence({'article_id': 'A', 'text': 'Rivera 2019. DSC.'}, 1), title='Rivera 2019')
    result = assess_query_qualifiers('For Rivera 2019, DSC?', [e], baseline_allowed=True)
    assert result['articles'][0]['checks'][0]['state'] == 'unknown_metadata'
    assert not result['candidate_allowed']


@pytest.mark.parametrize('metadata', [{'authors': 'Rivera', 'year': 2019}, {'authors': ['Rivera'], 'year': True}])
def test_malformed_nonempty_metadata_does_not_silently_match(metadata):
    with pytest.raises(ValueError):
        assess('For Rivera 2019, DSC?', ['DSC'], article_metadata={'A': metadata})


def test_repeated_method_question_is_one_requirement_and_empty_marker_is_unknown():
    result = assess('DSC and DSC containing?', ['DSC'])
    assert len(result['qualifiers']) == 1
    assert result['parse_warnings'] == ['material_marker_without_literal_phrase']
    assert not result['candidate_allowed']


@pytest.mark.parametrize('variant', ['empty_question', 'duplicate_id', 'empty_id', 'empty_article'])
def test_invalid_question_or_evidence_id_is_not_hidden(variant):
    e = constructed_evidence({'article_id': 'A', 'text': 'DSC'}, 1)
    question, evidence = 'DSC', [e]
    if variant == 'empty_question':
        question = ' '
    elif variant == 'duplicate_id':
        evidence.append(e)
    elif variant == 'empty_id':
        evidence = [replace(e, citation_id='')]
    else:
        evidence = [replace(e, article_id='')]
    with pytest.raises(ValueError):
        assess_query_qualifiers(question, evidence, baseline_allowed=True)


def test_empty_evidence_cannot_preserve_an_erroneous_allowance_outside_grammar_scope():
    result = assess_query_qualifiers('How were samples prepared?', [], baseline_allowed=True)
    assert not result['candidate_allowed'] and result['reason'] == 'no_evidence'


class Recorder:
    def __init__(self):
        self.calls = []

    def generate(self, question, evidence, **kwargs):
        self.calls.append((question, evidence, kwargs))
        return ProviderResult(False, [], 'constructed', 'not-a-model')


def test_wrapper_missing_requirement_abstains_before_wrapped_provider():
    recorder = Recorder()
    provider = QualifierGuardProvider(recorder)
    reply = provider.generate('Conductivity containing hafnium boride?',
                             [constructed_evidence({'article_id': 'A', 'text': 'Conductivity'}, 1)])
    assert not recorder.calls and reply == ProviderResult(False, [], VERSION, None)
    assert provider.assessment['reason'] == 'no_single_article_covers_required_mentions'


def test_wrapper_forwards_unchanged_input_and_options_when_only_necessary_mentions_pass():
    recorder = Recorder()
    provider = QualifierGuardProvider(recorder)
    evidence = [constructed_evidence({'article_id': 'A', 'text': 'DSC'}, 1)]
    result = provider.generate('DSC?', evidence, answer_style='mini_review', answer_language='ru')
    assert result.provider == 'constructed'
    assert recorder.calls == [('DSC?', evidence, {'answer_style': 'mini_review', 'answer_language': 'ru'})]
    assert recorder.calls[0][1] is evidence


def test_explicit_injection_into_existing_answer_pipeline_prevents_wrapped_generation(monkeypatch):
    from app.generation.service import answer_question
    from app.retrieval.search import SearchResponse
    from tests.unit.test_generation import _search_result, _settings

    text = 'Conductivity was reported for membranes containing polymer films.'
    result = replace(_search_result(), full_text=text, snippet=text)
    monkeypatch.setattr('app.generation.service.search_chunks', lambda *a, **kw: SearchResponse(query='test', results=[result]))
    recorder = Recorder()
    provider = QualifierGuardProvider(recorder)
    response = answer_question(object(), _settings(),
        'What conductivity was reported for membranes containing hafnium boride?', provider=provider)
    assert not recorder.calls and not response.claims
    assert provider.assessment is not None and not provider.assessment['candidate_allowed']
    assert response.metadata['evidence_adequacy']['adequate']


def prepared_storage(tmp_path):
    # A constructed predecessor capture; no scientific source or live retrieval.
    capture = tmp_path / 'capture'
    capture.mkdir()
    q = '<script> DSC containing hafnium boride?'
    row = {'id': 'constructed_observed', 'question': q, 'baseline_status': 'context_prepared_before_generation',
           'trace': {'evidence': [vars(constructed_evidence({'article_id': 'A', 'text': 'DSC'}, 1))]},
           'sources': {'pages': {}}, 'current_prompt': 'Constructed prompt'}
    (capture / 'capture.json').write_text(json.dumps({'queries': [row]}), encoding='utf-8')
    manifest = {'version': 'query_evidence_packet_v0.1', 'phase': 'read_only_current_context_captured',
                'code': {}, 'inputs': {}, 'outputs': {'capture.json': file_hash(capture / 'capture.json')}}
    (capture / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    output = tmp_path / 'prepared'
    with patch('app.evaluation.query_qualifiers_run.load_packets', return_value=({'version': manifest['version'],
        'questions': [{'id': row['id'], 'question': q}]}, {})):
        prepare(tmp_path / 'unused', capture, output)
    return output


def test_frozen_export_is_exclusive_deterministic_escaped_and_preserves_full_baseline(tmp_path):
    prepared = prepared_storage(tmp_path)
    first, repeat = tmp_path / 'first', tmp_path / 'repeat'
    summary = export(prepared, first)
    export(prepared, repeat)
    assert summary['constructed_reference_agreements'] == len(CASES)
    assert summary['candidate_allowed'] == summary['new_model_calls'] == 0
    for path in first.iterdir():
        assert path.read_bytes() == (repeat / path.name).read_bytes()
    plan, _ = load(prepared)
    report = json.loads((first / 'report.json').read_bytes())
    assert report['observed'][0]['baseline'] == plan['observed_queries'][0]
    html = (first / 'review.html').read_text(encoding='utf-8')
    assert '&lt;script&gt; DSC' in html and '<form' not in html
    assert html.count('class="case"') == len(CASES) + 1
    with pytest.raises(FileExistsError):
        export(prepared, first)


@pytest.mark.parametrize('variant', ['code', 'input', 'plan_hash', 'phase', 'metadata'])
def test_frozen_drift_stops_export(tmp_path, variant):
    prepared = prepared_storage(tmp_path)
    path = prepared / 'manifest.json'
    manifest = json.loads(path.read_bytes())
    if variant == 'code':
        manifest['code'] = {}
    elif variant == 'input':
        manifest['inputs'][str(FIXTURE.resolve())] = '0' * 64
    elif variant == 'phase':
        manifest['phase'] = 'other'
    else:
        p = prepared / 'plan.json'
        plan = json.loads(p.read_bytes())
        plan['article_metadata'] = {'injected': {}}
        p.write_text(json.dumps(plan), encoding='utf-8')
        if variant == 'metadata':
            manifest['outputs']['plan.json'] = file_hash(p)
    path.write_text(json.dumps(manifest), encoding='utf-8')
    with pytest.raises(ValueError):
        export(prepared, tmp_path / 'rejected')
