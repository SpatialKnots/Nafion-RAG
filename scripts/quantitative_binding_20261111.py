"""Frozen source comparison and explicit synthetic selections; no dispatch mode."""

from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import asdict, replace
from pathlib import Path
from unittest.mock import patch

from scripts import bilingual_lexical_admission_20261110 as replay
from scripts import gigachat_answer_smoke as f

BASE = f.ROOT / 'output/quantitative_binding_20261111'
PARENT = f.ROOT / 'output/refusal_groups_20261110/comparison_v01'
CAPTURE = f.ROOT / 'output/refusal_groups_20261110/capture_v01'


def read(path):
    return json.loads(path.read_bytes())


def synthetic(module, api, retrieval, mode, settings):
    from app.generation.providers import GeneratedClaim, ProviderResult
    from app.retrieval.search import SearchResponse, SearchResult
    class Provider:
        calls = 0
        def generate(self, question, evidence, **kwargs):
            self.calls += 1
            return ProviderResult(mode != 'abstain', [] if mode == 'abstain' else [
                GeneratedClaim('F1' if mode == 'select' else 'Invented numerical prose.', [evidence[0].citation_id])],
                'SYNTHETIC', 'not_a_real_model_result')
    provider = Provider()
    raw = SearchResponse(**{**retrieval, 'results': [SearchResult(**r) for r in retrieval['results']]})
    with patch.object(module, 'search_chunks', lambda *a, **kw: raw):
        result = module.answer_question(replay.NoDB(), settings, **api, provider=provider)
    if provider.calls != 1:
        raise ValueError('Synthetic selection must invoke its stub exactly once')
    return module.answer_response_to_dict(result)


