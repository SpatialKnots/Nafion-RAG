"""Exact baseline reconstruction, conservative source recovery and per-group audit."""

from __future__ import annotations

import importlib.util
import json
import sys
from copy import deepcopy
from pathlib import Path

from scripts import assess_refusal_groups_20261110 as assess
from scripts import bilingual_lexical_admission_20261110 as parent
from scripts import gigachat_answer_smoke as f
from scripts import refusal_groups_20261110 as capture


def main():
    from app.generation import service
    source = capture.BASE / 'capture_v01'
    f.verify_manifest(source)
    f.verify(capture.read(source / 'bindings.json'))
    settings = f.configure()
    app = f.bindings([*f.ROOT.joinpath('app').rglob('*.py'), *f.ROOT.joinpath('app').rglob('*.yaml')])
    before = capture.read(source / 'app_bindings.json')
    if {p for p in before if before[p] != app.get(p)} != {str(f.ROOT / 'app/generation/service.py')}:
        raise ValueError('Unexpected previous app file changed')
    if set(app) - set(before) != {str(f.ROOT / 'app/generation/evidence_preservation.py')}:
        raise ValueError('Unexpected new app file')
    name = 'app.generation._refusal_groups_baseline'
    spec = importlib.util.spec_from_file_location(name, source / 'service.py')
    old = importlib.util.module_from_spec(spec)
    sys.modules[name] = old
    spec.loader.exec_module(old)
    folder = capture.BASE / 'comparison_v01'
    folder.mkdir(exist_ok=False)
    original = capture.read(source / 'cases.json')
    after_cases, records = deepcopy(original), []
    for before_case, after_case in zip(original, after_cases, strict=True):
        cid = before_case['case']['id']
        previous = parent.BASE / 'comparison_v03' / cid
        api = capture.read(parent.PARENT / cid / 'api_request.json')
        trace = before_case['preparation']['trace']
        baseline, old_native = parent.run_service(old, api, trace, settings)
        expected = capture.read(previous / 'after.json')
        if baseline != expected:
            raise ValueError('Old whole service reconstruction differs: ' + cid)
        expected_native = (previous / 'request_unsent.json').read_bytes() if (previous / 'request_unsent.json').exists() else None
        if old_native != expected_native:
            raise ValueError('Old native reconstruction differs: ' + cid)
        current, native = parent.run_service(service, api, trace, settings)
        if current['generation_reached'] != baseline['generation_reached']:
            raise ValueError('Information recovery changed admission: ' + cid)
        if not before_case['refused'] and (current != baseline or native != old_native):
            raise ValueError('Previously ready trace/native changed: ' + cid)
        if current['trace']['retrieval'] != baseline['trace']['retrieval']:
            raise ValueError('Retrieval changed')
        for evidence in current['trace']['evidence']:
            row = capture.read(source / 'chunks.json')[evidence['chunk_id']]
            if any(row[k] != evidence[k] for k in ('text', 'article_id', 'page_start', 'page_end', 'source_type')):
                raise ValueError('Raw evidence changed')
        after_case['preparation'] = current
        out = folder / cid
        out.mkdir()
        f.write(out / 'before.json', baseline)
        f.write(out / 'after.json', current)
        if native is not None:
            f.save(out / 'request_unsent.json', native)
        f.manifest(out)
        preservation = current['trace']['metadata'].get('retrieved_raw_preservation')
        records.append({'id': cid, 'ready': current['generation_reached'], 'raw_preservation': preservation,
                        'native_unchanged': native == old_native})
    annotation = capture.read(assess.ANNOTATIONS)
    analysis = assess.evaluate(after_cases, capture.read(source / 'chunks.json'),
                               capture.read(source / 'original_pdf_text.json'), annotation)
    old_analysis = capture.read(capture.BASE / 'assessment_v01/result.json')
    result = {'cases': records, 'analysis_after': analysis,
        'fully_selected_annotated_before': old_analysis['fully_selected_annotated_cases'],
        'fully_selected_annotated_after': sum(r['all_annotated_witnesses_selected'] for r in analysis),
        'ready_before': sum(not r['refused'] for r in original), 'ready_after': sum(r['ready'] for r in records),
        'model_calls': 0, 'oauth_calls': 0, 'fresh_DB_queries': 0, 'scientific_accuracy': None}
    f.verify(app)
    f.write(folder / 'result.json', result)
    f.write(folder / 'cases_after.json', after_cases)
    f.write(folder / 'bindings.json', {**app, **f.bindings([Path(__file__), assess.ANNOTATIONS,
        source / 'manifest.json', capture.BASE / 'assessment_v01/manifest.json'])})
    f.manifest(folder)
    print(json.dumps({k: v for k, v in result.items() if k not in ('cases', 'analysis_after')}))


if __name__ == '__main__':
    sys.dont_write_bytecode = True
    policy = f.NetworkPolicy()
    sys.addaudithook(policy)
    main()
    if policy.denied:
        raise ValueError('External network attempted during refused-context comparison')
