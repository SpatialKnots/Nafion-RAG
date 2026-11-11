"""Freeze guarded delivery and replay saved native answers; no live model/DB calls."""

from __future__ import annotations

import argparse
import html
import importlib.metadata
import json
import sys
from dataclasses import asdict
from pathlib import Path

from app.generation import required_fields_guard_routes as routes
from app.generation.providers import Evidence, GeneratedClaim, ProviderResult
from app.generation.required_fields_guard import VERSION, RequiredFieldsGuardProvider
from scripts import gigachat_answer_smoke as f

BASE = f.ROOT / 'output/required_fields_guard_20261110'
PARENT = f.ROOT / 'output/required_answer_fields_20261110'
PROTOCOL = f.ROOT / 'docs/records/required_fields_guard_2026-11-10_v0.1.md'
IDS = ('Satoh_07', 'Fan_05', 'Satoh_06', 'Fan_10', 'Satoh_03')


def read(path):
    return json.loads(path.read_bytes())


def verify_historical(bindings):
    """Verify old source with exactly one explicit pre-edit-main mapping."""
    old = read(BASE / 'pre_edit_v01/old_app_bindings.json')
    main = str(f.ROOT / 'app/main.py')
    if main in bindings and bindings[main] != old[main]:
        raise ValueError('Unexpected historical main.py identity')
    f.verify({str(BASE / 'pre_edit_v01/main.py') if path == main else path: digest
              for path, digest in bindings.items()})


class ReplayProvider:
    def __init__(self, native):
        self.native, self.calls = native, 0

    def generate(self, *args, **kwargs):
        self.calls += 1
        return self.native


