"""Freeze the parent and inspect two original PDF pages without changing source data."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import fitz

from scripts import gigachat_answer_smoke as f

BASE = f.ROOT / 'output/peng_glyph_binding_20261111'
PDF = f.ROOT / 'data/pdf/6ab4542d9156e377_Peng_2021.pdf'
PARENT = f.ROOT / 'output/quantitative_binding_20261111/comparison_v05'


def main():
    frozen = BASE / 'pre_edit_v01'
    frozen.mkdir(parents=True, exist_ok=False)
    f.verify_manifest(PARENT)
    f.verify(json.loads((PARENT / 'bindings.json').read_bytes()))
    app = f.bindings([*f.ROOT.joinpath('app').rglob('*.py'), *f.ROOT.joinpath('app').rglob('*.yaml')])
    for name in ('quantitative_facts.py',):
        f.save(frozen / name, (f.ROOT / 'app/generation' / name).read_bytes())
    f.write(frozen / 'app_bindings.json', app)
    f.write(frozen / 'bindings.json', f.bindings([Path(__file__), PARENT / 'manifest.json', PDF]))
    f.manifest(frozen)
    folder = BASE / 'pdf_probe_v01'
    folder.mkdir()
    executable = shutil.which('pdftoppm')
    if not executable:
        raise FileNotFoundError('Poppler pdftoppm required')
    observations = []
    with fitz.open(PDF) as doc:
        for pno in (4, 5):
            page = doc[pno - 1]
            text = page.get_text()
            f.save(folder / f'page{pno}.txt', text.encode())
            done = subprocess.run([executable, '-f', str(pno), '-l', str(pno), '-scale-to', '1900',
                '-singlefile', '-png', str(PDF), str(folder / f'page{pno}')], capture_output=True)
            f.save(folder / f'page{pno}_stderr.txt', done.stderr)
            if done.returncode:
                raise RuntimeError('PDF rendering failed')
            for block in page.get_text('rawdict')['blocks']:
                for line in block.get('lines', []):
                    for span in line['spans']:
                        for c in span['chars']:
                            if c['c'] not in ('\x01', '\x03', '\ue09d'):
                                continue
                            font = [row for row in page.get_fonts() if row[3].split('+', 1)[-1] == span['font']]
                            if len(font) != 1:
                                raise ValueError('Nonunique glyph font')
                            xref = font[0][0]
                            observations.append({'page': pno, 'raw_character': c['c'], 'bbox': c['bbox'],
                                'origin': c['origin'], 'font': span['font'], 'font_xref': xref,
                                'font_object': doc.xref_object(xref),
                                'font_program_sha256': f.sha(doc.extract_font(xref)[3])})
        for xref in (279, 69):
            enc = int(doc.xref_get_key(xref, 'Encoding')[1].split()[0])
            f.save(folder / f'font{xref}_encoding.txt', doc.xref_object(enc).encode())
    f.write(folder / 'observations.json', observations)
    f.write(folder / 'bindings.json', f.bindings([Path(__file__), PDF]))
    f.manifest(folder)
    print(json.dumps({'pages': 2, 'glyph_observations': len(observations), 'PDF_sha256': f.sha(PDF.read_bytes())}))


if __name__ == '__main__':
    main()
