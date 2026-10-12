import hashlib
import json

import pytest

from scripts import stage3_numeric_change_review as review


@pytest.mark.parametrize('mismatch', ['diff', 'extractor'])
def test_review_refuses_stale_evidence_before_database_access(tmp_path, monkeypatch, mismatch):
    diff = tmp_path / 'diff.json'
    diff.write_text(json.dumps({'current_code_sha256': 'stale'}), encoding='utf-8')
    labels = tmp_path / 'labels.json'
    labels.write_text(json.dumps({'diff_sha256': 'stale' if mismatch == 'diff'
                                 else hashlib.sha256(diff.read_bytes()).hexdigest()}), encoding='utf-8')
    output = tmp_path / 'report.json'
    monkeypatch.setattr('sys.argv', ['review', '--diff', str(diff), '--labels', str(labels), '--output', str(output)])

    def unexpected_database_access():
        pytest.fail('Stale reviews must fail before database access')

    monkeypatch.setattr(review, 'SessionLocal', unexpected_database_access)
    with pytest.raises(ValueError, match='different diff' if mismatch == 'diff' else 'Extractor changed'):
        review.main()
    assert not output.exists()
