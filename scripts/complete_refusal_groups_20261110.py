"""Annotation-guided offline source packets: one explicit extra raw chunk at most."""

from __future__ import annotations

import json
from pathlib import Path

from scripts import gigachat_answer_smoke as f
from scripts import refusal_groups_20261110 as capture


def main():
    base = capture.BASE
    f.verify_manifest(base / 'review_v01')
    f.verify(capture.read(base / 'review_v01/bindings.json'))
    f.verify_manifest(base / 'comparison_v01')
    f.verify(capture.read(base / 'comparison_v01/bindings.json'))
    analysis = capture.read(base / 'comparison_v01/result.json')['analysis_after']
    cases = {c['case']['id']: c for c in capture.read(base / 'comparison_v01/cases_after.json')}
    proposals = {p['id']: p for p in capture.read(base / 'review_v01/context_action_proposals.json')}
    chunks = capture.read(base / 'capture_v01/chunks.json')
    folder = base / 'diagnostic_packets_v01'
    folder.mkdir(exist_ok=False)
    summaries = []
    for row in analysis:
        cid = row['id']
        case = cases[cid]
        existing = case['preparation']['trace']['evidence']
        sources = [{'kind': 'existing_selected', 'chunk_id': e['chunk_id'], 'article_id': e['article_id'],
                    'page_start': e['page_start'], 'page_end': e['page_end'], 'source_type': e['source_type'],
                    'text_layer': chunks[e['chunk_id']]['text_layer'], 'text': e['text']} for e in existing]
        action = None
        if cid in proposals:
            chosen = proposals[cid]['candidate']
            if chosen != chunks[chosen['chunk_id']] or chosen['article_id'] != case['case']['article_id']:
                raise ValueError('Context candidate differs from exact registered work/layer')
            if len(chosen['text']) > 14000:
                raise ValueError('Explicit extra-source budget exceeded')
            action = {'kind': 'append_one_registered_raw_chunk_offline', 'chunk_id': chosen['chunk_id'],
                      'raw_sha256': f.sha(chosen['text'].encode()), 'added_chars': len(chosen['text']),
                      'DB_lookups': 0, 'retrieval_executions': 0, 'provider_calls': 0,
                      'selection_origin': 'assistant post-hoc requirements; not natural retrieval performance'}
            sources.append({'kind': 'explicit_offline_addition', **chosen})
        if sum(len(s['text']) for s in sources) > 60000:
            raise ValueError('Diagnostic packet character ceiling exceeded')
        witnesses = []
        for observation in row['observations']:
            matches = []
            for source in sources:
                if observation['quote'] in source['text']:
                    start = source['text'].index(observation['quote'])
                    matches.append({'chunk_id': source['chunk_id'], 'start': start,
                                    'end': start + len(observation['quote']), 'kind': source['kind'],
                                    'raw_sha256': f.sha(source['text'].encode())})
            if not matches:
                raise ValueError('Annotated source requirement still unresolved: ' + cid)
            witnesses.append({'requirement': observation['label'], 'raw_quote': observation['quote'],
                              'matches': matches, 'semantic_support': 'assistant_source_review_only',
                              'scientific_validity': 'not_independently_evaluated'})
        packet = {'id': cid, 'question': case['case']['question'], 'group': row['group'], 'sources': sources,
                  'source_observations': witnesses, 'action_executed_offline': action,
                  'admission_changed': False, 'generation_input_approved': False, 'automatic_continuation': False,
                  'extra_chunk_budget': 1, 'extra_chars_ceiling': 14000, 'total_chars_ceiling': 60000,
                  'model_calls': 0, 'oauth_calls': 0, 'new_slots': 0}
        out = folder / cid
        out.mkdir()
        f.write(out / 'packet.json', packet)
        f.manifest(out)
        summaries.append({'id': cid, 'source_requirements_covered': len(witnesses),
                          'existing_sources': len(existing), 'extra_sources': int(action is not None),
                          'all_annotated_witnesses_present': True, 'normal_API_admission_changed': False})
    result = {'cases': summaries, 'case_count': len(summaries), 'explicit_offline_actions': sum(s['extra_sources'] for s in summaries),
              'all_annotated_witnesses_present': True, 'model_calls': 0, 'oauth_calls': 0, 'new_DB_queries': 0,
              'new_retrieval_executions': 0, 'new_slots': 0, 'scientific_accuracy': None,
              'scope': 'Annotation-guided diagnostic upper bound; not automatic runtime completion or scientific sufficiency.'}
    f.write(folder / 'summary.json', result)
    f.write(folder / 'bindings.json', f.bindings([Path(__file__), base / 'review_v01/manifest.json',
                                                base / 'comparison_v01/manifest.json', base / 'capture_v01/manifest.json']))
    f.manifest(folder)
    print(json.dumps({k: v for k, v in result.items() if k != 'cases'}))


if __name__ == '__main__':
    main()
