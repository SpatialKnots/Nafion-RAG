"""Canonical JSON maps have sorted keys; consume decisions in frozen case order."""

from unittest.mock import patch

from scripts import gigachat_answer_smoke as f
from scripts import prepare_query_rewriting_v02_20261110 as helper
from scripts import run_query_rewriting_20261110 as r


def test_sorted_decision_map_keeps_frozen_case_order_and_original_plan_bytes(tmp_path):
    rows = [{"id": cid, "question_original": "Какова энергия?"} for cid in r.IDS]
    f.write(tmp_path / "rewrite_closed_v01.json", {"remaining_allowance": 0})
    f.write(tmp_path / "meaning_review_v01.json", {cid: {"accept": True} for cid in r.IDS})
    original_hashes = {}
    for cid in r.IDS:
        folder = tmp_path / "rewrites" / cid
        folder.mkdir(parents=True)
        f.write(folder / "result.json", {"status": "rewrite_valid"})
        f.write(folder / "plan.json", {"english_question": "What is the energy?", "keywords": ["energy"],
                                       "requirements": ["Reported energy"]})
        f.manifest(folder)
        original_hashes[cid] = f.sha((folder / "plan.json").read_bytes())
    with patch.object(r, "BASE", tmp_path), patch.object(r, "cases", return_value=rows):
        assert helper.freeze() == {"cases": 20, "accepted": 20}
        frozen = r.read(tmp_path / "plans_freeze_v01/plans.json")
    assert [c["id"] for c in frozen["cases"]] == list(r.IDS)
    for cid in r.IDS:
        assert f.sha((tmp_path / "rewrites" / cid / "plan.json").read_bytes()) == original_hashes[cid]
    f.verify_manifest(tmp_path / "plans_freeze_v01")