def main():
    from app.generation import answer_facts, service
    from app.generation.providers import Evidence, GenerationOutputError
    settings = f.configure()
    frozen = BASE / 'pre_edit_v01'
    f.verify_manifest(frozen)
    f.verify(read(frozen / 'bindings.json'))
    app = f.bindings([*f.ROOT.joinpath('app').rglob('*.py'), *f.ROOT.joinpath('app').rglob('*.yaml')])
    before = read(frozen / 'app_bindings.json')
    changed = {str(f.ROOT / p) for p in ('app/generation/service.py', 'app/generation/answer_facts.py',
                                       'app/evaluation/query_packet_run.py')}
    if {p for p in before if before[p] != app.get(p)} != changed:
        raise ValueError('Unexpected old app source changed')
    if set(app) - set(before) != {str(f.ROOT / 'app/generation/quantitative_facts.py')}:
        raise ValueError('Unexpected new app module')
    name = 'app.generation._quantitative_baseline'
    spec = importlib.util.spec_from_file_location(name, frozen / 'service.py')
    old = importlib.util.module_from_spec(spec)
    sys.modules[name] = old
    spec.loader.exec_module(old)
    folder = BASE / 'comparison_v05'
    folder.mkdir(exist_ok=False)
    records = []
    for case in read(CAPTURE / 'cases.json'):
        cid = case['case']['id']
        prior = PARENT / cid
        f.verify_manifest(prior)
        expected = read(prior / 'after.json')
        api = read(replay.PARENT / cid / 'api_request.json')
        baseline, before_native = replay.run_service(old, api, expected['trace'], settings)
        old_native = (prior / 'request_unsent.json').read_bytes() if (prior / 'request_unsent.json').exists() else None
        if baseline != expected or before_native != old_native:
            raise ValueError('Baseline reconstruction differs: ' + cid)
        current, native = replay.run_service(service, api, expected['trace'], settings)
        if baseline['generation_reached'] and (current != baseline or native != before_native):
            raise ValueError('Previously ready full trace/native changed: ' + cid)
        if current['trace']['retrieval'] != baseline['trace']['retrieval']:
            raise ValueError('Retrieval changed')
        out = folder / cid
        out.mkdir()
        f.write(out / 'api_request.json', api)
        f.write(out / 'before.json', baseline)
        f.write(out / 'after.json', current)
        if native:
            f.save(out / 'request_unsent.json', native)
        newly = current['generation_reached'] and not baseline['generation_reached']
        quantitative = current['trace']['metadata'].get('quantitative_source_binding')
        if newly:
            evidence = [Evidence(**e) for e in current['trace']['evidence']]
            parsed = answer_facts.selection_records(evidence)
            payload = json.loads(evidence[0].text)
            chunk = read(CAPTURE / 'chunks.json')[evidence[0].chunk_id]
            answer_facts.verify_raw_binding(evidence[0].text, chunk['text'], article_id=evidence[0].article_id,
                chunk_id=evidence[0].chunk_id, citation_id=evidence[0].citation_id,
                page_start=evidence[0].page_start, page_end=evidence[0].page_end, source_type=chunk['source_type'])
            for record in parsed.values():
                for fact in record['facts']:
                    anchors = [fact['support'], *[v['source'] for v in
                        (fact['sample'], fact['value'], fact['unit'], fact['method'], *fact['conditions'].values()) if v]]
                    for anchor in anchors:
                        if (payload['raw_source'][anchor['start']:anchor['end']] != anchor['text']
                                or f.sha(payload['raw_source'].encode()) != anchor['raw_chunk_sha256']):
                            raise ValueError('Quantity/condition/support anchor drift')
            selected = synthetic(service, api, baseline['trace']['retrieval'], 'select', settings)
            abstained = synthetic(service, api, baseline['trace']['retrieval'], 'abstain', settings)
            if selected['status'] != 'answered' or abstained['status'] != 'insufficient_evidence':
                raise ValueError('Synthetic contract selection boundary differs')
            try:
                synthetic(service, api, baseline['trace']['retrieval'], 'invalid', settings)
            except GenerationOutputError:
                invalid_rejected = True
            else:
                raise ValueError('Synthetic unbound numerical prose admitted')
            f.write(out / 'synthetic_selection.json', {'execution': 'SYNTHETIC; not a new model answer',
                'selected': selected, 'abstained': abstained, 'invalid_prose_rejected': invalid_rejected,
                'native_records': parsed, 'original_display_sources': [asdict(replace(evidence[0],
                    text=payload['raw_source'], source_type=payload['raw_source_type']))]})
        row = {'id': cid, 'question': case['case']['question'], 'before_ready': baseline['generation_reached'],
               'after_ready': current['generation_reached'], 'newly_ready': newly, 'quantitative': quantitative,
               'native_unchanged': native == before_native, 'full_result_unchanged': current == baseline,
               'model_calls': 0, 'oauth_calls': 0, 'scientific_accuracy': None}
        f.write(out / 'result.json', row)
        f.manifest(out)
        records.append(row)
        print(json.dumps({k: row[k] for k in ('id', 'before_ready', 'after_ready')}), flush=True)
    f.verify(app)
    result = {'cases': records, 'before_ready': sum(r['before_ready'] for r in records),
              'after_ready': sum(r['after_ready'] for r in records), 'newly_ready': [r['id'] for r in records if r['newly_ready']],
              'synthetic_service_controls': sum(r['newly_ready'] for r in records) * 3,
              'model_calls': 0, 'oauth_calls': 0, 'DB_queries': 0, 'accuracy': None}
    f.write(folder / 'result.json', result)
    f.write(folder / 'bindings.json', {**app, **f.bindings([Path(__file__), CAPTURE / 'manifest.json',
                                                         PARENT / 'manifest.json', frozen / 'manifest.json'])})
    f.manifest(folder)
    print(json.dumps({k: v for k, v in result.items() if k != 'cases'}))


if __name__ == '__main__':
    sys.dont_write_bytecode = True
    policy = f.NetworkPolicy()
    sys.addaudithook(policy)
    main()
    if policy.denied:
        raise ValueError('External network attempted')