def freeze():
    f.verify_manifest(BASE / 'pre_edit_v01')
    previous = read(BASE / 'pre_edit_v01/old_app_bindings.json')
    verify_historical(previous)
    f.verify_manifest(PARENT / 'input_freeze_v01')
    f.verify_manifest(PARENT / 'review_v01')
    verify_historical(read(PARENT / 'input_freeze_v01/bindings.json'))
    if read(PARENT / 'closed_v01.json')['remaining_allowance'] != 0:
        raise ValueError('Old live scope must stay closed')
    settings = f.configure()
    paths = [*f.ROOT.joinpath('app').rglob('*.py'), *f.ROOT.joinpath('app').rglob('*.yaml'), Path(__file__), PROTOCOL,
        f.ROOT / 'scripts/test_answer_support_20261110.py', f.ROOT / 'scripts/gigachat_answer_smoke.py',
        f.ROOT / 'tests/unit/test_required_fields_guard.py', f.ROOT / 'tests/unit/test_required_fields_guard_routes.py',
        f.ROOT / 'docs/records/guard_transfer_v0.1/README.md',
        f.ROOT / 'docs/records/guard_transfer_v0.1/registration_template.json', f.ROOT / 'pyproject.toml']
    folder = BASE / 'freeze_v01'
    folder.mkdir(exist_ok=False)
    bindings = f.bindings(paths)
    for path in paths:
        target = folder / 'source_snapshot' / path.relative_to(f.ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        f.save(target, path.read_bytes())
    packages = {name: importlib.metadata.version(name) for name in ('fastapi', 'pydantic', 'starlette', 'httpx', 'sqlalchemy')}
    config = {'provider': settings.rag_provider, 'model': settings.rag_model,
              'max_tokens': settings.rag_gigachat_max_tokens, 'timeout_seconds': settings.rag_timeout_seconds,
              'methods_identity_policy': settings.rag_methods_identity_policy}
    content = {'version': VERSION, 'bindings': bindings, 'packages': packages, 'python': sys.version, 'config': config}
    f.write(folder / 'version.json', {**content, 'freeze_id': f.sha(f.encode(content)), 'live_model_calls': 0,
        'new_questions_registered': 0, 'new_references_seen': 0, 'transfer_status': 'awaiting_user_prepared_references',
        'historical_main_mapping': {'original_path': str(f.ROOT / 'app/main.py'),
            'historical_sha256': previous[str(f.ROOT / 'app/main.py')],
            'snapshot': str(BASE / 'pre_edit_v01/main.py'), 'current_sha256': f.sha((f.ROOT / 'app/main.py').read_bytes())}})
    f.write(folder / 'bindings.json', bindings)
    f.manifest(folder)
    return {'freeze_id': read(folder / 'version.json')['freeze_id'], 'app_python_files': len(list(f.ROOT.joinpath('app').rglob('*.py'))),
            'new_model_calls': 0, 'new_questions_registered': 0}


def replay():
    frozen = BASE / 'freeze_v01'
    f.verify_manifest(frozen)
    f.verify(read(frozen / 'bindings.json'))
    folder = BASE / 'review_v01'
    folder.mkdir(exist_ok=False)
    rows, bindings, panels = [], [frozen / 'manifest.json', PARENT / 'closed_v01.json'], []
    for cid in IDS:
        live, prepared = PARENT / 'live' / cid, PARENT / 'input_freeze_v01' / cid
        f.verify_manifest(live)
        inp, original = read(prepared / 'input.json'), read(live / 'provider_result.json')
        native = ProviderResult(original['answerable'], [GeneratedClaim(**c) for c in original['claims']],
                                original['provider'], original['model'])
        before = f.encode(asdict(native))
        provider, reviews = ReplayProvider(native), []
        delivered = RequiredFieldsGuardProvider(provider, on_review=reviews.append).generate(
            inp['question'], [Evidence(**e) for e in inp['evidence']], answer_language='ru')
        if provider.calls != 1 or len(reviews) != 1 or f.encode(asdict(native)) != before:
            raise ValueError('Replay altered the source result or repeated generation')
        reviewed = reviews[0]
        payload = {'delivery_status': reviewed['decision'], 'review': reviewed,
            'answer': {'answer': '\n\n'.join(c.text for c in delivered.claims) if delivered.answerable else None,
                       'status': 'answered' if delivered.answerable else 'insufficient_evidence',
                       'claims': [asdict(c) for c in delivered.claims]}}
        rows.append({'id': cid, 'payload': payload, 'delivered_result': asdict(delivered),
                     'execution': 'offline saved-native replay; not new model/API output', 'new_model_calls': 0})
        panels.append('<h2>' + html.escape(cid) + '</h2>' + routes.render(payload))
        bindings.extend([live / 'manifest.json', live / 'provider_result.json', live / 'response.bin', prepared / 'input.json'])
    report = {'cases': rows, 'freeze_id': read(frozen / 'version.json')['freeze_id'], 'new_model_calls': 0,
              'new_oauth_calls': 0, 'new_DB_calls': 0, 'bindings': f.bindings(bindings),
              'scope': 'saved exposed development answers; guard delivery is not scientific acceptance'}
    f.write(folder / 'report.json', report)
    body = ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>ARIADNE: защита выдачи</title>'
        '<style>body{font:16px system-ui;margin:24px;color:#18333f}pre{white-space:pre-wrap;overflow-wrap:anywhere}'
        'section{border:1px solid #abc;padding:12px;margin:12px 0}</style><h1>Экспериментальная защита выдачи</h1>'
        '<p>Offline replay пяти сохранённых ответов. Новых model/OAuth/DB calls0. '
        'Четыре ответа сохранены, Fan05 удержан из-за неустановленного механизма. '
        'Это не 4/5 научной точности и не новые API результаты.</p>' + ''.join(panels) + '</html>')
    f.save(folder / 'review.html', body.encode())
    f.manifest(folder)
    f.verify(read(frozen / 'bindings.json'))
    return {'cases': len(rows), 'retained': sum(r['delivered_result']['answerable'] for r in rows),
            'withheld': sum(r['payload']['review']['withheld'] for r in rows), 'new_model_calls': 0}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('freeze', 'replay'))
    args = parser.parse_args()
    policy = f.NetworkPolicy()
    sys.dont_write_bytecode = True
    sys.addaudithook(policy)
    print(json.dumps(freeze() if args.mode == 'freeze' else replay()), flush=True)
