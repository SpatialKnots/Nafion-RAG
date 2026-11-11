"""Compare all30 current-parent preparations with exact-source glyph data repair."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import patch

from scripts import bilingual_lexical_admission_20261110 as replay
from scripts import gigachat_answer_smoke as f
from scripts import quantitative_binding_20261111 as old_run
from scripts.peng_glyph_probe_20261111 import BASE, PARENT


def read(path):
    return json.loads(path.read_bytes())


def main():
    from app.generation import answer_facts, service
    from app.generation.providers import Evidence, GenerationOutputError

    settings = f.configure()
    frozen = BASE / 'pre_edit_v01'
    f.verify_manifest(frozen)
    before = read(frozen / 'app_bindings.json')
    app = f.bindings([*f.ROOT.joinpath('app').rglob('*.py'), *f.ROOT.joinpath('app').rglob('*.yaml')])
    changed = {str(f.ROOT / p) for p in ('app/generation/quantitative_facts.py', 'app/ui.py',
                                      'app/generation/required_fields_guard_routes.py')}
    if {p for p in before if before[p] != app.get(p)} != changed or set(app) - set(before) != {
            str(f.ROOT / 'app/generation/reviewed_glyphs.py')}:
        raise ValueError('Unexpected app patch scope')
    name = 'app.generation._glyph_baseline'
    spec = importlib.util.spec_from_file_location(name, frozen / 'quantitative_facts.py')
    baseline = importlib.util.module_from_spec(spec)
    sys.modules[name] = baseline
    spec.loader.exec_module(baseline)
    folder = BASE / 'comparison_v02'
    folder.mkdir(exist_ok=False)
    rows = []
    for previous in read(PARENT / 'result.json')['cases']:
        cid = previous['id']
        expected = read(PARENT / cid / 'after.json')
        api = read(PARENT / cid / 'api_request.json')
        with patch.object(service, 'prepare_quantitative_facts', baseline.prepare):
            prior, prior_native = replay.run_service(service, api, expected['trace'], settings)
        expected_native = (PARENT / cid / 'request_unsent.json').read_bytes() if previous['after_ready'] else None
        if prior != expected or prior_native != expected_native:
            raise ValueError('Prior baseline differs: ' + cid)
        current, native = replay.run_service(service, api, expected['trace'], settings)
        if current['trace']['retrieval'] != prior['trace']['retrieval']:
            raise ValueError('Retrieval changed')
        if previous['after_ready'] and (current != prior or native != prior_native):
            raise ValueError('Prior ready full trace/native changed: ' + cid)
        out = folder / cid
        out.mkdir()
        f.write(out / 'api_request.json', api)
        f.write(out / 'before.json', prior)
        f.write(out / 'after.json', current)
        if native:
            f.save(out / 'request_unsent.json', native)
        newly = current['generation_reached'] and not prior['generation_reached']
        if newly:
            evidence = [Evidence(**e) for e in current['trace']['evidence']]
            record = answer_facts.selection_records(evidence)['F1']
            raw = read(old_run.CAPTURE / 'chunks.json')[evidence[0].chunk_id]
            answer_facts.verify_raw_binding(evidence[0].text, raw['text'], article_id=evidence[0].article_id,
                chunk_id=evidence[0].chunk_id, citation_id=evidence[0].citation_id,
                page_start=evidence[0].page_start, page_end=evidence[0].page_end, source_type=raw['source_type'])
            selected = old_run.synthetic(service, api, expected['trace']['retrieval'], 'select', settings)
            abstained = old_run.synthetic(service, api, expected['trace']['retrieval'], 'abstain', settings)
            if selected['status'] != 'answered' or abstained['status'] != 'insufficient_evidence':
                raise ValueError('Synthetic selection boundary differs')
            try:
                old_run.synthetic(service, api, expected['trace']['retrieval'], 'invalid', settings)
            except GenerationOutputError:
                invalid_rejected = True
            else:
                raise ValueError('Unbound prose admitted')
            f.write(out / 'synthetic_selection.json', {'execution': 'SYNTHETIC, not a real model answer',
                'selected': selected, 'abstained': abstained, 'unbound_prose_rejected': invalid_rejected,
                'record': record})
        row = {'id': cid, 'question': api['question'], 'before_ready': prior['generation_reached'],
            'after_ready': current['generation_reached'], 'newly_ready': newly,
            'full_result_unchanged': current == prior, 'native_unchanged': native == prior_native,
            'model_calls': 0, 'oauth_calls': 0, 'scientific_accuracy': None}
        rows.append(row)
        f.write(out / 'result.json', row)
        f.manifest(out)
        print(json.dumps({k: row[k] for k in ('id', 'before_ready', 'after_ready')}), flush=True)
    f.verify(app)
    result = {'cases': rows, 'before_ready': sum(r['before_ready'] for r in rows),
        'after_ready': sum(r['after_ready'] for r in rows), 'newly_ready': [r['id'] for r in rows if r['newly_ready']],
        'model_calls': 0, 'oauth_calls': 0, 'new_slots': 0, 'accuracy': None}
    f.write(folder / 'result.json', result)
    f.write(folder / 'bindings.json', {**app, **f.bindings([Path(__file__), frozen / 'manifest.json',
        PARENT / 'manifest.json', f.ROOT / 'app/resources/reviewed_pdf_glyph_aliases_v01.json',
        f.ROOT / 'pyproject.toml', f.ROOT / 'tests/fixtures/reviewed_glyph_sources_v01.json'])})
    f.manifest(folder)
    print(json.dumps({k: v for k, v in result.items() if k != 'cases'}))


if __name__ == '__main__':
    sys.dont_write_bytecode = True
    policy = f.NetworkPolicy()
    sys.addaudithook(policy)
    main()
    if policy.denied:
        raise ValueError('External network attempted')
