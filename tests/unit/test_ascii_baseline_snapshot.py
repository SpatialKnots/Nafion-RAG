"""The historical baseline loader must not mutate its frozen source inventory."""

import sys

from scripts import gigachat_answer_smoke as files
from scripts.ascii_quote_selection_checks_20261105 import BASE, old_prepare


def test_historical_import_preserves_manifest_and_restores_bytecode_setting():
    frozen = BASE / "freeze_v01"
    files.verify_manifest(frozen)
    before = sys.dont_write_bytecode
    prepare = old_prepare()
    assert callable(prepare)
    assert sys.dont_write_bytecode == before
    files.verify_manifest(frozen)
