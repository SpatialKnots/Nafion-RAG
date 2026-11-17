"""Stable frozen-baseline reads across temporary isolated preparation constants."""

from unittest.mock import patch

import pytest

from scripts import fan_doi_besenhard_rewriting_prepare_20261113 as p


def test_frozen_guard_regression_is_reproduced_without_reading_a_file():
    guard = p.r.ReferenceGuard()
    with patch.object(p.r.baseline, "BASE", p.r.BASE), patch.object(p.r.baseline, "FREEZE", p.r.FREEZE):
        with pytest.raises(PermissionError):
            guard("open", (str(p.OLD_FREEZE / "questions.json"), "r", 0))


def test_stable_guard_keeps_frozen_baseline_hash_reads():
    guard = p.StableReferenceGuard()
    with patch.object(p.r.baseline, "BASE", p.r.BASE), patch.object(p.r.baseline, "FREEZE", p.r.FREEZE):
        for path in (p.OLD_FREEZE / "questions.json", p.OLD_PREPARED / "F1/manifest.json"):
            guard("open", (str(path), "r", 0))
    assert not guard.denied


@pytest.mark.parametrize("path", [
    p.r.baseline.USER_FILE,
    p.OLD_FREEZE.parent / "private_intake_v01/supplied_original.md",
    p.r.BASE / "assessment_v01/report.json",
])
def test_stable_allowance_cannot_open_references_or_assessments(path):
    guard = p.StableReferenceGuard()
    with pytest.raises(PermissionError):
        guard("open", (str(path), "r", 0))
