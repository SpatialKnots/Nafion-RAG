"""Literal source/selection boundary audit using explicit exposed source annotations."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

from app.generation.query_qualifiers import occurrences
from scripts import gigachat_answer_smoke as f
from scripts import refusal_groups_20261110 as capture

ANNOTATIONS = f.ROOT / 'docs/records/refusal_groups_annotations_v0.1.json'


def raw_span(text, start, end):
    starts = occurrences(text, start)
    if len(starts) != 1:
        raise ValueError('Start anchor not unique: ' + start + ': ' + str(len(starts)))
    endings = [m for m in occurrences(text, end) if m['end'] >= starts[0]['end']]
    if not endings or endings[0]['end'] - starts[0]['start'] > 3000:
        raise ValueError('End anchor absent or too distant: ' + end)
    left, right = starts[0]['start'], endings[0]['end']
    return {'start': left, 'end': right, 'quote': text[left:right], 'page_text_sha256': f.sha(text.encode())}


def evaluate(cases, chunks, pdfs, annotations):
    indexed = {r['case']['id']: r for r in cases if r['refused']}
    if set(indexed) != {r['id'] for r in annotations['cases']}:
        raise ValueError('Annotations do not match all remaining refusals')
    result = []
    for annotation in annotations['cases']:
        cid = annotation['id']
        case = indexed[cid]
        aid = case['case']['article_id']
        trace = case['preparation']['trace']
        dropped = {r['chunk_id'] for r in trace['metadata']['answer_evidence_deduplication']['dropped']}
        observations = []
        for requirement in annotation['requirements']:
            page = pdfs[aid][requirement['page'] - 1]
            try:
                witness = raw_span(page['text'], requirement['start'], requirement['end'])
            except ValueError as exc:
                raise ValueError(cid + '/' + requirement['label'] + ': ' + str(exc)) from exc
            quote = witness['quote']
            selected = [r['chunk_id'] for r in trace['evidence'] if quote in r['text']]
            retrieved = [r['chunk_id'] for r in trace['retrieval']['results'] if quote in (r['full_text'] or r['snippet'])]
            registered = [rid for rid, r in chunks.items() if r['article_id'] == aid and quote in r['text']]
            if not registered:
                status = 'PDF_only_or_registry_unresolved'
            elif selected:
                status = 'selected_literal_present'
            elif set(retrieved) & dropped:
                status = 'removed_by_deduplication'
            elif retrieved:
                status = 'removed_after_retrieval'
            else:
                status = 'registered_outside_retrieved_top_k'
            observations.append({**requirement, **witness, 'article_id': aid,
                'selected_chunk_ids': selected, 'retrieved_chunk_ids': retrieved, 'registered_chunk_ids': registered,
                'status': status, 'semantic_support': 'assistant_source_context_review_only',
                'scientific_validity': 'not_independently_evaluated'})
        result.append({'id': cid, 'question': case['case']['question'], 'group': annotation['group'],
            'action': annotation['action'], 'observations': observations,
            'all_annotated_witnesses_selected': all(r['selected_chunk_ids'] for r in observations),
            'blockers': sorted({r['status'] for r in observations if not r['selected_chunk_ids']})})
    return result


def run():
    source = capture.BASE / 'capture_v01'
    f.verify_manifest(source)
    f.verify(capture.read(source / 'bindings.json'))
    annotation = capture.read(ANNOTATIONS)
    rows = evaluate(capture.read(source / 'cases.json'), capture.read(source / 'chunks.json'),
                    capture.read(source / 'original_pdf_text.json'), annotation)
    groups = defaultdict(Counter)
    for r in rows:
        groups[r['group']]['count'] += 1
        groups[r['group']]['all_annotated_witnesses_selected'] += r['all_annotated_witnesses_selected']
    result = {'cases': rows, 'intent_groups': groups,
              'fully_selected_annotated_cases': sum(r['all_annotated_witnesses_selected'] for r in rows),
              'observation_statuses': Counter(o['status'] for r in rows for o in r['observations']),
              'source': annotation['origin'], 'accuracy': None, 'model_calls': 0, 'oauth_calls': 0}
    folder = capture.BASE / 'assessment_v01'
    folder.mkdir(exist_ok=False)
    f.write(folder / 'result.json', result)
    f.write(folder / 'bindings.json', f.bindings([ANNOTATIONS, Path(__file__), source / 'manifest.json']))
    f.manifest(folder)
    print(json.dumps({k: v for k, v in result.items() if k not in ('cases', 'source')}))


if __name__ == '__main__':
    run()
