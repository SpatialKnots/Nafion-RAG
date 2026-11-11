"""Compare exact old/new service preparation on frozen sources; no dispatch mode."""

from __future__ import annotations

import importlib.util
import json
import sys
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

from scripts import gigachat_answer_smoke as f

BASE = f.ROOT / 'output/bilingual_lexical_admission_20261110'
PARENT = f.ROOT / 'output/kondo_metadata_repair_20261110/prepared_v01'
QUESTIONS = f.ROOT / 'output/kondo_nambu_peng_transfer_20261110/input_freeze_v01/questions.json'


def read(path):
    return json.loads(path.read_bytes())


class NoDB:
    def __getattr__(self, name):
        raise AssertionError('Frozen replay forbids fresh DB access: ' + name)


def load_baseline():
    name = 'app.generation._bilingual_baseline_service'
    spec = importlib.util.spec_from_file_location(name, BASE / 'pre_edit_v01/service.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def run_service(module, api, raw, settings):
    from app.generation.required_fields_guard import RequiredFieldsGuardProvider
    from app.generation.required_fields_guard_routes import make_provider
    from app.retrieval.search import SearchResponse, SearchResult

    trace, native, reviews = {}, [], []
    provider = make_provider(settings)

    def post(url, body, authorization, *, oauth=False):
        if oauth:
            return b'{"access_token":"offline-preparation-placeholder"}'
        native.append(body)
        raise f.PreparedBoundary()

    provider._post = post
    guarded = RequiredFieldsGuardProvider(provider, on_review=reviews.append)

    def observe(retrieval, evidence, metadata):
        trace.update(retrieval=asdict(retrieval), evidence=[asdict(e) for e in evidence], metadata=metadata)

    payload = deepcopy(raw['retrieval'])
    retrieval = SearchResponse(**{**payload, 'results': [SearchResult(**r) for r in payload['results']]})
    result, reached = None, False
    with patch.object(module, 'search_chunks', lambda *a, **kw: deepcopy(retrieval)):
        try:
            answer = module.answer_question(NoDB(), settings, **api, provider=guarded, trace_observer=observe)
            result = module.answer_response_to_dict(answer)
        except f.PreparedBoundary:
            reached = True
    if not trace or len(native) != int(reached):
        raise ValueError('Missing trace/native boundary or repeated generation')
    return {'trace': trace, 'generation_reached': reached, 'answer': result}, native[0] if native else None


def main():
    from app.generation import service
    settings = f.configure()
    f.verify_manifest(BASE / 'pre_edit_v01')
    f.verify(read(BASE / 'pre_edit_v01/parent_bindings.json'))
    before = read(BASE / 'pre_edit_v01/app_bindings.json')
    app = f.bindings([*f.ROOT.joinpath('app').rglob('*.py'), *f.ROOT.joinpath('app').rglob('*.yaml')])
    changed = [path for path in before if before[path] != app.get(path)]
    added = list(set(app) - set(before))
    if changed != [str(f.ROOT / 'app/generation/service.py')] or added != [str(f.ROOT / 'app/generation/bilingual_lexical.py')]:
        raise ValueError('Unexpected app changes')
    old = load_baseline()
    folder = BASE / 'comparison_v03'
    folder.mkdir(exist_ok=False)
    rows, bindings = [], [QUESTIONS, BASE / 'pre_edit_v01/manifest.json']
    for case in read(QUESTIONS)['cases']:
        cid = case['id']
        prior = PARENT / cid
        f.verify_manifest(prior)
        api, trace = read(prior / 'api_request.json'), read(prior / 'trace.json')
        baseline, old_native = run_service(old, api, trace, settings)
        if baseline['trace'] != trace:
            raise ValueError('Historical full trace reconstruction differs: ' + cid)
        expected_native = (prior / 'request.json').read_bytes() if (prior / 'request.json').exists() else None
        if old_native != expected_native:
            raise ValueError('Historical native reconstruction differs: ' + cid)
        if baseline['answer'] is not None and baseline['answer'] != read(prior / 'preparation_api_response.json')['body']['answer']:
            raise ValueError('Historical refusal reconstruction differs: ' + cid)
        current, native = run_service(service, api, trace, settings)
        if current['trace']['retrieval'] != trace['retrieval'] or current['trace']['evidence'] != trace['evidence']:
            raise ValueError('Retrieval/selected raw evidence changed: ' + cid)
        if baseline['generation_reached'] and (not current['generation_reached'] or native != old_native or current != baseline):
            raise ValueError('Previously ready preparation changed: ' + cid)
        path = folder / cid
        path.mkdir()
        f.write(path / 'before.json', baseline)
        f.write(path / 'after.json', current)
        if native is not None:
            f.save(path / 'request_unsent.json', native)
        bridge = current['trace']['metadata']['evidence_adequacy'].get('bilingual_lexical_coverage')
        if bridge:
            sources = {e['citation_id']: e for e in trace['evidence']}
            for witness in bridge['witnesses']:
                source = sources[witness['citation_id']]
                if f.sha(source['text'].encode()) != witness['raw_text_sha256'] or source['article_id'] != witness['article_id']:
                    raise ValueError('Unbound source witness')
                for hit in (*witness['concept_matches'].values(), *witness['identifier_matches'].values()):
                    if source['text'][hit['start']:hit['end']] != hit['text']:
                        raise ValueError('Source quote drift')
                    if source['text'][hit['context_start']:hit['context_end']] != hit['context_text']:
                        raise ValueError('Source context drift')
                count = witness['item_count_match']
                if count and source['text'][count['start']:count['end']] != count['text']:
                    raise ValueError('Source item chain drift')
        row = {'id': cid, 'question': case['question'], 'before_reached': baseline['generation_reached'],
               'after_reached': current['generation_reached'], 'before_reason': trace['metadata']['evidence_adequacy']['reason'],
               'after_reason': current['trace']['metadata']['evidence_adequacy']['reason'],
               'bridge': bridge, 'raw_evidence_unchanged': True, 'native_unchanged': native == old_native,
               'scientific_accuracy': None, 'model_calls': 0, 'oauth_calls': 0}
        f.write(path / 'result.json', row)
        f.manifest(path)
        rows.append(row)
        bindings.append(prior / 'manifest.json')
        print(json.dumps({k: row[k] for k in ('id', 'before_reached', 'after_reached', 'after_reason')}), flush=True)
    f.verify(app)
    summary = {'cases': rows, 'before_ready': sum(r['before_reached'] for r in rows),
               'after_ready': sum(r['after_reached'] for r in rows),
               'newly_ready': [r['id'] for r in rows if r['after_reached'] and not r['before_reached']],
               'model_calls': 0, 'oauth_calls': 0, 'DB_calls': 0,
               'scope': 'Frozen retrieval; actual old/new service/native preparation, not fresh search or new answers.'}
    f.write(folder / 'summary.json', summary)
    f.write(folder / 'bindings.json', {**app, **f.bindings([*bindings, Path(__file__)])})
    f.manifest(folder)
    print(json.dumps({k: v for k, v in summary.items() if k != 'cases'}))


if __name__ == '__main__':
    sys.dont_write_bytecode = True
    policy = f.NetworkPolicy()
    sys.addaudithook(policy)
    main()
    if policy.denied:
        raise ValueError('External network attempt during frozen comparison')
