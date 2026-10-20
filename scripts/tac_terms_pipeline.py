"""Rebuild automatic Terms from a changed frozen corpus bundle; publish only complete validated snapshots."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from app.terms.review_store import canonical, current_snapshot, load_snapshot, register_snapshot, sha

VERSION = 'tac_terms_pipeline_v0.1'
INPUTS = ('snapshot', 'profiles', 'metadata', 'boundary_review', 'glossary')


def capture(config: Path, source_root: Path) -> tuple[dict[str, Any], dict[str, bytes], str]:
    raw = config.read_bytes()
    cfg = json.loads(raw)
    if not isinstance(cfg, dict) or set(cfg) - set(INPUTS) - {'review_root'} or not cfg.get('snapshot'):
        raise ValueError('Terms pipeline config requires snapshot and supported input paths only')
    values = {'config': raw}
    for name in INPUTS:
        if cfg.get(name):
            path = (source_root / cfg[name]).resolve()
            if not path.is_relative_to(source_root):
                raise ValueError('Terms pipeline input outside source root: '+name)
            values[name] = path.read_bytes()
    if 'glossary' not in values:
        cfg['glossary'] = 'docs/cross_lingual_glossary.yaml'
        values['glossary'] = (source_root / cfg['glossary']).read_bytes()
    codes = list((source_root/'app/terms').glob('*.py')) + list((source_root/'app/terms').glob('*.json'))
    codes += list((source_root/'scripts').glob('tac_*.py')) + list((source_root/'scripts/terms_graph').glob('*'))
    fingerprint = sha(canonical({'inputs': {n: sha(b) for n,b in values.items()},
                                 'code': {p.relative_to(source_root).as_posix():sha(p.read_bytes()) for p in codes if p.is_file()}}))
    return cfg, values, fingerprint


def invoke(source_root: Path, module: str, *args: str) -> None:
    result = subprocess.run([sys.executable, '-X', 'utf8', '-m', module, *args], cwd=source_root,
                            capture_output=True, text=True, encoding='utf-8', check=False)
    if result.returncode:
        raise RuntimeError(f'{module} failed ({result.returncode}):\n{result.stderr}\n{result.stdout}')


def save_status(review_root: Path, data: dict[str, Any]) -> None:
    path = review_root/'pipeline_status.json'
    temporary = path.with_suffix('.tmp')
    temporary.write_bytes(canonical(dict(schema=VERSION,**data)))
    temporary.replace(path)


def run_once(config: Path, output_root: Path, source_root: Path) -> dict[str, Any]:
    source_root = source_root.resolve()
    output_root = output_root.resolve()
    if not output_root.is_relative_to(source_root):
        raise ValueError('Terms pipeline output outside source root')
    cfg, values, fingerprint = capture(config, source_root)
    review_root = (source_root / cfg.get('review_root', 'data/reviews/terms')).resolve()
    if not review_root.is_relative_to(source_root):
        raise ValueError('Terms pipeline review store outside source root')
    output_root.mkdir(parents=True, exist_ok=True)
    review_root.mkdir(parents=True, exist_ok=True)
    lock = review_root / 'pipeline.lock'
    lock.mkdir()  # Atomic inter-process guard; stale lock is an explicit error, never silently removed.
    try:
        (lock/'owner.json').write_bytes(canonical({'pid':os.getpid(),'fingerprint':fingerprint}))
        previous_path = output_root/'current_run.json'
        if previous_path.exists():
            previous = json.loads(previous_path.read_bytes())
            if previous['fingerprint'] == fingerprint:
                for path, checksum in previous['artifacts'].items():
                    if sha((output_root/path).read_bytes()) != checksum:
                        raise ValueError('Terms pipeline cached artifact checksum mismatch: '+path)
                _, frozen = load_snapshot(review_root, previous['snapshot_id'])
                if current_snapshot(review_root) != previous['snapshot_id']:
                    register_snapshot(review_root, frozen)
                save_status(review_root,dict(state='ready',snapshot_id=previous['snapshot_id'],fingerprint=fingerprint))
                return dict(state='unchanged', snapshot_id=previous['snapshot_id'], fingerprint=fingerprint)
        run = output_root/'runs'/(fingerprint[:16]+'-'+uuid.uuid4().hex[:8])
        run.mkdir(parents=True)
        paths = {}
        for name, raw in values.items():
            path = run/(name+('.yaml' if name=='glossary' else '.json'))
            path.write_bytes(raw)
            paths[name] = str(path)
        retired = []
        changed_corpus = ('profiles' in values and json.loads(values['profiles']).get('snapshot_sha256') != sha(values['snapshot']))
        if 'profiles' not in paths or changed_corpus:
            if changed_corpus:
                retired.append('profiles from a previous corpus; regenerated automatically')
            paths['profiles'] = str(run/'profiles_generated.json')
            invoke(source_root,'scripts.tac_experiment','extract','--snapshot',paths['snapshot'],'--output',paths['profiles'])
        if 'metadata' not in paths or changed_corpus:
            if changed_corpus and 'metadata' in values:
                retired.append('metadata from a previous corpus; regenerated automatically')
            paths['metadata'] = str(run/'metadata_generated.json')
            invoke(source_root,'scripts.tac_metadata','--snapshot',paths['snapshot'],'--profiles',paths['profiles'],
                   '--output',paths['metadata'])
        for name in ('inventory','contexts','classification','relations'):
            paths[name] = str(run/(name+'.json'))
        base = ['--snapshot',paths['snapshot'],'--profiles',paths['profiles']]
        boundary = ['--boundary-review',paths['boundary_review']] if 'boundary_review' in paths and not changed_corpus else []
        if changed_corpus and 'boundary_review' in paths:
            retired.append('previous-corpus boundary audit not applied; new contexts remain unreviewed')
        invoke(source_root,'scripts.tac_terms',*base,'--glossary',paths['glossary'],*boundary,
               '--format','inventory-v0.2','--output',paths['inventory'])
        invoke(source_root,'scripts.tac_term_contexts',*base,'--inventory',paths['inventory'],'--output',paths['contexts'])
        classified = [*base,'--inventory',paths['inventory'],'--contexts',paths['contexts']]
        invoke(source_root,'scripts.tac_term_classification',*classified,'--output',paths['classification'])
        invoke(source_root,'scripts.tac_term_relations',*classified,'--classification',paths['classification'],
               '--output',paths['relations'])
        candidate_root = run/'candidate_store'
        invoke(source_root,'scripts.tac_terms_review','prepare',*classified,'--classification',paths['classification'],
               '--metadata',paths['metadata'],*boundary,'--relations',paths['relations'],'--root',str(candidate_root))
        sid, frozen = load_snapshot(candidate_root)
        table, graph = run/'ARIADNE_TAC.html', run/'ARIADNE_Atlas.html'
        invoke(source_root,'scripts.tac_terms_review','export','--root',str(candidate_root),'--sid',sid,
               '--graph',str(graph),'--table',str(table))
        if capture(config,source_root)[2] != fingerprint:
            raise ValueError('Terms pipeline input/code changed during build; previous active snapshot retained')
        artifacts = {p.relative_to(output_root).as_posix():sha(p.read_bytes())
                     for p in run.rglob('*') if p.is_file() and p.suffix in {'.json','.yaml','.html'}}
        record = dict(schema=VERSION,state='built',fingerprint=fingerprint,snapshot_id=sid,
                      documents=len(frozen['graph']['articles']),artifacts=artifacts,
                      table=str(table),graph=str(graph),run=str(run),manual_decisions_enabled=False)
        record['retired_inputs'] = retired
        register_snapshot(review_root,frozen)
        (run/'run_manifest.json').write_bytes(canonical(record))
        temporary = output_root/'current_run.tmp'
        temporary.write_bytes(canonical(record))
        temporary.replace(previous_path)
        save_status(review_root,dict(state='ready',snapshot_id=sid,fingerprint=fingerprint))
        return record
    finally:
        (lock/'owner.json').unlink(missing_ok=True)
        lock.rmdir()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--output-root',type=Path,required=True)
    parser.add_argument('--watch',type=float,help='Watch input/code changes; polling interval in seconds (at least 2)')
    args = parser.parse_args()
    if not args.output_root.resolve().is_relative_to(Path.cwd().resolve()):
        parser.error('Terms pipeline output must remain inside the workspace')
    if args.watch is not None and args.watch < 2:
        parser.error('--watch must be at least 2 seconds')
    last = ''
    while True:
        try:
            result = run_once(args.config,args.output_root,Path.cwd())
        except (ValueError, FileNotFoundError, FileExistsError, RuntimeError) as exc:
            if args.watch is None:
                raise
            result = dict(state='failed_previous_snapshot_retained',error=str(exc))
            # Publish failure diagnostics only to a resolved existing local store.
            try:
                cfg = json.loads(args.config.read_bytes())
            except (json.JSONDecodeError, FileNotFoundError):
                cfg = {}
            if isinstance(cfg,dict):
                root = (Path.cwd()/cfg.get('review_root','data/reviews/terms')).resolve()
                if root.is_relative_to(Path.cwd().resolve()) and root.exists():
                    save_status(root,result)
        message = json.dumps(result,ensure_ascii=False)
        if args.watch is None or message != last:
            print(message,flush=True)
            last = message
        if args.watch is None:
            break
        time.sleep(args.watch)


if __name__ == '__main__':
    main()
