"""Read-only corpus comparison against a trusted local git revision.

Historical extraction code is executed locally. Use only trusted repository refs.
Uncapped extraction is diagnostic-only; the production cap is restored immediately.
"""

import argparse
import hashlib
import json
import subprocess
import sys
import types
from dataclasses import asdict
from pathlib import Path

from sqlalchemy import select

import app.facts.extraction as current
from app.db.models import Chunk
from app.db.session import SessionLocal
from app.facts.extraction import extract_structured_fact_candidates_from_chunk

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--baseline-ref', required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
revision = subprocess.run(['git', 'rev-parse', '--verify', args.baseline_ref + '^{commit}'],
                          check=True, capture_output=True, encoding='utf-8').stdout.strip()

baseline = types.ModuleType('numeric_baseline')
sys.modules[baseline.__name__] = baseline
code = subprocess.run(['git', 'show', revision + ':app/facts/extraction.py'],
                      check=True, capture_output=True, encoding='utf-8').stdout
exec(compile(code, revision + ':app/facts/extraction.py', 'exec'), baseline.__dict__)
records = []
with SessionLocal() as session:
    chunks = list(session.scalars(select(Chunk).order_by(Chunk.id)))
    for chunk in chunks:
        before = baseline.extract_structured_fact_candidates_from_chunk(chunk)
        after = extract_structured_fact_candidates_from_chunk(chunk)
        saved_cap = current.MAX_FACTS_PER_CHUNK
        try:
            current.MAX_FACTS_PER_CHUNK = 100000
            uncapped = extract_structured_fact_candidates_from_chunk(chunk)
        finally:
            current.MAX_FACTS_PER_CHUNK = saved_cap
        def key(c):
            return c.field_name, c.field_value_text, str(c.field_value_numeric), c.unit
        removed = [asdict(c) for c in before if key(c) not in {key(x) for x in after}]
        added = [asdict(c) for c in after if key(c) not in {key(x) for x in before}]
        if removed or added:
            records.append(dict(chunk_id=str(chunk.id), removed=removed, added=added,
                                displaced_by_cap=[asdict(c) for c in before
                                                  if key(c) not in {key(x) for x in after}
                                                  and key(c) in {key(x) for x in uncapped}],
                                after_count=len(after), text=chunk.text))
report = dict(baseline_revision=revision, baseline_code_sha256=hashlib.sha256(code.encode()).hexdigest(),
              current_code_sha256=hashlib.sha256(Path('app/facts/extraction.py').read_bytes()).hexdigest(),
              chunks=len(chunks), changed_chunks=len(records),
              removed=sum(len(r['removed']) for r in records), added=sum(len(r['added']) for r in records), records=records)
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(
    json.dumps(report,ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k!='records'}))
print(json.dumps({'cap_displaced':sum(len(r['displaced_by_cap']) for r in records),
                  'cap_affected_chunks':sum(bool(r['displaced_by_cap']) for r in records)}))
