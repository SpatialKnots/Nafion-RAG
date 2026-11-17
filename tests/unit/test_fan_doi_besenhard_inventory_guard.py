"""The correction only permits the committed source inventory, not QA reviews."""

import pytest

from scripts import prepare_fan_doi_besenhard_20261113 as prep
from scripts.run_fan_doi_besenhard_preparations_20261113 import InventoryHashGuard


def test_source_inventory_hash_read_allowed():
    guard = InventoryHashGuard()
    guard("open", (str(prep.INVENTORY), "r", 0))
    assert not guard.denied


@pytest.mark.parametrize("path", [
    prep.PRIVATE / "supplied_original.md",
    prep.USER_FILE,
    prep.INVENTORY.with_name("assessment.json"),
])
def test_correction_keeps_reference_reads_blocked(path):
    guard = InventoryHashGuard()
    with pytest.raises(PermissionError):
        guard("open", (str(path), "r", 0))
    assert guard.denied == [str(path.resolve())]
