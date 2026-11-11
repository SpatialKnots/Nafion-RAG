"""Reproduce old/new preparations on all 30 frozen cases; no real transport."""

from __future__ import annotations

import importlib.util
import json
import sys
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

from scripts import bilingual_lexical_admission_20261110 as replay
from scripts import gigachat_answer_smoke as f
from scripts import quantitative_binding_20261111 as previous

BASE = f.ROOT / 'output/kondo_potential_method_20261111'
PARENT = f.ROOT / 'output/nambu_identity_20261111/comparison_v01'


def read(path):
    return json.loads(path.read_bytes())


def main():
    from app.generation import answer_facts, service
    from app.generation.providers import Evidence, GenerationOutputError

    settings = f.configure()
    frozen = BASE / 'pre_edit_v01'
    f.verify_manifest(frozen)
    f.verify(read(frozen / 'parent_bindings.json'))
    f.verify_manifest(PARENT)
    app = f.bindings([*f.ROOT.joinpath('app').rglob('*.py'), *f.ROOT.joinpath('app').rglob('*.yaml')])
    before = read(frozen / 'app_bindings.json')
    changed = {str(f.ROOT / 'app/generation/quantitative_facts.py'), str(f.ROOT / 'app/retrieval/source_reference.py')}
    if ({p for p in before if before[p] != app.get(p)} != changed
            or set(app) - set(before) != {str(f.ROOT / 'app/generation/potential_method.py')}):
        raise ValueError('Unexpected app patch scope')
    spec = importlib.util.spec_from_file_location('app.generation._order_baseline', frozen / 'quantitative_facts.py')
    old = importlib.util.module_from_spec(spec)
    old.__file__ = str(f.ROOT / 'app/generation/quantitative_facts.py')
    sys.modules[spec.name] = old
    spec.loader.exec_module(old)
    out = BASE / 'comparison_v01'
    out.mkdir(exist_ok=False)
    rows = []
    from app.retrieval.search import SearchResult
    from app.retrieval.source_reference import rank_context
    pools = {c['id']: c['rows'] for c in read(BASE / 'capture_v01/cases.json')}
    for parent in read(PARENT / 'result.json')['cases']:
        cid = parent['id']
        api, expected = read(PARENT / cid / 'api_request.json'), read(PARENT / cid / 'after.json')
        expected_native = (PARENT / cid / 'request_unsent.json').read_bytes() if parent['after_ready'] else None
        with patch.object(service, 'prepare_quantitative_facts', old.prepare):
            prior, prior_native = replay.run_service(service, api, expected['trace'], settings)
        if prior != expected or prior_native != expected_native:
            raise ValueError('Baseline reconstruction differs: ' + cid)
        inputs = deepcopy(expected['trace'])
        selected, role_metadata = rank_context(api['question'], [SearchResult(**r) for r in pools[cid]], top_k=api['top_k'])
        inputs['retrieval']['results'] = [asdict(r) for r in selected]
        inputs['retrieval']['metadata']['explicit_source_reference'].update(role_metadata)
        if cid != 'Kondo_02' and inputs != expected['trace']:
            raise ValueError('Other retrieval changed: ' + cid)
        current, native = replay.run_service(service, api, inputs, settings)
        if cid != 'Kondo_02' and (current != prior or native != prior_native):
            raise ValueError('Other case changed: ' + cid)
        folder = out / cid
        folder.mkdir()
        for name, value in (('api_request', api), ('before', prior), ('after', current)):
            f.write(folder / (name + '.json'), value)
        if native:
            f.save(folder / 'request_unsent.json', native)
        if cid == 'Kondo_02':
            if not current['generation_reached'] or prior['generation_reached']:
                raise ValueError('Order preparation not newly ready')
            evidence = [Evidence(**e) for e in current['trace']['evidence']]
            record = answer_facts.selection_records(evidence)['F1']
            raw = read(previous.CAPTURE / 'chunks.json')[evidence[0].chunk_id]
            answer_facts.verify_raw_binding(evidence[0].text, raw['text'], article_id=evidence[0].article_id,
                chunk_id=evidence[0].chunk_id, citation_id=evidence[0].citation_id, page_start=evidence[0].page_start,
                page_end=evidence[0].page_end, source_type=raw['source_type'])
            anchors = []
            for fact in record['facts']:
                for anchor in [fact['support'], *[v['source'] for v in (
                        fact['sample'], fact['value'], fact['unit'], fact['method'], *fact['conditions'].values()) if v]]:
                    if raw['text'][anchor['start']:anchor['end']] != anchor['text']:
                        raise ValueError('Raw field/header anchor differs')
                    anchors.append(anchor)
            with patch.object(service, 'prepare_quantitative_facts', old.prepare):
                ranking_only, _ = replay.run_service(service, api, inputs, settings)
            contract_only, _ = replay.run_service(service, api, expected['trace'], settings)
            if ranking_only['generation_reached'] or contract_only['generation_reached']:
                raise ValueError('Ablation unexpectedly ready')
            f.write(folder / 'ablation.json', {'ranking_only_ready': False, 'contract_only_ready': False, 'both_ready': True})
            selected = previous.synthetic(service, api, inputs['retrieval'], 'select', settings)
            abstained = previous.synthetic(service, api, inputs['retrieval'], 'abstain', settings)
            if selected['status'] != 'answered' or abstained['status'] != 'insufficient_evidence':
                raise ValueError('Synthetic selection boundary differs')
            try:
                previous.synthetic(service, api, inputs['retrieval'], 'invalid', settings)
            except GenerationOutputError:
                pass
            else:
                raise ValueError('Unbound prose admitted')
            f.write(folder / 'source_audit.json', {'record': record, 'anchors_checked': len(anchors),
                'raw_sha256': f.sha(raw['text'].encode()), 'native_bytes': len(native), 'native_sha256': f.sha(native)})
            f.write(folder / 'synthetic.json', {'execution': 'SYNTHETIC, not real model answers',
                'selection': selected, 'abstention': abstained, 'invalid_prose_rejected': True})
        row = {'id': cid, 'question': api['question'], 'before_ready': prior['generation_reached'],
            'after_ready': current['generation_reached'], 'full_result_unchanged': current == prior,
            'native_unchanged': native == prior_native, 'scientific_accuracy': None}
        rows.append(row)
        f.write(folder / 'result.json', row)
        f.manifest(folder)
        print(json.dumps({k: row[k] for k in ('id', 'before_ready', 'after_ready')}), flush=True)
    result = {'cases': rows, 'before_ready': sum(r['before_ready'] for r in rows),
        'after_ready': sum(r['after_ready'] for r in rows),
        'newly_ready': [r['id'] for r in rows if r['after_ready'] and not r['before_ready']],
        'real_model_calls': 0, 'real_oauth_calls': 0, 'new_slots': 0, 'scientific_accuracy': None}
    f.write(out / 'result.json', result)
    f.verify(app)
    f.write(out / 'bindings.json', {**app, **f.bindings([Path(__file__), PARENT / 'manifest.json',
        f.ROOT / 'app/resources/reviewed_pdf_glyph_aliases_v01.json',
        f.ROOT / 'app/resources/reviewed_conductivity_glyph_aliases_v01.json', f.ROOT / 'pyproject.toml',
        f.ROOT / 'app/resources/reviewed_best_ce_glyph_aliases_v01.json', BASE / 'capture_v01/manifest.json'])})
    f.manifest(out)
    print(json.dumps({k: v for k, v in result.items() if k != 'cases'}))


if __name__ == '__main__':
    sys.dont_write_bytecode = True
    policy = f.NetworkPolicy()
    sys.addaudithook(policy)
    main()
    if policy.denied:
        raise ValueError('Unexpected external network attempt')
